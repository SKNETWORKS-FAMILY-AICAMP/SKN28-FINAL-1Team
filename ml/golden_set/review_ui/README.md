# 골든셋 검수 화면

`templates` 로 만든 검수표 CSV 를 브라우저에서 판정하고, **같은 스키마로 다시 내보낸다.**
뒤쪽 집계(`validate-reviews` → `synthesize`)는 그대로 쓰면 된다.

```bash
python -m ml.golden_set templates --run-dir <run> --pair-count <N>   # 검수표 만들기
open ml/golden_set/review_ui/index.html                              # 화면 열기
```

서버도 빌드도 없다. `index.html` 하나가 전부이고 외부 라이브러리를 쓰지 않는다.
고른 CSV 와 이미지는 **브라우저 밖으로 나가지 않는다.**

## 쓰는 법

1. 검수표 CSV 를 넣는다 — 넣은 표만 화면에 나온다

   `reviewer_label` 은 **파일에 적힌 값을 그대로 읽어 온다.** 검수자별 패키지라
   사람이 다시 적을 이유가 없고, 잘못 적으면 A 파일이 B 이름으로 나간다.
   서로 다른 검수자의 파일을 함께 넣으면 막는다.

2. 이미지 폴더를 고른다 — 패키지의 `images/` 폴더를 통째로 고르면 된다

   CSV 의 경로(`images/파일명`)는 ZIP 을 푼 위치 기준이라 브라우저가 그대로 열 수 없다.
   그래서 **파일 이름만** 떼어 고른 폴더에서 찾는다. 폴더를 안 넣어도 판정은 되지만
   사진 없이 보게 된다. 저장할 때 경로를 절대경로로 바꾸지 않는다.

3. 판정한다

   | 키 | 하는 일 |
   |---|---|
   | `1`~`9` | 보기 고르기 — 고르면 **다음 칸으로 자동 이동** |
   | `0` | "판단 불가" (Q 점수 전용) |
   | `Enter` / `Shift+Enter` | 다음 건 / 이전 건 |
   | `↑` `↓` | 칸 이동 |
   | `Esc` | 입력창 빠져나오기 |

   claim 은 `1` `2` `1` `2` `1` `1` 치고 `Enter` 면 한 건이 끝난다.

4. **CSV 내보내기** 를 누른다 — 표마다 `{표}.{검수자명}.csv` 로 받아진다

   내려받기와 함께 **화면에도 같은 내용을 펼쳐 준다.** 내려받기가 막히는 환경이 있어서
   (권한이 제한된 미리보기 화면 등) 그때 아무 일도 안 일어나면 판정을 회수할 길이 없다.
   파일이 잘 받아졌으면 그냥 닫으면 되고, 아니면 거기서 복사해 저장하면 된다.

판정은 브라우저에 자동 저장돼서 중간에 닫아도 **첫 미완료 건부터** 이어진다.
저장 공간은 **검수자별로 나뉘어** 있어서 한 브라우저에서 A·B 패키지를 열어도 섞이지 않는다.
다만 브라우저 데이터를 지우면 판정도 사라지므로, 길게 할 때는 중간에 한 번씩 내보내 두는 편이 안전하다.

## 계약 규칙을 옮긴 곳

`WEB_REVIEW_UI_CHANGE_REQUEST.md` 의 요구가 화면 동작으로 들어가 있다.

- 선택값은 화면에 한글로 보이지만 **저장은 영어값**(`YES` / `CONTRIBUTES` / `left` …)
- **조건부 필수** — 값이 없으면 판정을 쓸 수 없는 칸들이라, 채워야 그 건이 완료로 잡힌다
  - `detected_items_correct=NO` → `corrected_detected_items`
  - `human_judgment=CONTEXT_DEPENDENT` → `condition_tag`
  - `winner=context_dependent|unassessable` → `notes`
- claim 화면은 **모델의 기여 방향을 보여주지 않는다.** 먼저 보면 검수자가 모델 답에 끌린다
- 쌍대 비교의 좌우를 **다시 섞지 않는다.** A·B 가 같은 `pair_id` 를 반대 배치로 보도록
  파일이 이미 짜여 있어서, 화면에서 흔들면 그 설계가 깨진다
- **미리 채워진 열은 쓰지 않는다** — `reviewer_label` 포함 (아래 테스트로 확인한다)
- 행 순서·헤더를 유지하고 `CSV UTF-8`(BOM 포함)로 저장한다
- 최소수정 검수표는 이번 배포에서 제외됐다

## 고칠 때

문구·선택지·항목 순서는 전부 `index.html` 안의 **`TABLES` 상수** 한 곳에 모여 있다.
표를 손보는 일이라면 그 부분만 보면 되고 나머지 로직은 건드릴 필요가 없다.

```js
const TABLES = {
  image_observation: { title, file, key, image, ctx, fields: [...] },
  claim:             { ... },
  pairwise:          { ... },
};
```

`fields` 한 줄이 판정 칸 하나다.

```js
{ col: 'evidence_correct', ko: '문장의 시각적 사실이 …', opts: YND }
{ col: 'condition_tag', ko: '어떤 조건에서 기여하나', type: 'text',
  when: (a) => a.human_judgment === 'CONTEXT_DEPENDENT',   // 이때만 나타나고
  required: true }                                          // 채워야 완료로 잡힌다
{ col: 'notes', ko: '이유 한 문장', type: 'text',
  required: (a) => a.winner === 'unassessable' }            // 답에 따라 필수가 되기도 한다
```

`col` 은 CSV 열 이름과 **정확히 같아야 한다** (`review.py` 의 `*_REVIEW_FIELDS` 기준).

## 테스트

CSV 파싱·직렬화를 고쳤다면 반드시 돌린다.

```bash
node ml/golden_set/review_ui/test_csv.mjs <검수표가 있는 폴더>
```

`index.html` 에서 순수 함수만 떼어 실제 검수표로 확인한다. 열 밀림·따옴표 안 쉼표 보존·
미리 채워진 열 불변·행 키 생성 등을 본다.

배포 패키지(`reviewer-a-package`)로 확인한 결과는 아래와 같다.

| 표 | 행 | 열(입력) |
|---|---:|---|
| 이미지 관찰 | 160 | 10 (5) |
| claim | 479 | 13 (6) |
| 쌍대 비교 | 180 | 17 (4) |

이미지 189장은 전 행에서 파일명으로 찾아지고, 내보낸 CSV 는 행 수·열 순서·미리 채워진 값을
그대로 유지한다. 쌍대 비교의 좌우는 파일에 적힌 순서 그대로 그린다(A·B 가 서로 반대 배치).

claim 검수표의 `statement` 에는 쉼표를 품은 문장이 실제로 들어 있어서, 단순 split 으로
파싱하면 열이 통째로 밀린다. 밀린 채 저장되면 판정값이 엉뚱한 열에 들어가고 사람이
알아채기 어렵다 — 이 테스트가 막는 것이 주로 그 경우다.
