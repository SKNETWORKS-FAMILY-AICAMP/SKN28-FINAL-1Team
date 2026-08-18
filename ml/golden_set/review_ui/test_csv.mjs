/**
 * index.html 의 CSV 순수 함수만 떼어 실제 검수표로 검증한다.
 *
 * CSV 가 이 도구에서 가장 깨지기 쉬운 곳이다. claim 검수표의 statement 에는
 * "코트의 다크 브라운과 슬랙스의 베이지, 터틀넥의 …" 처럼 **쉼표를 품은 따옴표 문장**이
 * 들어 있어서, 단순 split 으로 파싱하면 열이 통째로 밀린다. 밀린 채 저장되면 판정값이
 * 엉뚱한 열에 들어가고, 그 사실을 사람이 알아채기 어렵다.
 *
 * 실행:
 *   node test_csv.mjs [검수표폴더]
 *   (기본값은 아래 DEFAULT_DIR — templates 로 뽑은 *.template.csv 가 있는 폴더)
 */
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_DIR = join(HERE, 'sample');
const DIR = process.argv[2] ?? DEFAULT_DIR;

if (!existsSync(join(DIR, 'claim_reviews.template.csv'))) {
  console.error(`검수표를 찾지 못했습니다: ${DIR}`);
  console.error('사용법: node test_csv.mjs <검수표가 있는 폴더>');
  process.exit(2);
}

/* index.html 안의 <script> 에서 순수 함수 구간만 잘라 실행한다.
   (그 뒤는 DOM 을 만지는 코드라 노드에서 돌지 않는다) */
const html = readFileSync(join(HERE, 'index.html'), 'utf8');
const script = html.slice(html.indexOf('<script>') + 8, html.indexOf('</script>'));
const pure =
  script.slice(0, script.indexOf("if (typeof window !== 'undefined')")) +
  'window.__gsreview = { parseCsv, toCsv, applyAnswers, asObject, TABLES, ORDER };';

const window = {};
new Function('window', 'console', pure)(window, console);
const { parseCsv, toCsv, applyAnswers, asObject, TABLES } = window.__gsreview;

let failed = 0;
const ok = (cond, msg) => {
  console.log(`${cond ? '✅' : '❌'} ${msg}`);
  if (!cond) failed += 1;
};
const read = (name) => parseCsv(readFileSync(join(DIR, name), 'utf8'));
const strip = (h) => h.map((c) => c.replace(/^﻿/, ''));

/* ── 1. 따옴표 안의 쉼표가 살아남는가 ── */
const claim = read('claim_reviews.template.csv');
const header = strip(claim[0]);
const first = asObject(claim[0], claim[1]);

ok(claim[1].length === header.length, `열 개수 일치 (${claim[1].length})`);
ok(Boolean(first.golden_id && first.claim_id), '미리 채워진 열이 제자리에 있음');
const quoted = claim.slice(1).find((r) => (asObject(claim[0], r).statement ?? '').includes(','));
ok(Boolean(quoted), '쉼표를 품은 문장을 찾음 (파싱 검증 대상)');

/* ── 2. 판정 없이 왕복해도 원본이 보존되는가 ── */
const rt = parseCsv(
  toCsv(header, applyAnswers(claim[0], claim.slice(1), {}, 'reviewer-a', TABLES.claim.key)),
);
ok(rt.length === claim.length, `행 수 보존 (${rt.length - 1}건)`);
ok(asObject(rt[0], rt[1]).statement === first.statement, '왕복 후 statement 동일');
ok(asObject(rt[0], rt[1]).reviewer_label === 'reviewer-a', 'reviewer_label 채워짐');

/* ── 3. 판정값이 올바른 열에 들어가는가 ── */
const key = TABLES.claim.key(first);
const answers = {
  [key]: {
    evidence_correct: 'YES',
    human_judgment: 'CONTRIBUTES',
    verdict: 'EDIT',
    human_confidence_1_3: '2',
    overgeneralization_risk: 'NO',
    stereotype_risk: 'NO',
    edited_statement: '고쳐 쓴 문장, 쉼표 포함',
    notes: '메모',
  },
};
const out = parseCsv(
  toCsv(header, applyAnswers(claim[0], claim.slice(1), answers, 'reviewer-b', TABLES.claim.key)),
);
const o1 = asObject(out[0], out[1]);
ok(o1.verdict === 'EDIT' && o1.human_confidence_1_3 === '2', '판정값이 정확한 열에 들어감');
ok(o1.edited_statement.includes('쉼표 포함'), '새로 쓴 문장의 쉼표도 안전');
ok(o1.statement === first.statement, '미리 채워진 열은 건드리지 않음');
if (out.length > 2) ok(asObject(out[0], out[2]).verdict === '', '판정 안 한 행은 빈칸 유지');

/* ── 4. 네 표의 입력 열이 도구 정의와 맞는가 ── */
for (const def of Object.values(TABLES)) {
  const file = `${def.file}.template.csv`;
  if (!existsSync(join(DIR, file))) {
    console.log(`⏭  ${def.title}: ${file} 없음 — 건너뜀`);
    continue;
  }
  const rows = read(file);
  const cols = new Set(strip(rows[0]));
  const missing = def.fields.map((f) => f.col).filter((c) => !cols.has(c));
  ok(
    missing.length === 0 && cols.has('reviewer_label'),
    `${def.title}: 입력 열 ${def.fields.length}개 모두 존재${missing.length ? ` — 누락 ${missing}` : ''}`,
  );
  const k = def.key(asObject(rows[0], rows[1]));
  ok(Boolean(k) && !String(k).includes('undefined'), `${def.title}: 행 키 생성 (${k})`);
}

console.log(failed ? `\n❌ 실패 ${failed}건` : '\n✅ 전부 통과');
process.exit(failed ? 1 : 0);
