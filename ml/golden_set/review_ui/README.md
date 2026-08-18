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

1. 검수자명을 넣는다 (기본 `reviewer-a`)
2. 검수표 CSV 를 넣는다 — 넣은 표만 화면에 나온다
3. 이미지 폴더를 고른다

   CSV 의 `local_path` 는 만든 PC 의 경로(`E:\images\...`)라 다른 기기에서 열 수 없다.
   그래서 **파일 이름만** 떼어 고른 폴더에서 찾는다. 폴더를 안 넣어도 판정은 되지만
   사진 없이 보게 된다.

4. 판정한다

   | 키 | 하는 일 |
   |---|---|
   | `1`~`9` | 보기 고르기 — 고르면 **다음 칸으로 자동 이동** |
   | `0` | "판단 불가" (Q 점수 전용) |
   | `Enter` / `Shift+Enter` | 다음 건 / 이전 건 |
   | `↑` `↓` | 칸 이동 |
   | `Esc` | 입력창 빠져나오기 |

   claim 은 `1` `2` `1` `2` `1` `1` 치고 `Enter` 면 한 건이 끝난다.

5. **CSV 내보내기** 를 누른다 — 표마다 `{표}.{검수자명}.csv` 로 받아진다

판정은 브라우저에 자동 저장돼서 중간에 닫아도 **첫 미완료 건부터** 이어진다.
다만 브라우저 데이터를 지우면 판정도 사라지므로, 길게 할 때는 중간에 한 번씩 내보내 두는 편이 안전하다.

## 가이드 규칙을 옮긴 곳

`HUMAN_REVIEW_GUIDE.md` 의 규칙이 화면 동작으로 들어가 있다.

- 선택값은 화면에 한글로 보이지만 **저장은 영어값**(`YES` / `CONTRIBUTES` / `APPROVE` …)
- `verdict=EDIT` 일 때만 수정 문장 칸이 나타난다
- 사진으로 판단할 수 없는 Q 점수는 추측하지 말라는 규칙 → `0` 키가 그 자리를 맡는다
- **미리 채워진 열은 쓰지 않는다** (아래 테스트로 확인한다)
- 저장은 `CSV UTF-8` (BOM 포함)

## 고칠 때

문구·선택지·항목 순서는 전부 `index.html` 안의 **`TABLES` 상수** 한 곳에 모여 있다.
표를 손보는 일이라면 그 부분만 보면 되고 나머지 로직은 건드릴 필요가 없다.

```js
const TABLES = {
  image_observation: { title, file, key, image, ctx, fields: [...] },
  claim:             { ... },
  pairwise:          { ... },
  minimum_edit:      { ... },
};
```

`fields` 한 줄이 판정 칸 하나다.

```js
{ col: 'evidence_correct', ko: '이미지에서 근거가 확인되나', opts: YND }
{ col: 'q_color_1_5',      ko: '색 조화', opts: Q15, blankable: true }   // 0 키 허용
{ col: 'edited_statement', ko: '수정한 문장', type: 'text',
  when: (a) => a.verdict === 'EDIT' }                                    // 조건부 노출
```

`col` 은 CSV 열 이름과 **정확히 같아야 한다** (`review.py` 의 `*_REVIEW_FIELDS` 기준).

## 테스트

CSV 파싱·직렬화를 고쳤다면 반드시 돌린다.

```bash
node ml/golden_set/review_ui/test_csv.mjs <검수표가 있는 폴더>
```

`index.html` 에서 순수 함수만 떼어 실제 검수표로 확인한다. 열 밀림·따옴표 안 쉼표 보존·
미리 채워진 열 불변·행 키 생성 등을 본다.

claim 검수표의 `statement` 에는 쉼표를 품은 문장이 실제로 들어 있어서, 단순 split 으로
파싱하면 열이 통째로 밀린다. 밀린 채 저장되면 판정값이 엉뚱한 열에 들어가고 사람이
알아채기 어렵다 — 이 테스트가 막는 것이 주로 그 경우다.
