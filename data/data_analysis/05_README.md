# 05. (huggingface) polyvore-outfits 데이터 보는 법

## 1. 이 데이터는 무엇인가

`s3://skn28-cozy/05_huggingface_polyvore_outfits/`는 Polyvore(패션 SNS·쇼핑몰) 사용자 68,306명이 직접 구성한 코디(outfit)와 그 코디를 이루는 261,058개 개별 패션 아이템의 이미지·텍스트 메타데이터를 한 묶음으로 담은 공개 벤치마크 데이터셋이다. 원 논문은 Vasileva et al., "Learning Type-Aware Embeddings for Fashion Compatibility", ECCV 2018다.

단순 아이템 나열이 아니라 "어떤 아이템들이 하나의 코디로 함께 입혔는가"라는 조합(compatibility) 정보 자체가 라벨로 들어 있어, 우리 프로젝트의 "아이템 조합 추천 룰" 학습·검증에 바로 쓸 수 있다.

확인된 핵심 자산:

- 코디(outfit) 68,306개 — 사람이 직접 만든 정답 조합
- 아이템 261,058개 — 상품 단위 텍스트 메타데이터
- 상품 이미지 바이너리(parquet) — huggingface datasets 형식
- 호환성(compatibility) 이진 라벨 — "이 조합이 어울리는가/안 어울리는가"
- 빈칸채우기(FITB) 문제 — "이 코디에서 비어있는 슬롯에 가장 어울리는 아이템은?"
- 카테고리 매핑표 — `category_id` ↔ 카테고리명 ↔ 대분류(`semantic_category`)

## 2. S3 위치

기준 버킷:

```powershell
aws s3 ls s3://skn28-cozy/
```

5번 데이터 최상위:

```powershell
aws s3 ls s3://skn28-cozy/05_huggingface_polyvore_outfits/
```

이미지 parquet 위치:

```text
s3://skn28-cozy/05_huggingface_polyvore_outfits/data/disjoint/
s3://skn28-cozy/05_huggingface_polyvore_outfits/data/nondisjoint/
```

라벨·구조 데이터 위치:

```text
s3://skn28-cozy/05_huggingface_polyvore_outfits/disjoint/
s3://skn28-cozy/05_huggingface_polyvore_outfits/nondisjoint/
s3://skn28-cozy/05_huggingface_polyvore_outfits/maryland_polyvore_hardneg/
```

코디·아이템 메타 위치:

```text
s3://skn28-cozy/05_huggingface_polyvore_outfits/polyvore_item_metadata.json
s3://skn28-cozy/05_huggingface_polyvore_outfits/polyvore_outfit_titles.json
```

## 3. 전체 폴더 구조

`aws s3 ls --recursive --summarize` 기준 39개 오브젝트, 약 4.30GB. 핵심 트리는 다음과 같다.

```text
05_huggingface_polyvore_outfits/
├── README.md                          # huggingface 데이터셋 카드 (6,868 bytes)
├── categories.csv                     # 카테고리 ID ↔ 카테고리명 ↔ 대분류 (4,910 bytes)
├── polyvore_item_metadata.json        # 아이템 261,058개 텍스트 메타 (≈ 105MB)
├── polyvore_outfit_titles.json        # 코디별 제목 (≈ 6.6MB)
│
├── data/                              # 이미지 바이너리 parquet (huggingface datasets 로딩용)
│   ├── disjoint/
│   │   ├── train.parquet              # ≈ 649MB
│   │   ├── validation.parquet         # ≈ 132MB
│   │   └── test.parquet               # ≈ 629MB
│   └── nondisjoint/
│       ├── train.parquet              # ≈ 1.79GB  ★ 가장 큰 파일
│       ├── validation.parquet         # ≈ 223MB
│       └── test.parquet               # ≈ 427MB
│
├── disjoint/                          # "아이템 단위 분리" 스플릿의 라벨·구조 데이터
│   ├── train.json / valid.json / test.json
│   ├── compatibility_train.txt / _valid.txt / _test.txt
│   ├── fill_in_blank_train.json / _valid.json / _test.json
│   └── typespaces.p
│
├── nondisjoint/                       # "코디 단위 분리" 스플릿, 파일 구성 동일
│
└── maryland_polyvore_hardneg/         # Maryland 원본 기준 하드 네거티브 버전
```

가장 중요한 구조적 포인트: **`disjoint`/`nondisjoint` 폴더가 두 세트** 존재한다 (`data/disjoint`, `data/nondisjoint` vs 최상위 `disjoint/`, `nondisjoint/`).

- `data/*` = **이미지 바이너리 parquet**
- 최상위 `disjoint/`, `nondisjoint/` = **이미지 없이 라벨·조합 구조(JSON·TXT)만**

이 두 세트는 파일명이 겹치지 않게 계층으로 분리되어 있어 혼동하지 않도록 주의.

## 4. 폴더별 의미

### README.md (6,868 bytes)

huggingface 데이터셋 카드의 원본. YAML 프론트매터에 `configs:`(disjoint / nondisjoint 두 config), `task_categories:`, `dataset_info:` 등이 들어 있어 본 데이터셋이 `datasets.load_dataset`으로 그대로 로드되도록 설계됐음을 알려준다.

### categories.csv (4,910 bytes)

`category_id`, 카테고리 세부명, 대분류(`semantic_category`)의 3컬럼 CSV. 직접 열어 확인한 예시:

```text
28,pants,bottoms
29,shorts,bottoms
46,heels,shoes
55,baseball cap,hats
62,necklace,jewellery
```

대분류(`semantic_category`)는 약 11종으로 확인됨: `all-body`, `tops`, `bottoms`, `outerwear`, `shoes`, `bags`, `accessories`, `hats`, `scarves`, `sunglasses`, `jewellery`.

### polyvore_item_metadata.json (≈ 105MB)

key가 `item_id`인 큰 딕셔너리. 직접 발췌한 한 레코드:

```json
"183179503": {
  "url_name": "christian pellizzari floral jacquard trousers",
  "description": "Gold and black silk blend floral jacquard trousers from Christian Pellizzari. Color: Metallic. Gender: Female. Pattern: Floral. Material: Viscose/Polyester/Silk/Polyamide.",
  "catgeories": ["Women's Fashion", "Clothing", "Pants", "Christian Pellizzari pants"],
  "title": "Christian Pellizzari floral jacquard trousers",
  "related": ["Floral pants", "Grey pants", "Print pants", "Patterned pants", "Floral-print pants", "Metallic pants"],
  "category_id": "28",
  "semantic_category": "bottoms"
}
```

`catgeories`는 원본 오탈자 그대로 유지됨에 유의. 실제 활용 시 텍스트가 비어 있는 저메타데이터 아이템은 필터링하는 전처리가 필요하다.

### polyvore_outfit_titles.json (≈ 6.6MB)

key가 `set_id`, value가 `{url_name, title}`. 발췌:

```json
"219779031": {"url_name": "spring trend colored denim", "title": "Denim Jumpers"},
"223685706": {"url_name": "summer date", "title": "Summer Date"}
```

TPO(상황·목적)를 유추할 수 있는 자연어 라벨. 단, 샘플 60건 기준 `title`이 빈 문자열인 코디가 약 15% 존재함을 확인.

### data/{disjoint,nondisjoint}/*.parquet

실제 아이템 이미지 데이터. huggingface `datasets` 라이브러리로 바로 로드하도록 설계된 parquet이다. parquet 스키마는 미확인이지만, 파일명/용량(가장 큰 train.parquet ≈ 1.79GB)을 미루어 이미지 바이트 + `item_id` 식별자가 컬럼으로 들어 있는 구조로 추정.

### disjoint/, nondisjoint/ 공통 파일

| 파일 | 역할 |
|---|---|
| `train.json` / `valid.json` / `test.json` | `set_id → items:[{item_id, index}]` 코디 구성 |
| `compatibility_*.txt` | 코디 호환성 이진분류 라벨 (1=호환, 0=비호환) |
| `fill_in_blank_*.json` | 빈칸채우기(FITB) 4지선다 문제·정답 |
| `typespaces.p` | 카테고리쌍 임베딩 서브스페이스 정의(pickle, ≈ 1.4KB) |

disjoint는 아이템 단위로, nondisjoint는 outfit 단위로 train/valid/test가 분리돼 있다(아래 6·7절에서 자세히).

### maryland_polyvore_hardneg/

오리지널(Maryland) Polyvore 데이터 기준의 하드 네거티브 버전. `compatibility_*.txt`, `fill_in_blank_*.json`만 있고 코디 구성 json은 없다. 위 disjoint/nondisjoint 라벨과 짝을 맞춰 쓰면 헷갈리는 오답 후보로 모델을 더 엄격히 평가할 수 있다.

## 5. 가장 중요한 파일: train.json

`disjoint/train.json`(또는 `nondisjoint/train.json`)은 코디 구성의 **중심 테이블**이다. 한 줄이 곧 outfit 한 세트다.

발췌한 첫 번째 레코드:

```json
{
  "items": [
    {"item_id": "132621870", "index": 1},
    {"item_id": "153967122", "index": 2},
    {"item_id": "171169800", "index": 3}
  ],
  "set_id": "199244701"
}
```

핵심 키:

- `set_id`: 코디의 PK
- `items[].item_id`: 각 아이템의 ID — `polyvore_item_metadata.json`의 키와 동일한 키 공간
- `items[].index`: 코디 내 슬롯 순서(보통 1=상의류부터 소품류까지 카테고리 우선순위)

즉 `train.json`을 중심축으로 두고 `polyvore_item_metadata.json`을 좌측 조인하면 "이 코디는 어떤 아이템들로 이뤄졌고 그 아이템들의 텍스트 속성은 무엇인가"가 한 번에 펼쳐진다.

## 6. 샘플 하나를 보는 순서

`nondisjoint/train.json`에서 첫 번째 코디를 골라본다.

1. `set_id = 199244701`을 찾는다.
2. `items[].item_id` 값 `132621870`, `153967122`, `171169800`을 기억해 둔다.
3. `polyvore_item_metadata.json`에서 이 세 item_id 각각의 메타데이터를 본다.
4. 각 item에 대해 `category_id`로 `categories.csv`를 조회해 대분류(`semantic_category`)를 매핑한다.
5. 같은 item_id로 `data/{disjoint,nondisjoint}/*.parquet`에서 이미지를 찾는다 — parquet 스키마는 미확인이지만 동일 item_id 컬럼이 있을 것으로 추정.
6. (선택) `compatibility_train.txt`에서 `199244701_1 199244701_2 199244701_3` 같은 패턴으로 등장하는 라인을 찾으면 "이 조합이 호환인가(라벨 1)" / "이 조합이 비호환인가(라벨 0)" 여부를 알 수 있다.
7. (선택) `fill_in_blank_train.json`에서 같은 `set_id`의 question을 찾아 어떤 아이템이 정답 슬롯에 들어갔는지 확인한다.

이 7단계 한 번이면 "한 코디 = 한 정답 조합"이라는 데이터의 본질이 잡힌다.

## 7. SQL로 보면 쉬운 이유

파일은 여러 개로 나뉘어 있지만, 실제로는 관계형 테이블처럼 다룰 수 있다. 추천하는 스키마는 다음과 같다.

```sql
-- 한 코디 = 한 outfit (set_id PK)
CREATE TABLE outfits (
    set_id   TEXT PRIMARY KEY,
    source   TEXT  -- 'disjoint' | 'nondisjoint'
);

-- outfit N : N item
CREATE TABLE outfit_items (
    set_id   TEXT,
    index    INTEGER,
    item_id  TEXT,
    PRIMARY KEY (set_id, index)
);

-- 아이템 텍스트 메타
CREATE TABLE items (
    item_id           TEXT PRIMARY KEY,
    url_name          TEXT,
    title             TEXT,
    description       TEXT,
    related           TEXT,            -- JSON array 그대로
    category_id       TEXT,
    semantic_category TEXT
);

-- 카테고리 매핑(카테고리 표준화 기준표)
CREATE TABLE categories (
    category_id       TEXT,
    category_name     TEXT,
    semantic_category TEXT
);

-- 코디 호환성 이진분류(정답 라벨)
CREATE TABLE compatibility (
    label            INTEGER,   -- 1=호환, 0=비호환
    set_id           TEXT,
    set_part_count   INTEGER,
    set_tokens       TEXT       -- "199244701_1 199244701_2 ..."
);

-- 빈칸채우기 4지선다 (set_id 단위)
CREATE TABLE fitb (
    set_id         TEXT,
    blank_position INTEGER,
    correct_token  TEXT,          -- set_id가 question과 동일한 정답
    answer1        TEXT,
    answer2        TEXT,
    answer3        TEXT,
    answer4        TEXT
);

-- 코디 자연어 제목(TPO 시드)
CREATE TABLE outfit_titles (
    set_id    TEXT PRIMARY KEY,
    url_name  TEXT,
    title     TEXT
);
```

이렇게 넣으면 질문을 SQL로 바꿀 수 있다.

특정 코디의 아이템 구성 보기:

```sql
SELECT oi.index, i.item_id, i.title, i.semantic_category
FROM outfits o
JOIN outfit_items oi ON o.set_id = oi.set_id
JOIN items i        ON oi.item_id = i.item_id
WHERE o.set_id = '199244701'
ORDER BY oi.index;
```

카테고리 조합(이 코디 = tops + bottoms + shoes처럼) 빈도 집계:

```sql
WITH per_outfit AS (
    SELECT o.set_id,
           MAX(CASE WHEN i.semantic_category='tops'        THEN 1 ELSE 0 END) AS has_tops,
           MAX(CASE WHEN i.semantic_category='bottoms'      THEN 1 ELSE 0 END) AS has_bottoms,
           MAX(CASE WHEN i.semantic_category='shoes'        THEN 1 ELSE 0 END) AS has_shoes,
           MAX(CASE WHEN i.semantic_category='outerwear'    THEN 1 ELSE 0 END) AS has_outerwear
    FROM outfits o JOIN outfit_items oi ON o.set_id = oi.set_id
                   JOIN items i        ON oi.item_id = i.item_id
    GROUP BY o.set_id
)
SELECT has_tops, has_bottoms, has_shoes, has_outerwear, COUNT(*) AS n_outfits
FROM per_outfit
GROUP BY has_tops, has_bottoms, has_shoes, has_outerwear
ORDER BY n_outfits DESC;
```

"이 상의에 자주 매칭된 하의" 보기(FITB의 co-occurrence 활용):

```sql
SELECT o2.item_id, COUNT(*) AS cnt
FROM outfit_items o1
JOIN outfit_items o2
     ON o1.set_id = o2.set_id AND o1.index <> o2.index
JOIN items i1 ON o1.item_id = i1.item_id
JOIN items i2 ON o2.item_id = i2.item_id
WHERE i1.semantic_category = 'tops'
  AND i2.semantic_category = 'bottoms'
  AND o1.item_id = '183179503'          -- 기준이 되는 상의
GROUP BY o2.item_id
ORDER BY cnt DESC
LIMIT 20;
```

이렇게 두면 "방대한 JSON 한 덩어리"가 아니라 **테이블 조합**으로 다룰 수 있다.

## 8. 이 데이터로 알 수 있는 것

이 데이터로 바로 알 수 있는 것:

- 어떤 카테고리 조합이 자주 등장하는가(tops+bottoms+shoes, outer+inner 같은 슬롯 패턴)
- 같은 카테고리 안에서 어떤 item_id들이 자주 같이 코디를 구성하는가
- "Summer Date", "Workout Wear" 같은 TPO 자연어 라벨이 붙은 코디의 카테고리 구성
- 비호환(라벨 0) 조합의 패턴 — 흔한 동시 등장 빈도와 비교해 비정상 패턴 학습

조금 더 분석하면 알 수 있는 것:

- 상의별로 자주 매칭되는 하의 / 신발의 상위 N
- 카테고리별 / 색상별(description의 "Color: Metallic" 같은 패턴) 조합 빈도
- 빈칸채우기 정답률로 측정한 "어울리는 아이템 추천" 모델의 정확도
- Maryland 하드 네거티브로 모델의 헷갈리는 케이스 강건성

추천 시스템 활용 시 가장 먼저 봐야 할 파일은 `polyvore_outfit_titles.json` + `train.json`의 조합이다. 이 둘을 합치면 "TPO별 정답 코디 구성"이 만들어진다.

## 9. 추천 시스템에 활용하는 방법

### 코디 조합 학습 데이터로 사용

`{disjoint,nondisjoint}/train.json`의 `set_id → items` 구조와 `polyvore_item_metadata.json`의 `semantic_category`를 조인하면, **"상의 X + 하의 Y + 신발 Z가 한 세트로 얼마나 자주 등장하는가"** 라는 카테고리 조합 빈도표를 만들 수 있다. 이 표가 곧 우리 추천 엔진의 "아이템 조합 규칙" 기반이 된다. `compatibility_*.txt`의 0/1 라벨은 그 규칙을 지도학습으로 검증·정교화하는 정답셋이다.

### 빈칸채우기(FITB) = "다음 아이템 추천"과 동형

`fill_in_blank_*.json`의 "일부 아이템이 주어졌을 때 나머지 한 슬롯에 어울리는 아이템은?" 문제는 우리 서비스의 "사용자가 이미 고른 상의/하의에 어울리는 아우터·신발·액세서리 추천" 시나리오와 구조가 같다. 추천 모델의 학습·평가 데이터로 재사용하거나 few-shot 예시로 변형해 쓸 수 있다.

### TPO(상황·목적) 자연어 라벨

`polyvore_outfit_titles.json`의 `title`("Summer Date", "Workout Wear", "Mardi Gras")은 TPO 기반 추천의 자연어 라벨이다. 빈 문자열(샘플 기준 10~15%)은 제외하고, `url_name`(검색 쿼리 원문)을 보조 텍스트로 함께 쓰면 활용도가 높다.

### 색상/소재/패턴 추출 → RAG 지식베이스

`polyvore_item_metadata.json`의 `description`(예: "...Color: Metallic. Pattern: Floral. Material: Viscose/Polyester/Silk/Polyamide.")과 `related`는 색상·패턴·소재 정보를 비정형 텍스트로 담고 있다. 이를 임베딩하면 "이런 옷과 어울리는 색상·소재 조합"을 검색하는 RAG 지식베이스의 원천 문서가 된다.

### 카테고리 표준화 기준표

`categories.csv`의 `semantic_category`는 우리 서비스의 옷장 카테고리(상의/하의/아우터/신발/가방/액세서리 등)와 맞춰볼 기준표로 쓸 수 있다. 다만 주얼리/스포츠웨어의 세부 카테고리는 우리 범위보다 세분화돼 있어 별도 매핑 작업이 필요하다.

### disjoint / nondisjoint 이원화 전략

- `nondisjoint`: train.parquet가 1.79GB로 가장 풍부, 학습 볼륨 확보용
- `disjoint`: 아이템 단위로 분리되어 일반화 검증용 (동일 아이템이 train/val/test에 등장하지 않음)

추천 모델은 nondisjoint로 학습하고 disjoint로 최종 평가하는 패턴이 효과적이다.

## 10. 초보자용 최소 분석 루틴

처음에는 이것만 하면 된다.

1. `nondisjoint/train.json`을 pandas로 읽어 행 개수와 한 줄 샘플을 본다.
2. 그 한 줄의 `items[].item_id` 셋을 `polyvore_item_metadata.json`에서 조회해 텍스트 메타를 본다.
3. 같은 item_id의 `category_id`를 `categories.csv`와 매핑해 `semantic_category`를 붙인다.
4. `fill_in_blank_*.json`에서 같은 set_id로 시작하는 question을 찾아 어떤 답이 정답 슬롯에 들어갔는지 본다.
5. `compatibility_*.txt`에서 같은 set_id의 토큰들이 등장하는 라인을 보고 라벨(0/1)을 확인한다.
6. `polyvore_outfit_titles.json`에서 같은 set_id의 자연어 제목(TPO)까지 붙이면 끝.

```text
nondisjoint/train.json
→ set_id 1개 선택
→ items[].item_id 메모
→ polyvore_item_metadata.json에서 텍스트 메타 조회
→ categories.csv에서 semantic_category 매핑
→ fill_in_blank_*.json에서 정답 슬롯 확인
→ compatibility_*.txt에서 라벨 확인
→ polyvore_outfit_titles.json에서 TPO 자연어 라벨 확인
```

처음부터 parquet의 이미지 바이트까지 다루려면 무겁다. 위 6단계까지만 해도 데이터 본질은 충분히 잡힌다.

## 11. 규모와 주의사항

`aws s3 ls --recursive --summarize`로 확인한 S3 전체:

- 오브젝트 39개, 총 약 **4.30GB**

용량 분포:

- `polyvore_item_metadata.json`: 105MB. 261k 아이템의 텍스트 메타 — 단일 다운로드 가능
- `polyvore_outfit_titles.json`: 6.6MB. 68k 코디의 자연어 제목
- `categories.csv`: 4.8KB
- `data/{disjoint,nondisjoint}/*.parquet`: 6개, 합쳐 약 **3.85GB**
- `{disjoint,nondisjoint}/{train,valid,test}.json`: 6개, 각 1~32MB
- `{disjoint,nondisjoint}/compatibility_*.txt`, `fill_in_blank_*.json`: 6+6개, 각 0.5~9MB
- `typespaces.p`: 1.4KB
- `maryland_polyvore_hardneg/`: 약 23MB

주의사항:

- **disjoint / nondisjoint 폴더가 두 세트 존재** — `data/*`는 이미지 parquet, 최상위 `disjoint, nondisjoint/`는 라벨·구조. 혼동 주의.
- **`polyvore_item_metadata.json`은 한 덩어리 JSON 한 줄짜리 dict** — `json.load()` 시 메모리 사용량이 크다. 스트리밍 파서(ijson)나 SQLite로 한 번에 적재하는 방식 권장.
- **parquet 스키마는 미확인** — 이번 분석 단계에서는 컬럼명·이미지 포맷(JPEG bytes 등)을 직접 파싱하지 않았다. 실제 활용 시점에 `pandas.read_parquet` 또는 `datasets.load_dataset`으로 첫 행을 찍어 스키마를 확정해야 한다.
- **`catgeories` 필드는 원본 오탈자 그대로** — `categories.csv`의 키와 매핑할 때 오타에 주의.
- **빈 텍스트 메타** — 다수 아이템이 `description`/`title`/`related`가 빈 문자열이므로, 텍스트 기반 필터링·검색 시 빈 값 처리가 필요하다.
- **`title` 빈 코디** — `polyvore_outfit_titles.json`의 `title`이 비어 있는 코디가 약 15% 존재, TPO 룰 적용 시 제외 필요.
- **train/val/test split은 disjoint / nondisjoint 두 가지 의미** — disjoint는 아이템 단위 분리(엄격), nondisjoint는 outfit 단위 분리(쉬운 평가). 일관성 있게 한 가지를 골라 쓰는 것이 안전.

## 12. 이번에 내려받은 샘플

작업 폴더:

```text
C:\Users\Playdata\AppData\Local\Temp
```

파일:

```text
05_categories.csv                  # 4,910 bytes
05_titles.json                     # 6,970,887 bytes
```

(`polyvore_item_metadata.json` 105MB와 parquet들은 이번 세션에서는 내려받지 않았다. 분석 필요 시 다음 세션에서 받는 것을 권장.)

이 두 파일만으로도 다음을 확인했다:

- `categories.csv`: `semantic_category` 11종 확인, 카테고리 ID 중복 행 관찰
- `polyvore_outfit_titles.json` 60건 샘플 추출: TPO 자연어 라벨 패턴, 빈 title 비율 추정

## 13. 출처 및 확인 근거

출처:

- S3: `s3://skn28-cozy/05_huggingface_polyvore_outfits/`
- 원 논문: Vasileva et al., "Learning Type-Aware Embeddings for Fashion Compatibility", ECCV 2018
- Confluence: https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/8749183
- 시각화 아티팩트: https://claude.ai/code/artifact/10f3a450-2927-4a3e-849d-93380b0446cd (구 버전)
- 시각화 아티팩트 (통일 디자인): `data/05_polyvore_outfits/artifact.html` — 11번 아티팩트 CSS로 재작성 (2026-07-09)

확인 근거:

- `aws s3 ls`, `aws s3 ls --recursive --summarize`로 폴더 구조와 객체 39개·약 4.30GB 실측.
- `categories.csv`를 직접 내려받아 `category_id`, 카테고리명, `semantic_category` 3컬럼 구조 확인.
- `polyvore_outfit_titles.json`을 내려받아 `set_id → {url_name, title}` 구조와 빈 title 비율(약 15%) 확인.
- 기존 README.md 분석 내용을 토대로 `{disjoint,nondisjoint}/train.json`의 `set_id → items:[{item_id, index}]` 구조 및 `compatibility_*.txt`의 `1 set_id_1 set_id_2 ...` 라벨 포맷 확인.
- `polyvore_item_metadata.json`의 레코드 예시(`183179503`의 trousers)는 기존 분석에서 발췌한 것을 그대로 인용.
