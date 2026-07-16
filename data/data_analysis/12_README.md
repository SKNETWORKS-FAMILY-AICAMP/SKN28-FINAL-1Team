# 12. ETRI FASCODE(Fashion-How 2024) 데이터 보는 법

## 1. 이 데이터는 무엇인가

`s3://skn28-cozy/12.한국전자통신연구원_FASCODE/`는 ETRI(한국전자통신연구원)가 주최한 AI 경진대회 "Fashion-How 2024 (Season 5)"의 공식 데이터셋이다. **4개의 서브태스크(subtask 1·2·3·4)**로 나뉘어 있고, **subtask 3·4가 "옷을 추천해주는 AI(코디봇)"와 사용자가 실제로 나눈 대화형 패션 코디네이션 로그**로서 본 데이터셋의 핵심이다.

핵심 자산:

- **subtask3·4**: 코디봇↔사용자 대화 로그(`ddata.txt`), 아이템 코드별 메타데이터(`mdata.txt`), 평가용 dev 셋(`cl_eval_*.dev`), 아이템 사진(`img_jpg/`), 사진별 사전추출 특징벡터(`img_feats/`).
- **subtask1·2**: "옷 사진 → 속성 라벨" 이미지 분류용. `Fashion-How24_sub{1,2}_train.csv` + 카테고리별 폴더의 실제 제품 사진.
- 모든 텍스트 파일이 **EUC-KR(CP949)**, 일부 서브태스크는 **인코딩 수정본**이 별도 파일로 존재.

우리 프로젝트의 "대화형 추천 + TPO 기반 룰 + 이미지-텍스트 멀티모달" 모든 축과 직접 맞물리는 자료다.

## 2. S3 위치

기준 버킷:

```powershell
aws s3 ls s3://skn28-cozy/
```

12번 데이터 최상위:

```powershell
aws s3 ls s3://skn28-cozy/12.한국전자통신연구원_FASCODE/
```

각 서브태스크 위치:

```text
s3://skn28-cozy/12.한국전자통신연구원_FASCODE/Fashion-How_2024_subtask1-001/
s3://skn28-cozy/12.한국전자통신연구원_FASCODE/Fashion-How_2024_subtask2-003/
s3://skn28-cozy/12.한국전자통신연구원_FASCODE/Fashion-How_2024_subtask3/
s3://skn28-cozy/12.한국전자통신연구원_FASCODE/Fashion-How_2024_subtask4/
```

인코딩 수정본(subtask4 원본의 깨진 EUC-KR을 고친 별도 파일):

```text
s3://skn28-cozy/12.한국전자통신연구원_FASCODE/(sub4_encoding_fix)ddata.txt.2023.08 (1).29
```

## 3. 전체 폴더 구조

`aws s3 ls --recursive --summarize` 결과: **총 55,087 객체, 약 6.89GB**.

```text
12.한국전자통신연구원_FASCODE/
├── Fashion-How_2024_subtask1-001/
├── Fashion-How_2024_subtask2-003/
├── Fashion-How_2024_subtask3/
├── Fashion-How_2024_subtask4/
└── (sub4_encoding_fix)ddata.txt.2023.08 (1).29   (18.4MB, 최상위에 인코딩 수정본 별도)
```

각 서브태스크 폴더 안의 공통 골격:

```text
Fashion-How_2024_subtaskN/
├── ETRI_Fashion-How_Season_5_안내서.pdf                # 4개 서브태스크 모두 동일(82,340 bytes)
├── ETRI_Fashion-How_Season_5_베이스라인_설명자료N.pdf
├── 한_파일명_Baseline모델_task.ipynb_확인               # 0 bytes 더미 파일
├── Baseline_Model/                                     # 대회 측 베이스라인 코드
└── Dataset/ 또는 data/                                  # 실제 학습·평가 데이터
```

`한_파일명_..._확인` 류의 **0바이트 파일**은 4개 서브태스크 모두에서 반복적으로 나타나며, 다운로드해도 내용이 없으므로 무시.

### 서브태스크별 data/ 안의 파일 구성

`subtask3/data/` 발췌:

```text
subtask3/data/
├── task1.ddata.txt ~ task6.ddata.txt                # 태스크 1~6별 원본 대화 로그
├── task1.ddata.wst.txt ~ task6.ddata.wst.txt         # 형태소 분석(띄어쓰기) 버전
├── mdata.txt.2023.08.23                               # 아이템 속성 메타데이터
├── mdata.wst.txt.2023.08.23                           # 메타 형태소 분석 버전
├── cl_eval_task1.dev ~ cl_eval_task6.dev              # 평가용 대화+정답 후보(dev)
├── cl_eval_task*.wst.dev                              # 위의 형태소 분석 버전
├── img_jpg/                                           # 아이템 코드별 제품 사진 (subtask3: 6,380장, 559MB)
└── img_feats/                                         # 아이템 코드별 .npy 특징벡터 (≈ 32,896 bytes/파일)
```

`subtask4/Fashion-How_2024_subtask4/data/`는 동일 구조로, 대화는 `ddata.txt.2023.08.29`(14.4MB) 하나로 통합, 이미지는 7,461장(640MB). **subtask4 = subtask3의 확장/통합판**으로 판단.

### subtask1, subtask2 안

```text
subtask1/Dataset/
├── Fashion-How24_sub1_train.csv                       # 523KB
├── train/ val/
│   └── 2BLOUSE 2019/ 2CARDIGON 2019/ 2COAT 2019/ ...  # 카테고리별 제품 사진

subtask2/Dataset/
├── Fashion-How24_sub2_train.csv                       # 478KB
├── train/ val/
│   └── ...
```

## 4. 폴더별 의미

### subtask1·2 — 이미지 속성 분류 데이터 (대화 아님)

`Fashion-How24_sub1_train.csv` 헤더:

```
image_name,BBox_xmin,BBox_ymin,BBox_xmax,BBox_ymax,Daily,Gender,Embellishment
1209/BO00001-1.jpg,45,197,313,393,4,4,0
```

- `image_name`: 카테고리 폴더 안의 사진 파일 경로
- `BBox_*`: 사진 내 옷 영역 바운딩박스
- `Daily`, `Gender`, `Embellishment`: 일상성, 성별, 장식 유무의 **정수 코드 라벨**

subtask2도 같은 구조이며 라벨만 `Color`(색상 클래스 정수)로 바뀐다.

### subtask3·4 — 대화형 패션 코디네이션 데이터 (본 데이터)

**① `*.ddata.txt`** — 대화 로그

탭(TAB) 구분 4컬럼:

```
턴번호(세션마다 0부터 리셋) \t 발화자태그(<CO>/<US>/<AC>) \t 발화텍스트 \t 대화행위(Dialogue Act) 태그(;로 복수 가능)
```

- `<CO>` = 코디봇(AI) 발화
- `<US>` = 사용자 발화
- `<AC>` = 시스템의 추천 행동(Action). 텍스트가 아니라 **그 시점에 추천된 아이템 코드**가 들어감(예: `CD-032 BL-216 SK-259 SE-175` = 카디건·블라우스·스커트·신발 조합)

발췌(`task1.ddata.txt`, EUC-KR → UTF-8):

```
0   <CO>   안녕하세요. 코디봇입니다. 무엇을 도와드릴까요?                            INTRO
1   <US>   최근에 열린 꽃축제에 가려고 하는데, 그때 입을 스커트를 포함한 의상 추천해주세요.
2   <CO>   원하시는 스커트 기장이 있으신가요?                                          ASK_LENGTH
3   <US>   중간 기장으로 보여주세요.
4   <CO>   겉옷이 포함된 코디로 추천해드릴까요?                                       SUGGEST_TYPE
5   <US>   얇은 가디건으로 추천 부탁드려요.
6   <CO>   네. 반영하여 추천드리겠습니다. 잠시만 기다려주세요.                          ETC;WAIT
7   <AC>   CD-032 BL-216 SK-259 SE-175
8   <CO>   아이보리 색상의 머메이드형 스커트와 부드러운 소재의 베이지 색상 가디건을 …   EXP_RES_COLOR;EXP_RES_ETC;EXP_RES_MATERIAL;CONFIRM_SATISFACTION
9   <US>   상의와 신발은 캐쥬얼한 디자인이 마음에 들어요. …                            USER_SUCCESS_PART
10  <CO>   네. 반영하여 원하시는 색상이 있나요?                                       ASK_COLOR
11  <US>   어두운 계열로 보여주세요.
…
25  <CO>   코디봇을 이용해주셔서 감사합니다.                                          CLOSING
```

대화행위 태그 20여 종. 실제 관찰된 것: `INTRO`, `ASK_LENGTH`/`ASK_COLOR`, `SUGGEST_TYPE`, `WAIT`, `ETC`, `EXP_RES_COLOR`/`MATERIAL`/`PATTERN`/`WIDTH`/`LENGTH`/`DESCRIPTION`/`ETC`, `CONFIRM_SATISFACTION`/`CONFIRM_REPLY`/`CONFIRM_SHOW`, `USER_SUCCESS`/`USER_SUCCESS_PART`, `SUCCESS`, `CLOSING`. 사용자 발화는 대부분 자유발화(태그 없음), `USER_SUCCESS(_PART)`만 예외적으로 붙음.

**② `*.ddata.wst.txt`** — 형태소 분석 버전

```
0  <CO>  안녕_하 세 요 코디 봇 입 니다 무엇 을 도와 드릴_까 요   INTRO
```

`wst` = word-segmented text. 형태소 분석을 거친 결과로, NLU 모델(의도 분류기) 학습 시 토큰화 전처리를 대회 측이 미리 해 둔 데이터.

**③ `mdata.txt`** — 아이템(옷) 속성 메타데이터

탭 구분 5컬럼: `아이템코드 \t 슬롯(T/B/O/S 등 추정) \t 카테고리코드 \t 속성유형(F/M/C/E) \t 속성설명텍스트`. 아이템 하나에 여러 줄이 반복.

발췌(EUC-KR → UTF-8):

```
BL-001  T  BL  F  상의 스트레이트 실루엣
BL-001  T  BL  F  상의 허리 길이
BL-001  T  BL  M  면
BL-001  T  BL  M  평직물
BL-001  T  BL  C  스카이 블루 페일 톤 / 단색
BL-001  T  BL  E  전시회
BL-001  T  BL  E  여성스러운
```

속성유형 4종:

- `F` = Fabric/Form (실루엣, 여밈, 칼라, 소매 형태 등 디자인 요소)
- `M` = Material (소재: 면, 평직물, 뻣뻣한 소재 등)
- `C` = Color (색상: "스카이 블루 페일 톤 / 단색")
- `E` = Emotion/스타일 감성 ("여성스러운", "발랄한", "바캉스룩" 등)

**④ `img_jpg/`** — 아이템 코드별 제품 사진

파일명은 mdata·ddata의 아이템 코드와 동일 (`BL-001.jpg`, `CD-220.jpg` 등). subtask3 6,380장(559MB), subtask4 7,461장(640MB).

**⑤ `img_feats/`** — 사진별 사전추출 특징벡터

`.npy` 파일이 `img_jpg/`와 **대부분** 1:1로 묶여 있지만 정확히 일치하지는 않음 (subtask3 기준 img_jpg 6,380 vs img_feats 6,385로 5개 차이). 약 32,896 bytes/파일 → 고정 차원 임베딩 벡터. 카테고리 코드 접두어: `BL`(블라우스), `CD`(가디건), `SK`(스커트), `SE`(신발), `CT`(코트), `SW`(스웨터/니트), `JP`/`KN`/`PT`/`VT`/`JK` 등.

**⑥ `cl_eval_task*.dev`** — 평가용 대화+정답 후보

```
; 0
CO  안녕하세요. …
US  꽃축제에 어울릴만한 코디를 추천해주세요
CO  가을과 잘 어울리는 따뜻한 소재의 치마가 포함된 코디를 추천해드릴까요?
US  치마 좋아요. 하체비만이라서 치마가 길었으면 좋겠어요
CO  상의는 축제에서 활동하기 편하도록 넉넉한 핏으로 추천해드릴까요?
US  좋아요.
R1  JP-345 KN-406 SK-338 SE-194
R2  JP-345 KN-396 SK-338 SE-194
R3  JP-345 KN-406 SK-383 SE-194
```

대화 맥락 + 후보 조합 3개(R1/R2/R3) 랭킹 라벨.

## 5. 가장 중요한 파일: ddata.txt

`task1.ddata.txt`부터 `task6.ddata.txt`까지 6개가 본 데이터의 중심. (subtask4는 이 6개가 통합된 단일 `ddata.txt.2023.08.29`.)

왜 ddata가 가장 중요한가:

- **추천 행동의 정답 로그**: 매 턴 `<AC>`로 그 시점 추천된 아이템 코드가 박혀 있어, "사용자 요구 → 봇 응답 → 추천된 아이템 시퀀스"가 한 파일 안에서 시간순으로 재생된다.
- **대화 상태 전이(state transition) 라벨**: 20여 종의 Dialogue Act 태그(`INTRO`, `ASK_*`, `EXP_RES_*`, `CONFIRM_*`, `USER_SUCCESS(_PART)`, `SUCCESS`, `CLOSING`)가 실제 대화에서 어떻게 순차적으로 펼쳐지는지 그대로 들어 있다.
- **추천 근거 문장 패턴**: `EXP_RES_COLOR`, `EXP_RES_MATERIAL`, `EXP_RES_LENGTH`, `EXP_RES_PATTERN` 같은 "왜 이 옷인지"를 풀어 설명하는 발화 패턴이 대량 존재 → LLM의 추천 이유 문장 학습 few-shot에 직접 사용 가능.

mdata·평가지·이미지·특징벡터는 모두 이 ddata의 보조·평가 자산이다.

## 6. 샘플 하나를 보는 순서

`subtask3/data/task1.ddata.txt`의 첫 세션을 그대로 따라가 본다.

1. 파일을 EUC-KR로 연다.
2. `0 <CO> … INTRO` 한 줄을 찾는다 — 세션 시작점.
3. 1·3·5번처럼 `<US>` 줄에서 사용자 요청/응답을 따라간다.
4. 2·4·6·7번이 사용자에게 질문하는 흐름(`ASK_LENGTH`, `SUGGEST_TYPE`)임을 확인.
5. 7번 `<AC> CD-032 BL-216 SK-259 SE-175` — 이 한 줄이 **이번 턴의 추천 결과**.
6. mdata.txt.2023.08.23에서 CD-032, BL-216, SK-259, SE-175의 F/M/C/E 속성을 본다.
7. 8번 `<CO>` 의 `EXP_RES_COLOR;EXP_RES_ETC;EXP_RES_MATERIAL;CONFIRM_SATISFACTION` — 추천 이유를 색상·재질·디테일 축으로 풀어 설명 + 만족도 확인.
8. 9번 `<US>` `USER_SUCCESS_PART` — 부분 만족. 다른 슬롯에 대해 추가 요청.
9. 10·11번 `ASK_COLOR` 다시 색상 질문 흐름.
10. 13번 `<AC> CD-220 SK-418` — 부분 수정된 두 번째 추천.
11. 16~19번 `USER_SUCCESS_PART` → `CONFIRM_REPLY` → 또 다른 후보(`SK-287`) 단일 추천.
12. 21번 `<AC> CD-220 BL-216 SK-287 SE-175` — 최종 코디.
13. 22번 `<CO> CONFIRM_SHOW;CONFIRM_SATISFACTION` — 최종 코디 제시 + 만족도 재확인.
14. 23~25번 `SUCCESS` → `CLOSING` — 세션 종료.

이 14단계로 한 세션의 흐름이 잡힌다.

## 7. SQL로 보면 쉬운 이유

```sql
-- 아이템 마스터 + 속성
CREATE TABLE items (
    item_id        TEXT,
    slot_code      TEXT,    -- 'T' | 'B' | 'O' | 'S' (전신 일부 추정)
    category_code  TEXT,    -- 'BL', 'CD' …
    PRIMARY KEY (item_id)
);
CREATE TABLE item_attributes (
    item_id   TEXT,
    attr_type TEXT,         -- 'F' | 'M' | 'C' | 'E'
    attr_text TEXT
);

-- 세션
CREATE TABLE sessions (
    session_id     INTEGER PRIMARY KEY,
    subtask        TEXT,    -- 'sub3' | 'sub4' | 'sub1' | 'sub2'
    source_file    TEXT,    -- 'task1.ddata.txt' 등
    n_turns        INTEGER
);

-- 한 세션의 한 턴
CREATE TABLE turns (
    session_id   INTEGER,
    turn_no      INTEGER,
    speaker      TEXT,       -- '<CO>' | '<US>' | '<AC>'
    utterance    TEXT,
    dialogue_act TEXT,       -- 'EXP_RES_COLOR;EXP_RES_MATERIAL' 등
    PRIMARY KEY (session_id, turn_no)
);

-- 한 시점의 추천 아이템(여러 슬롯 동시 가능)
CREATE TABLE turn_recommendations (
    session_id  INTEGER,
    turn_no     INTEGER,
    item_id     TEXT,
    is_partial  INTEGER       -- 0=중간, 1=최종 코디
);

-- 평가용 dev: 후보 랭킹
CREATE TABLE eval_rank (
    eval_index  INTEGER,
    rank        INTEGER,       -- 1 | 2 | 3
    set_tokens  TEXT           -- 'JP-345 KN-406 SK-338 SE-194'
);

-- subtask1·2 이미지 속성 라벨
CREATE TABLE image_attribute_labels (
    subtask     INTEGER,       -- 1 | 2
    image_name  TEXT,
    bbox_xmin   INTEGER,
    bbox_ymin   INTEGER,
    bbox_xmax   INTEGER,
    bbox_ymax   INTEGER,
    class_id    INTEGER,       -- subtask1: Daily/Gender/Embellishment 각각 별도 행
    PRIMARY KEY (subtask, image_name)
);
```

자주 쓰일 SQL 예시.

`EXP_RES_COLOR`가 붙은 코디봇 발화 비율:

```sql
SELECT
  SUM(CASE WHEN dialogue_act LIKE '%EXP_RES_COLOR%'     THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS p_color,
  SUM(CASE WHEN dialogue_act LIKE '%EXP_RES_MATERIAL%'  THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS p_mat,
  SUM(CASE WHEN dialogue_act LIKE '%EXP_RES_LENGTH%'    THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS p_len
FROM turns WHERE speaker = '<CO>';
```

특정 슬롯(상의/BL)이 추천될 때 자주 동반된 슬롯:

```sql
WITH ac_per_session AS (
    SELECT DISTINCT session_id, turn_no
    FROM turn_recommendations r
    JOIN items i ON r.item_id = i.item_id
    WHERE i.category_code = 'BL'
)
SELECT r2.item_id, COUNT(*) AS cnt
FROM ac_per_session a
JOIN turn_recommendations r2
     ON a.session_id = r2.session_id AND a.turn_no = r2.turn_no
JOIN items i2 ON r2.item_id = i2.item_id
WHERE i2.category_code <> 'BL'
GROUP BY r2.item_id
ORDER BY cnt DESC LIMIT 20;
```

`E` 태그 안의 TPO 키워드("오피스", "데이트") 분포:

```sql
SELECT attr_text, COUNT(*) AS cnt
FROM item_attributes
WHERE attr_type = 'E' AND attr_text LIKE '%오피스%'
GROUP BY attr_text
ORDER BY cnt DESC LIMIT 20;
```

## 8. 이 데이터로 알 수 있는 것

이 데이터로 바로 알 수 있는 것:

- 코디봇이 **어떤 순서로 사용자에게 질문**하는지 (`ASK_LENGTH` → `ASK_COLOR` → `SUGGEST_TYPE` …)
- 추천 이유를 풀 때 **어떤 슬롯(색상·소재·길이·패턴·폭·상황)**이 자주 등장하는지
- 추천 결과(`<AC>`)가 **카테고리 슬롯별로 어떻게 묶이는지** (상의/하의/아우터/신발 동시 등장 빈도)
- `IMG_FEATS`가 **고정 차원 임베딩 벡터**(≈ 32,896 bytes/파일, 차원 추정 ≈ 1,024 float32)이라는 점에서, 대회 측이 사전 학습된 CNN으로 추출해 둔 특징을 그대로 쓸 수 있음
- subtask1·2의 **`Daily`/`Gender`/`Embellishment`/`Color` 클래스 분포** — 사용자 옷장 사진 자동 태깅 모델의 학습 데이터로 사용 가능
- 평가셋의 **top-3 후보 분포** — 모델이 헷갈리는 조합 패턴

조금 더 분석하면 알 수 있는 것:

- 한 세션 안에서 `USER_SUCCESS_PART` (부분 만족)이 **평균 몇 번** 일어나는지
- 추천 거절 후 코디봇이 **평균 몇 번 재추천**하는지
- 같은 옷(`item_id`)이 다른 세션들에서 **얼마나 자주 추천되는지**(인기도 측면)
- `E` 태그의 TPO 키워드를 RAG로 임베딩해 사용자 발화("소개팅룩")와 매칭했을 때의 top-10

## 9. 추천 시스템에 활용하는 방법

### 대화 흐름(state machine) few-shot / 설계 근거

`INTRO → ASK_LENGTH/COLOR/SITUATION → SUGGEST_TYPE → WAIT → <AC> → EXP_RES_COLOR/MATERIAL/LENGTH/PATTERN/… → CONFIRM_SATISFACTION → USER_SUCCESS(_PART) → CONFIRM_REPLY → 재추천 → CONFIRM_SHOW → SUCCESS → CLOSING` 순서가 정답 골격. 우리 AI 캐릭터의 "인사 → 조건 질문 → 대기 → 추천 + 근거 → 만족도 확인 → 부분 수정 → 재추천 → 최종 확정 → 마무리"에 그대로 이식.

### 슬롯(속성) 설계 근거

`ASK_LENGTH`, `ASK_COLOR`, `EXP_RES_PATTERN`, `EXP_RES_WIDTH` 등 태그와 mdata의 F/M/C/E 4축 = "옷 추천 대화에서 결정적으로 오가는 정보 = 기장/색상/소재/핏/실루엣/감성(TPO)"이라는 실데이터 근거. 우리 시스템의 슬롯 정의·질문 분기로 그대로 사용 가능.

### 추천 근거 텍스트 생성(RAG) 소스

mdata의 F/M/C/E 서술("상단 스트레이트 실루엣", "부드러운 소재", "스카이 블루 페일 톤 / 단색", "여성스러운")은 우리 LLM이 추천 문구를 생성할 때 템플릿·스타일 참고 자료로 그대로 사용 가능. 우리 자체 상품 데이터에 같은 F/M/C/E 스타일 태그를 붙여두면 이 데이터의 문장 패턴을 few-shot에 직접 넣을 수 있다.

### 추천 랭킹/평가 벤치마크 설계 참고

`cl_eval_task*.dev`의 "대화 맥락 + 후보 조합 3개(R1/R2/R3)" 구조 = "주어진 대화 맥락에서 정답에 가까운 조합을 추천하는가" 평가 포맷 참고. 우리 자체 평가셋을 만들 때 같은 포맷(`R1/R2/R3` + 정답 정의)으로 변형 가능.

### 이미지 임베딩 / 시각 유사도 검색 프로토타이핑

`img_jpg/` + `img_feats/`(사전 추출 임베딩)가 아이템 코드로 **대부분** 1:1로 묶여 있어, "이미지 → 임베딩 → 유사 아이템 검색" 시각 추천 모듈의 **파이프라인 프로토타입**을 우리 데이터 없이도 먼저 검증 가능. 단, 정확히 1:1은 아니어서(subtask3은 img_jpg 6,380 vs img_feats 6,385로 5개 차이) 매칭 시 코드셋 차집합 확인이 필요. 또한 사용자 "옷장 사진" 도메인과 스튜디오 제품샷의 차이가 있어 그대로 파인튜닝 소스는 비추, 검증·프로토타입용으로 적합.

### subtask1·2 → 옷장 사진 자동 태깅 모듈 학습

`Daily`(일상성)/`Gender`(성별)/`Embellishment`(장식)/`Color`(색상) 라벨은 사용자가 올린 옷 사진의 속성을 자동 태깅하는 모듈의 학습·검증 데이터로 그대로 활용 가능.

### 주의사항

- 모든 txt 파일은 **EUC-KR(CP949)** + (있다면) 형태소 결합 `_` 토큰. UTF-8 열면 전부 깨진다.
- `(sub4_encoding_fix)ddata.txt.2023.08.29`는 인코딩 수정본으로, 원본 `ddata.txt.2023.08.29`이 깨져 보이는 경우 이걸 먼저 쓰는 것이 안전.
- 0바이트 더미 파일(`한_파일명_*_확인`)은 무시.
- subtask4 폴더는 `Fashion-How_2024_subtask4/Fashion-How_2024_subtask4/...`처럼 한 겹 더 중첩돼 있어 상위 폴더만 보고 "비어있다"고 오판하지 말 것.

## 10. 초보자용 최소 분석 루틴

처음에는 이것만 하면 된다.

1. `subtask3/data/task1.ddata.txt`를 `encoding='cp949'`으로 연다.
2. 첫 세션의 ~25턴을 한 화면에 본다.
3. `<CO>`/`<US>`/`<AC>` 3종 화자 태그 + `INTRO/CLOSING` 흐름을 눈에 익힌다.
4. `<AC>` 행의 아이템 코드를 메모해 두고, 같은 코드를 `mdata.txt.2023.08.23`에서 조회해 F/M/C/E 속성을 본다.
5. `img_jpg/{코드}.jpg`가 실제로 존재하는지 한 장만 받아 확인한다(`aws s3 ls`로도 확인 가능).
6. `cl_eval_task1.dev`의 첫 세션(`; 0`)을 읽고 R1/R2/R3 후보가 어떻게 다른지 본다.

```text
task1.ddata.txt → 한 세션 25턴
→ <AC> 줄의 아이템 코드 메모
→ mdata에서 F/M/C/E 속성 조회
→ img_jpg에서 실제 사진 확인
→ cl_eval_task1.dev의 R1/R2/R3 비교
```

이 6단계면 subtask3의 본질이 잡힌다.

## 11. 규모와 주의사항

S3 실측치:

| 항목 | 값 |
|---|---|
| 전체 객체 | 55,087 |
| 전체 용량 | ≈ 6.89GB |
| 서브태스크 폴더 수 | 4 (subtask1~4) |
| 최상위 단일 파일 | `(sub4_encoding_fix)ddata.txt.2023.08.29` 18.4MB |
| subtask3 이미지 (img_jpg) | 6,380장 / 559MB |
| subtask3 특징벡터 (img_feats) | 6,385 .npy (이미지보다 5개 많음) |
| subtask4 이미지 | 7,461장 / 640MB |
| subtask4 통합 ddata | 14.4MB |
| 0바이트 더미 파일 | 4개 서브태스크 모두 (각 1개) |

용량 추정치는 `--summarize` 표본 기반이며 일부는 미확인. 사전추출 임베딩 차원은 파일 크기(32,896 bytes)로부터 약 4,096 float32 또는 8,192 float16 정도로 추정 가능하나 정확한 수는 실제 로드 후 확인 필요.

주의사항:

- **인코딩**: 모든 txt는 EUC-KR(CP949). (sub4_encoding_fix) 파일이 별도로 존재하는 이유가 이 인코딩 깨짐 보정. UTF-8 열면 전부 깨진다.
- **0바이트 더미 파일**: `한_파일명_Baseline모델_task.ipynb_확인` 류는 실데이터 아님.
- **subtask4 중첩 폴더**: `Fashion-How_2024_subtask4/Fashion-How_2024_subtask4/data/...` 처럼 한 번 더 들어가 있어 경로 주의.
- **빈 PDF 더미 가능성**: 일부 0바이트 파일 외 추가 더미가 섞여 있을 가능성. 다운로드 후 `file`/`head`로 확인 권장.
- **img_feats 차원**: 정확한 차원은 본 단계에서 미확인. `numpy.load` 후 `.shape` 확인 필요.
- **img_feats ≠ img_jpg 수**: subtask3에서 img_feats=6,385장, img_jpg=6,380장으로 **5개 차이**. 일부 아이템은 이미지 없이 특징벡터만 존재하거나(또는 그 반대)하는 케이스. 두 폴더 매칭이 1:1이 아니므로 사전에 코드셋 차집합을 확인해야 함.
- **트렌드 시점**: 2024년 ETRI Fashion-How 5기. 11번(2020)보다는 최신이지만 절대 최신 트렌드는 아님.

## 12. 이번에 내려받은 샘플

작업 폴더:

```text
C:\Users\Playdata\AppData\Local\Temp
```

파일:

```text
12_subtask3_ddata.txt        # 1,755,008 bytes (task1.ddata.txt) — 모자이크/깨진 표시지만 원문 EUC-KR
12_subtask3_mdata.txt        # 4,313,600 bytes (mdata.txt.2023.08.23) — 동일
```

표시된 문자가 깨진 것처럼 보이지만 이는 다운로드 직후 UTF-8 뷰로 본 결과이며, 실제 인코딩은 EUC-KR이다.

이 두 파일로 다음을 확인했다:

- ddata의 첫 세션 25~30턴 발췌
- 같은 세션의 `<AC> CD-032 BL-216 SK-259 SE-175` 추천 행
- `EXP_RES_COLOR;EXP_RES_MATERIAL;CONFIRM_SATISFACTION` 결합 태그 패턴
- USER_SUCCESS_PART 패턴
- mdata의 BL-001/002 F 속성, M 속성(면/평직물), C 속성(스카이 블루), E 속성(여성스러운/전시회 등)
- `BL`/`JK`/`CT` 등 카테고리 코드 접두어 패턴

`img_jpg/`의 사진이나 `img_feats/`의 npy, `cl_eval_*.dev`는 이번 세션에서 따로 받지 않았다.

## 13. 출처 및 확인 근거

출처:

- 시각화 아티팩트: https://claude.ai/code/artifact/447db2d6-bba9-469e-80a2-ea9cf0a31130 (구 버전)
- 시각화 아티팩트 (통일 디자인): `data/12_FASCODE/artifact.html` — 11번 아티팩트 CSS로 재작성 (2026-07-09)
- S3: `s3://skn28-cozy/12.한국전자통신연구원_FASCODE/`
- 제공: ETRI(한국전자통신연구원), AI 경진대회 "Fashion-How 2024 (Season 5)"
- 라이선스: S3 metadata 미확인, ETRI 대회 운영 정책 적용 가정
- Confluence: 없음(팀 분석 페이지 미작성 상태였음)

확인 근거:

- `aws s3 ls --recursive --summarize`로 55,087 객체, ≈ 6.89GB 실측.
- `aws s3 ls`로 4개 서브태스크 폴더 + 최상위 단일 파일 18.4MB 확인.
- `Fashion-How_2024_subtask3/data/task1.ddata.txt`를 직접 내려받아 첫 세션 25~30턴 발췌, `<CO>/<US>/<AC>` 3종 화자 확인.
- `mdata.txt.2023.08.23` 내려받아 BL-001의 F/M/C/E 속성 14건, BL-002의 시작 9건 발췌.
- 4컬럼(턴번호/화자/발화/대화행위) 구조와 `<AC>`가 텍스트가 아닌 아이템 코드인 점 확인.
- txt 파일들이 UTF-8로 열리지 않고 EUC-KR 디코딩이 필요함을 메타/매직으로 확인.
- 0바이트 파일 4개(각 서브태스크에 1개씩) 존재 확인.
- subtask 폴더 안에 `Dataset/` 또는 `data/`가 둘 다 또는 한쪽만 있는 점은 실 ls 결과로 확인.
