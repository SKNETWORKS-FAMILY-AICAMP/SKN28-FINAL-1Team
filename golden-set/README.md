# 골든셋 (Golden Set) — 추천 판단의 기준 자산

- **작성일**: 2026-08-06
- **브랜치**: `golden_set`
- **성격**: 추천 시스템이 "이 조합이 좋다/나쁘다"를 판단할 때 참조하는 **기준 규칙 자산**

---

## 0. 용어 정리 — 이 폴더의 '골든셋'은 평가셋이 아니다

프로젝트 안에 **골든셋**이라는 말이 두 가지 뜻으로 쓰이고 있어 먼저 갈라 둔다.

| | 이 폴더 (`golden-set/`) | `fashion-rag-today-look_4.md` §5 |
|---|---|---|
| 뜻 | **추천이 참조하는 기준 규칙** | **추천을 채점하는 평가셋** |
| 예 | "고채도 보색 2색 대면적 금지" | "최저 3℃ 시나리오에서 반팔이 나오면 오답" |
| 성격 | 입력 | 정답지 |

두 개를 한 폴더에 두면 **자기가 만든 규칙으로 자기를 채점**하게 되어 평가가 무의미해진다.
따라서 평가용 골든셋(날씨×체형×옷장 20~30케이스)은 이 폴더에 넣지 않는다.

---

## 1. 폴더 구성

**주제별로 자기 완결**이다. 색상 작업 중에는 체형 파일이 보이지 않고, 그 반대도 같다.
서술 문서(`.md`)만 `docs/`에 모아 **판단 원천(JSON)과 설명(MD)을 물리적으로 분리**했다 — §2 원칙이 폴더 구조에 그대로 드러난다.

```
golden-set/
├── README.md                           # 이 문서 (두 주제 공통 진입점)
│
├── docs/                               # 서술 문서 — 판단하지 않는다
│   ├── 00-selection-criteria.md        #   무엇을 골든셋에 넣는가 (선정 기준 5축, 공통)
│   ├── 01-color-combination-rules.md   #   색상 조합 규칙 설명
│   ├── 02-body-proportion-rules.md     #   체형·비율 규칙 설명
│   └── 03-body-proportion-matrix.md    #   체형 4축 처방 요약표 (파생)
│
├── color/                              # ■ 색상
│   ├── rules/                          #   판단 원천
│   │   ├── color_rules.json            #     [생성물] v2 18색(CIELCh) + 153쌍 등급
│   │   ├── color_taxonomy_map.json     #     [수기] 아이템 태그(한국어) → v2 색 변환표
│   │   └── _archive/                   #     grade_map_extracted(추출 실패본) · v1 보존
│   ├── tools/
│   │   ├── compute_color_attributes.py #     hex → CIELCh 속성
│   │   ├── build_color_rules.py        #     속성 + 규칙 R1~R6 → color_rules.json
│   │   ├── validate_color_map.py       #     [검증] 매핑표 ↔ taxonomy ↔ v2 정합
│   │   ├── crosscheck_grade_map.py     #     [검증] 추출 등급표 대조 (기각 근거 출력)
│   │   ├── generate_outfit_grid.py / gen_*.py  # 코디 예시 이미지 생성
│   │   └── _archive/                   #     extract_*·detect_*·v1 (실패 시도 기록)
│   └── images/
│       ├── reference/pinterest_ref.jpg #     v2 팔레트 출처 (제3자 이미지, 노출 금지)
│       └── outfits/                    #     코디 예시 — **전부 생성물, 판단 원천 아님**
│
└── body/                               # ■ 체형
    ├── rules/
    │   ├── body_shape_thresholds.json  #     [생성물] 사이즈코리아 181명 백분위
    │   └── body_fit_rules.json         #     [수기] 4축(폭 + 세로 3종) 처방
    ├── tools/
    │   ├── derive_body_thresholds.py   #     사이즈코리아 CSV → 체형 임계값
    │   └── _archive/
    └── images/
        ├── shapes/                     #     5체형 개별 실루엣 (6장)
        └── comparison/                 #     성별·BMI·목·허벅지 비교 (6장, 03번 문서가 참조)
```

> **`color/images/outfits/curated/curated_matching_rules.json`은 파일명과 달리 판단 원천이 아니다.**
> 예시 이미지를 "어떤 조합으로 그릴지" 고르는 생성 입력이다. 추천에 쓰면
> `color/rules/color_rules.json`과 충돌한다 — 여기선 Black의 짝을 6개로 한정하지만
> R2는 Black이 모든 accent와 잘 맞는다고 판정한다. 파일 안에 `role` 키로 명시해 두었다.
> **판단 원천은 `*/rules/` 아래에만 둔다** — 이 파일이 `images/` 밑에 있는 이유다.

---

## 2. 판단 원천 원칙 (중요)

`fashion-rag-today-look_4.md` §3-3의 **이중 원천 방지 원칙**을 그대로 따른다.

> **`*/rules/*.json`이 판단의 유일한 원천이다. `*.md`는 판단하지 않는다.**

- 숫자·임계값·등급은 전부 `*/rules/`의 JSON에만 존재한다.
- MD 문서는 그 JSON을 **인용해 설명**할 뿐이며, MD에만 있는 숫자는 규칙이 아니다.
- `filter_rules.py`(추후 구현)는 이 JSON을 로드해 쓰고, MD를 파싱하지 않는다.
- knowledge 청크(RAG)는 MD에서 생성하되, 역시 **설명 근거 검색용**이지 판단용이 아니다.

`[생성물]` 표시된 파일은 **직접 수정하지 않는다.** `*/tools/`의 스크립트를 고치고 다시 실행한다.

```bash
# 색상 규칙 재생성
python golden-set/color/tools/build_color_rules.py

# 체형 임계값 재산출
python golden-set/body/tools/derive_body_thresholds.py

# 검증 (taxonomy나 팔레트가 바뀌면 여기서 먼저 깨진다)
python golden-set/color/tools/validate_color_map.py
python golden-set/color/tools/crosscheck_grade_map.py
```

### 팔레트가 아이템 태그와 다르다 — 매핑표 필수

v2 색 이름(영문 18색)은 레퍼런스에서 온 것이고, 실제 아이템에 붙는 `color` 태그는
`taxonomy.py::COLORS`의 한국어 17색이다. 두 체계 사이에 **`rules/color_taxonomy_map.json`이
반드시 끼어야** `filter_rules.py`가 `color="레드"`를 받아 등급을 찾을 수 있다.
매핑 5건은 손실이 있으며(`멀티`는 대응 색 자체가 없다), 상세는 [01번 문서 §6](docs/01-color-combination-rules.md)에 있다.

---

## 3. 현재 상태 요약

| 규칙 축 | 상태 | 근거 |
|---|---|---|
| 색상 조합 (v2 18색, 153쌍) | ✅ 완료 | CIELCh 속성 + 규칙 R1~R6 자동 등급 — 권장 125 · 허용 7 · 주의 19 · 기피 2 |
| 아이템 태그 ↔ v2 매핑 | ⚠️ **손실 5건** | `블루`는 Blue 추가로 해소. `멀티`만 대응 색 없음 — [01번 §6](docs/01-color-combination-rules.md) |
| 레퍼런스 등급표 교차검증 | ❌ **불가** | 이미지 셀 검출 실패 (7개 행 뭉개짐, na 27칸) — 계산 등급 유지 |
| 체형 분류 (가로축 5분류) | ✅ 완료 | 사이즈코리아 실측 181명 성별 백분위 |
| 체형별 핏·기장 권장 | ✅ 초안 | 수기 규칙 (`body_fit_rules.json` v0.3.0 — 색 처방 없음) — `should` 전용 |
| **세로축 ① 상체:하체** | ⛔ **입력 없음** | 다리길이/앉은키 컬럼 부재 |
| **세로축 ② 목 길이** | ⛔ **입력·태그 둘 다 없음** | 목 컬럼 부재 + `neckline` 태그 부재 |
| **세로축 ③ 허벅지:종아리** | ⛔ **입력 없음** ⚠️ | `thigh`/`calf` 컬럼은 있으나 **둘레라 오용 위험** — [02번 §4-2](docs/02-body-proportion-rules.md) |
| 룩 단위 규칙 L1~L5 | ⬜ 미JSON화 | 문서 초안만 존재 — [01번 §7](docs/01-color-combination-rules.md) |
| 퍼스널컬러 4계절 | ⬜ 미분류 | 새 축인지 범위 밖인지 미정 — 현재는 예시 이미지 생성 입력 |
| 날씨·TPO 규칙 | ⬜ 범위 밖 | `filter_rules.py`(문서 4 P0)가 담당 |

### 다음에 해야 할 일 (우선순위)

1. ~~**v2 팔레트에 `Blue` 추가**~~ — ✅ 완료(2026-08-06). 같은 구조의 `퍼플`→Lavender 문제로 **중간 명도 퍼플** 추가 검토.
2. **세로축 3종 입력 방식 결정** — 세로축 규칙 전체가 여기에 막혀 있다.
   pose 추출 1회로 세 값이 한 번에 나오므로 **하나의 결정**이다.
3. **taxonomy 4건 추가** — `rise`, `neckline`, `FITS`에 부츠컷, 신발 소분류 세분화.
   입력이 생겨도 이게 없으면 처방을 아이템에 적용할 수 없다.
4. **`멀티` 처리 확정** — `multi_rule`로 남길지, `color_rules.json`에 1급 항목으로 넣을지.
5. **L1~L5 JSON화** — 룩 단위 규칙이 코드에 전달되지 않는다.

> ⚠️ **`thigh_calf_ratio`를 `BodyMeasurement.thigh / .calf`로 계산하지 말 것.**
> 두 컬럼은 존재하지만 **둘레**다. 그대로 쓰면 에러 없이 무관한 값이 나오고
> 그 값으로 실루엣 처방이 정해진다. `body_fit_rules.json`의 `do_not_use`에 명시돼 있다.

---

## 4. 반영되지 않은 외부 자료

작업 시점에 아래 두 자료를 읽지 못했다. 내용을 받으면 규칙에 병합해야 한다.

1. **Google Drive 골든셋 폴더** — 이 세션에 Drive 접근 도구가 없다.
2. **Confluence 체형·색상 규칙 페이지** (`.../pages/19365905`) — Atlassian 연동이 미인증 상태다.
   (전달받은 두 링크는 같은 페이지 ID다.)

두 자료가 이 폴더의 규칙과 충돌할 경우, **Confluence 문서가 팀 합의 원본이므로 우선**한다.
