import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const buildDirectory = mkdtempSync(join(tmpdir(), 'cozy-shared-reference-'));
const require = createRequire(import.meta.url);

function compilePresentationModule() {
  const compiler = join(mobileRoot, 'node_modules', 'typescript', 'bin', 'tsc');
  const result = spawnSync(
    process.execPath,
    [
      compiler,
      'src/lib/sharedReferencePresentation.ts',
      '--ignoreConfig',
      '--target',
      'ES2022',
      '--module',
      'node16',
      '--moduleResolution',
      'node16',
      '--outDir',
      buildDirectory,
      '--skipLibCheck',
      '--declaration',
      'false',
    ],
    { cwd: mobileRoot, encoding: 'utf8' },
  );

  if (result.status !== 0) {
    throw new Error(`sharedReferencePresentation.ts 컴파일 실패\n${result.stdout}${result.stderr}`);
  }
  return require(join(buildDirectory, 'sharedReferencePresentation.js'));
}

try {
  const {
    buildReferenceBadge,
    buildReferenceBubble,
    sharedReferenceUnavailableLabel,
  } = compilePresentationModule();

  assert.equal(
    sharedReferenceUnavailableLabel({
      referenceEligible: false,
      referenceUnavailableReason: 'PRIVATE',
    }),
    '나만 보기 상태',
  );
  assert.equal(
    sharedReferenceUnavailableLabel({
      referenceEligible: false,
      referenceUnavailableReason: 'VECTOR_NOT_READY',
    }),
    '이미지 분석 중',
  );
  assert.equal(
    sharedReferenceUnavailableLabel({
      referenceEligible: true,
      referenceUnavailableReason: null,
    }),
    null,
    'BORROWED도 서버가 eligible이면 선택 가능해야 한다.',
  );

  assert.deepEqual(
    buildReferenceBadge({
      source_type: 'WARDROBE',
      match_type: 'STYLE_SIMILAR',
      reasons: ['색상과 핏이 비슷해요'],
    }),
    {
      label: '친구 옷과 스타일이 비슷한 내 옷',
      isStyleFallback: true,
      reasons: ['색상과 핏이 비슷해요'],
    },
  );
  assert.deepEqual(
    buildReferenceBadge({
      source_type: 'PRODUCT',
      match_type: 'VISUAL_SIMILAR',
      reasons: ['실루엣이 비슷해요'],
    }),
    {
      label: '친구 옷과 비슷한 새 상품',
      isStyleFallback: false,
      reasons: ['실루엣이 비슷해요'],
    },
  );
  assert.equal(buildReferenceBadge({ match_type: 'UNKNOWN' }), null);

  assert.deepEqual(
    buildReferenceBubble(
      {
        shared_item_id: 'shared-item-1',
        item_name: '',
        category_large: '아우터',
        owner_name: '하영',
        room_name: '친구 옷장',
        image_url: null,
      },
      '이 옷처럼 추천해줘',
    ),
    {
      kind: 'reference',
      text: '이 옷처럼 추천해줘',
      sharedItemId: 'shared-item-1',
      imageUrl: null,
      itemName: '아우터',
      ownerName: '하영',
      roomName: '친구 옷장',
    },
    '대화를 다시 열어도 reference_summary로 말풍선을 복원해야 한다.',
  );

  console.log('공유 옷 레퍼런스 모바일 회귀 테스트: 7개 시나리오 통과');
} finally {
  const expectedPrefix = join(tmpdir(), 'cozy-shared-reference-');
  if (buildDirectory.startsWith(expectedPrefix)) {
    rmSync(buildDirectory, { recursive: true, force: true });
  }
}
