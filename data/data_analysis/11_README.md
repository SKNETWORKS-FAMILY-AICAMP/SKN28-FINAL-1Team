# 11. ETRI PoC 패션 코디 데이터셋 보는 법

## 1. 이 데이터는 무엇인가

`s3://skn28-cozy/11. 한국전자통신연구원_자율성장 인공지능 기술검증(PoC)을 위한 패션 코디 데이터셋/`은 ETRI(한국전자통신연구원) PoC 결과물로, "코디봇"이라는 가상의 상담원이 사용자와 나눈 **패션 코디 추천 대화 코퍼스**와 그 대화에 등장한 **의류 아이템 이미지**, 그리고 각 아이템의 **디자인/소재/색상/감성(스타일·TPO) 속성**을 한 묶음으로 정리한 데이터셋이다.

핵심 자산:

- **대화 코퍼스**: 7,236개 세션, 평균 21턴. 사용자가 자연어로 옷차림을 요청하면 봇이 되묻고 상의/하의/아우터/신발을 조합해 추천 → 사용자가 만족·불만족 반응을 표현하는 **상담형 추천 대화 흐름** 자체가 라벨링되어 있다.
- **아이템 이미지**: 13개 카테고리(BL/CD/CT/JK/JP/KN/OP/PT/SE/SH/SK/SW/VT)에 걸쳐 3,351장.
- **아이템 메타**: 2,603개 아이템에 대해 디자인(F)·소재(M)·색상(C)·감성(E) 4개 축으로 속성 텍스트가 매겨져 있다.
- **평가용 dev 셋**: 201개 대화 맥락 + top-3 정답 코디 조합.

우리 프로젝트의 **AI 캐릭터 대화형 추천** 기능과 거의 동일한 시나리오(대화 기반 패션 코디 추천)를 다루고 있어 활용도가 매우 높다.

## 2. S3 위치

기준 버킷:

```powershell
aws s3 ls s3://skn28-cozy/
```

11번 데이터 최상위:

```powershell
aws s3 ls 's3://skn28-cozy/11. 한국전자통신연구원_자율성장 인공지능 기술검증(PoC)을 위한 패션 코디 데이터셋/'
```

아이템 이미지 위치:

```text
s3://skn28-cozy/11. …패션 코디 데이터셋/img/
```

텍스트 메타·대화·평가셋 위치:

```text
s3://skn28-cozy/11. …패션 코디 데이터셋/mdata.wst.txt.2020.6.23
s3://skn28-cozy/11. …패션 코디 데이터셋/ddata.wst.txt.2020.6.23
s3://skn28-cozy/11. …패션 코디 데이터셋/ac_eval_t1.wst.dev
```

## 3. 전체 폴더 구조

`aws s3 ls --recursive --summarize`로 확인한 S3 상태:

- 전체 3,354 객체, 약 331MB

```text
11. 한국전자통신연구원_자율성장 인공지능 기술검증(PoC)을 위한 패션 코디 데이터셋/
├── img/                                       # 3,351 파일 (≈ 305MB)
│   ├── BL-001.jpg ~ BL-208.jpg                # 블라우스(상의)
│   ├── CD-001.jpg ~ CD-206.jpg                # 가디건(아우터)
│   ├── CT-001.jpg ~ CT-310.jpg                # 코트(아우터)
│   ├── JK-001.jpg ~ JK-340.jpg                # 재킷(아우터)
│   ├── JP-001.jpg ~ JP-310.jpg                # 점퍼(아우터)
│   ├── KN-001.jpg ~ KN-376.jpg                # 니트(상의)
│   ├── OP-001.jpg ~ OP-176.jpg                # 원피스(하의 슬롯)
│   ├── PT-001.jpg ~ PT-402.jpg                # 팬츠(하의)
│   ├── SE-001.jpg ~ SE-194.jpg                # 신발
│   ├── SH-001.jpg ~ SH-168.jpg                # 셔츠(상의)
│   ├── SK-001.jpg ~ SK-325.jpg                # 스커트(하의)
│   ├── SW-001.jpg ~ SW-180.JPG                # 맨투맨/스웨트셔츠(상·하)
│   └── VT-001.jpg ~ VT-115.jpg                # 베스트(아우터)
├── mdata.wst.txt.2020.6.23                    # 아이템 2,603개, 64,632줄, EUC-KR
├── ddata.wst.txt.2020.6.23                    # 대화 7,236개 세션, 154,662줄, EUC-KR
└── ac_eval_t1.wst.dev                         # 평가셋 201 세션, 1,990줄, EUC-KR
```

**중요 — 인코딩**: 세 텍스트 파일은 모두 **EUC-KR(CP949)**로 인코딩된 탭 구분(TSV) 순수 텍스트다. UTF-8로 그대로 열면 전부 깨진다. Python: `open(path, encoding="cp949")`.

또한 어절들이 `코디_해`, `포함_된`처럼 밑줄(`_`)로 형태소 결합되어 띄어쓰기 단위가 형태소 분석기를 거친 상태다(예: "치마 바지 원피스 중 어떤 옷 이 포함_된 코디 를 추천_해 드릴_까 요").

## 4. 폴더별 의미

### img/

파일명 패턴: `{카테고리코드}-{일련번호}.jpg`. 카테고리 코드는 13종:

| 코드 | 품목 | mdata 2번째 컬럼 슬롯 | 이미지 수 |
|---|---|---|---|
| BL | 블라우스 | T(상의) | 208 |
| KN | 니트 | T(상의) | 376 |
| SH | 셔츠 | T(상의) | 168 |
| SW | 맨투맨/스웨트셔츠 | T(상의) | 221 |
| OP | 원피스 | B(하의 슬롯 대체) | 176 |
| PT | 팬츠 | B(하의) | 402 |
| SK | 스커트 | B(하의) | 325 |
| CD | 가디건 | O(아우터) | 206 |
| CT | 코트 | O(아우터) | 310 |
| JK | 재킷 | O(아우터) | 340 |
| JP | 점퍼 | O(아우터) | 310 |
| VT | 베스트 | O(아우터) | 115 |
| SE | 신발 | S(신발) | 194 |

이 T/B/O/S 4-슬롯 구분은 mdata의 2번째 컬럼 값과 카테고리 코드를 교차 집계해 확인한 것이다(예: `T BL`, `B PT`, `O JK`, `S SE` 등 13개 조합 모두 확인됨). 원피스(OP)가 "하의" 슬롯에 묶인 이유는 실제 대화에서 "아우터 + 원피스 + 신발"처럼 원피스가 상의·하의를 동시에 대체하는 슬롯으로 쓰이기 때문으로 추정된다.

### mdata.wst.txt.2020.6.23

탭 구분 5컬럼: `아이템코드 \t 슬롯(B/O/S/T) \t 카테고리코드 \t 속성유형(F/M/C/E) \t 속성설명텍스트`. 아이템 하나당 여러 줄(속성 설명 개수만큼) 반복.

발췌(EUC-KR → UTF-8):

```
BL-001  T  BL  F  단추 여밈 의 전체 오픈형
BL-001  T  BL  F  스탠드 칼라 와 브이넥 네크라인 의 결합 스타일
BL-001  T  BL  M  면 100%
BL-001  T  BL  M  구김 이 가 기 쉬운
BL-001  T  BL  C  시원_해 보이 는 소라색 SKY BLUE
BL-001  T  BL  E  여성 스러운
BL-001  T  BL  E  오피스 룩
BL-001  T  BL  E  로맨틱 한 데이트 룩

SE-039  S  SE  F  로우 스니커즈
SE-039  S  SE  M  컨버스
SE-039  S  SE  C  화이트 솔리드 컬러
SE-039  S  SE  E  캐주얼 한
SE-039  S  SE  E  어느 스타일 에도 어울리 는 기본 아이템
```

(위 발췌는 BL-001의 20개 속성 중 대표 8개만 — 실제 BL-001은 F 6 / M 3 / C 2 / E 9 = 20속성.)

속성유형 4종 실측 분포: `F`(디자인/실루엣/디테일, 27,497줄), `M`(소재·세탁, 14,321줄), `C`(색상·톤·계절감, 5,919줄), `E`(감성/TPO 키워드, 16,895줄). 특히 `E`에는 "오피스 룩", "로맨틱한 데이트 룩", "데일리 룩"처럼 **TPO를 직접 지칭하는 표현**이, `C`에는 "가을에 입기 좋은 색상"처럼 **계절 정보가 색상 설명에 함께 딸려오는 경우**가 많다.

메타데이터가 존재하는 고유 아이템 수 = 2,603개(이미지 3,351장보다 적음). 카테고리별로는 CT(310)/OP(176)가 정확히 일치하지만, BL·KN·SE 등 나머지는 이미지가 메타데이터보다 많다 → **메타데이터 결측이 존재**.

### ddata.wst.txt.2020.6.23

154,662줄이 7,236개 대화 세션으로 나뉘어 있다(세션마다 `INTRO` 시작, `CLOSING` 종료. 직접 카운트해 `INTRO`·`CLOSING`이 각 정확히 7,236회로 일치 확인). 세션당 평균 ≈ 21턴.

컬럼 4개 (탭 구분):

```
턴번호 \t 화자(<CO>/<US>/<AC>) \t 발화내용 \t 대화행위(Dialogue Act) 태그(;로 복수 가능)
```

발췌(EUC-KR → UTF-8):

```
0   <CO>  어서 오 세 요 코디 봇 입 니다 무엇 을 도와 드릴_까 요    INTRO
1   <US>  처음 대학교 들어가 는데 입 을 옷 코디 해 주 세 요
2   <CO>  신입생 코디 에 어울리 게 화사 한 스웨터 를 추천_해 드릴_게 요  EXP_RES_SITUATION;EXP_RES_DESCRIPTION
3   <AC>  SW-009
4   <US>  이 옷 에 어울리 는 치마 로 추천_해 주 세 요             USER_SUCCESS
5   <AC>  SK-016
...
13  <US>  나쁘 지_않 네 요 외투 도 추천_해 주 시 겠_어 요          USER_SUCCESS
14  <CO>  요즘 계절 에는 가디건 이나 자켓 을 걸치기 에 좋_은데 …     ASK_TYPE
...
24  <AC>  CT-019 SW-009 SK-053 SE-039
25  <CO>  네 지금 까지 제안 해 드린 아이템 으로 전체 코디샷 을 제안 해 드립 니다   CONFIRM_SHOW
27  <US>  네 마음 에 드_네 요 감사_합 니다                          USER_SUCCESS
29  <CO>  이용_해 주 셔 서 감사_합 니다                             CLOSING
```

- `<CO>`: 코디봇 발화
- `<US>`: 사용자 발화
- `<AC>`: 그 시점에 실제로 제시된 아이템 코드(하나 또는 여러 개, 여러 개일 때 최종 코디 전체)

대화행위 태그 40여 종. 실제 빈도 상위: `WAIT`(14,354), `USER_SUCCESS`(13,620), `CONFIRM_SATISFACTION`(12,628), `USER_FAIL`(11,244), `EXP_RES_DESCRIPTION`(10,985), `INTRO`/`CLOSING`(각 7,236), `EXP_RES_COLOR`(5,849), `EXP_RES_MATERIAL`(4,212), `EXP_RES_LENGTH`(3,279), `ASK_TYPE`/`ASK_COLOR`/`ASK_DESCRIPTION`(질문형) 등.

### ac_eval_t1.wst.dev

1,990줄, `; 0`, `; 1` … 처럼 세미콜론+번호로 구분된 **201개 평가 세션**. 각 세션은 `ddata`와 비슷한 `CO`/`US` 대화 턴에 이어 정답 후보 3개를 랭킹으로 제시하는 `R1`/`R2`/`R3`로 끝난다.

발췌(EUC-KR → UTF-8):

```
; 0
US   가을 축제 에 입고 갈 스타일 로 코디 해 주 세 요
CO   치마 바지 원피스 중 어떤 옷 이 포함_된 코디 를 추천_해 드릴_까 요
US   원피스 나 치마 로 추천_해 주 세 요
CO   가을 에 입 기 좋 은 적당_한 두께감 의 아우터 와 함께 추천_해 드릴_까 요
US   네
R1   JP-137 KN-008 SK-047 SE-042
R2   JP-137 KN-045 SK-047 SE-004
R3   JP-137 KN-045 SK-047 SE-052
```

대화 맥락이 주어졌을 때 어떤 코디 조합이 정답에 가까운지의 **top-3 정답 랭킹**이 붙어 있는 평가셋.

## 5. 가장 중요한 파일: ddata.wst.txt

데이터의 본질은 **ddata 대화 코퍼스**다. mdata/ac_eval/dataset 이미지는 모두 이 대화를 보조·평가하기 위한 자산이다.

왜 ddata가 가장 중요한가:

- **대화 흐름(state machine)의 정답 라벨**: ASK_TYPE → WAIT → EXP_RES_* → CONFIRM_SATISFACTION → USER_SUCCESS/FAIL → SUCCESS → CLOSING 같은 흐름이 실제 데이터로 들어 있다. 우리 AI 캐릭터의 대화 시나리오 설계의 가장 직접적인 근거.
- **추천 결과 기록**: `<AC>` 행에 실제 추천된 아이템 코드가 들어가 있다. 어떤 코디가 사용자에게 어떤 흐름으로 제시되었는지를 시간순으로 재생할 수 있다.
- **추천 근거 설명 문장**: `EXP_RES_COLOR`, `EXP_RES_MATERIAL`, `EXP_RES_LENGTH`, `EXP_RES_PATTERN`, `EXP_RES_SITUATION` 등 "왜 이 옷을 추천했는지"의 자연어 근거 문장 패턴이 들어 있다. 우리 LLM이 추천 근거를 설명할 때의 few-shot 예시로 활용 가능.

## 6. 샘플 하나를 보는 순서

위에서 발췌한 "첫 세션 30턴"을 그대로 따라가 본다.

1. ddata를 EUC-KR로 연다.
2. 세션 시작 마커(`INTRO` 다음의 턴 0)를 찾는다. 여기까지가 한 세션.
3. 0번 `<CO>`의 인사("어서 오 세 요 … INTRO")로 세션이 열렸음을 확인.
4. 1번 `<US>` 사용자가 첫 요청("처음 대학교 들어가 는데 입 을 옷 코디 해 주 세 요").
5. 2번 `<CO>`에서 `EXP_RES_SITUATION;EXP_RES_DESCRIPTION`이 따라 붙는다 → "코디봇이 상황과 설명 근거를 함께 제시" 패턴.
6. 3번 `<AC>` 첫 추천 SW-009(맨투맨).
7. 4번 `<US>` USER_SUCCESS — 이 시점에서 사용자가 추가 요청("이 옷에 어울리는 치마로"). 5번 `<AC>` SK-016(스커트) 추천.
8. 7·8번에서 `USER_FAIL` → `<CO>`가 `EXP_RES_COLOR;EXP_RES_LENGTH`로 다른 후보 제시 → 9번 `<AC>` SK-053 — **추천 거절 시 대안 제시** 패턴.
9. 14번 `<CO>` `ASK_TYPE` — 새로운 슬롯(아우터) 제안. 15번 `<US>` 사용자 응답. 16번 `<AC>` CT-019. 17번 `<CO>` 근거 설명.
10. 24번 `<AC>` `CT-019 SW-009 SK-053 SE-039` — **최종 코디 셋**(아우터 + 상의 + 하의 + 신발).
11. 25번 `<CO>` `CONFIRM_SHOW` — 전체 코디샷 제시.
12. 27번 `<US>` `USER_SUCCESS`. 29번 `<CO>` `CLOSING` — 세션 종료.

이 12단계로 한 세션의 흐름을 잡으면 ddata의 구조가 완전히 보인다.

## 7. SQL로 보면 쉬운 이유

이 데이터는 텍스트와 코드를 함께 다루기 쉬운 행·열 테이블로 풀 수 있다.

```sql
-- 아이템 마스터 + 속성
CREATE TABLE items (
    item_id        TEXT,
    slot           TEXT,    -- 'T' | 'B' | 'O' | 'S'
    category_code  TEXT,    -- 'BL', 'PT' 등
    PRIMARY KEY (item_id)
);

CREATE TABLE item_attributes (
    item_id   TEXT,
    attr_type TEXT,         -- 'F' | 'M' | 'C' | 'E'
    attr_text TEXT,
    PRIMARY KEY (item_id, attr_type, attr_text)
);

-- 세션
CREATE TABLE sessions (
    session_id  INTEGER PRIMARY KEY,
    n_turns     INTEGER,
    closed_by   TEXT   -- 'CLOSING' 정상 종료인지 / 'USER_FAIL' 거절 반복인지
);

-- 한 세션의 한 턴
CREATE TABLE turns (
    session_id  INTEGER,
    turn_no     INTEGER,        -- 한 세션 내 0부터 시작
    global_line INTEGER,        -- ddata 파일의 실제 줄번호 (디버깅용)
    speaker     TEXT,           -- '<CO>' | '<US>' | '<AC>'
    utterance   TEXT,
    dialogue_act TEXT,          -- 'INTRO', 'EXP_RES_COLOR;EXP_RES_MATERIAL' 등
    PRIMARY KEY (session_id, turn_no)
);

-- 하나의 대화 안에 들어가는 추천 아이템(여러 번 등장 가능)
CREATE TABLE turn_actions (
    session_id   INTEGER,
    turn_no      INTEGER,
    item_id      TEXT,
    is_final_set INTEGER,       -- 0=중간 추천, 1=최종 코디
    PRIMARY KEY (session_id, turn_no, item_id)
);

-- 평가용 dev: 정답 랭킹
CREATE TABLE eval_sessions (
    eval_index  INTEGER,         -- '; 0' 의 번호
    session_id  INTEGER,         -- ddata 세션 중 어느 세션과 매칭되는지 (있다면)
    rank        INTEGER,         -- 1 | 2 | 3
    set_tokens  TEXT             -- 'JP-137 KN-008 SK-047 SE-042'
);
```

이렇게 넣으면 자주 쓰는 질의가 SQL이 된다.

가장 많이 등장한 아이템 코드 top 30:

```sql
SELECT item_id, COUNT(*) AS n_recommends
FROM turn_actions
GROUP BY item_id
ORDER BY n_recommends DESC
LIMIT 30;
```

USER_FAIL 후 다시 추천된 빈도:

```sql
WITH fail_turn AS (
    SELECT session_id, turn_no
    FROM turns
    WHERE dialogue_act LIKE '%USER_FAIL%'
),
retry_turn AS (
    SELECT t.session_id, t.turn_no
    FROM turns t
    JOIN fail_turn f ON t.session_id = f.session_id
                     AND t.turn_no = f.turn_no + 1
    WHERE t.speaker = '<AC>'
)
SELECT COUNT(*) FROM retry_turn;
```

특정 TPO 키워드("오피스 룩")가 붙은 아이템이 추천된 빈도:

```sql
SELECT ia.item_id, COUNT(*) AS cnt
FROM item_attributes ia
JOIN turn_actions ta ON ta.item_id = ia.item_id
WHERE ia.attr_type = 'E'
  AND ia.attr_text LIKE '%오피스%'
GROUP BY ia.item_id
ORDER BY cnt DESC
LIMIT 30;
```

## 8. 이 데이터로 알 수 있는 것

이 데이터로 바로 알 수 있는 것:

- 코디봇이 실제로 사용하는 **대화 상태 전이 패턴** (`ASK_* → WAIT → EXP_RES_* → CONFIRM_* → USER_*`)
- 7,236개 실제 세션에서 사용자가 **무엇을 먼저 요구하고, 무엇을 거절하는지** (USER_FAIL 분포)
- 추천된 아이템의 **TPO(오피스/데이트/주말/여행 등)** 분포 — E 태그 16,895줄에 녹아 있음
- 13개 카테고리(BL/CD/.../SW)별 **색상·소재·디자인 패턴** — F/M/C 속성 텍스트로 파악
- "이 슬롯(상의)에는 이런 디자인, 이 슬롯(아우터)에는 이런 소재" 같은 **슬롯별 자연어 어휘**
- 평가셋의 top-3 후보 분포로 본 "어울리는 조합과 덜 어울리는 조합의 차이"

조금 더 분석하면 알 수 있는 것:

- (T, B, O, S) 4-슬롯 구조에서의 **슬롯 동시 등장 패턴** — 어떤 카테고리끼리 한 코디에 같이 나오는지
- `EXP_RES_COLOR` 등의 추천 근거 문장이 **어떤 어휘**로 작성되는지 (few-shot 예시 후보)
- `USER_FAIL` 직후 코디봇이 **얼마나 자주 재추천하는지**, 평균 몇 번 만에 성공하는지
- 사용자가 "오피스룩"과 "캐주얼룩" 같은 **TPO 키워드를 어떻게 표현하는지**의 어휘 사전

## 9. 추천 시스템에 활용하는 방법

### 대화 흐름(state machine)을 우리 AI 캐릭터에 이식

`INTRO → ASK_TYPE/ASK_COLOR/ASK_LENGTH → SUGGEST_TYPE → WAIT → <AC> → EXP_RES_COLOR/MATERIAL/LENGTH/PATTERN → CONFIRM_SATISFACTION → USER_SUCCESS / USER_FAIL → CONFIRM_REPLY → 재추천 → SUCCESS → CLOSING` 패턴을 그대로 few-shot 예시로 넣거나, 상태기반(state machine) 설계의 정답 골격으로 쓸 수 있다. 특히 `EXP_RES_COLOR`, `EXP_RES_MATERIAL`, `EXP_RES_LENGTH`, `EXP_RES_PATTERN`, `EXP_RES_SITUATION`이 "왜 이 옷을 추천했는지"를 슬롯별로 풀어 설명하는 패턴은 우리 LLM의 추천 근거 문장 스타일 학습에 직접 참고 가능.

### 슬롯(속성) 설계의 근거

`ASK_TYPE`, `ASK_COLOR`, `ASK_LENGTH`, `ASK_DESCRIPTION` 같은 태그와 mdata의 `F`(디자인)/`M`(소재)/`C`(색상)/`E`(감성) 4대 축은, 추천 시스템이 사용자에게 "무엇을 더 물어봐야 하는지"의 슬롯 정의에 그대로 재사용 가능하다. 즉 "옷 추천 대화에서 결정적으로 오가는 정보 = 기장/색상/소재/핏/실루엣/감성(TPO·무드)"이라는 실데이터 근거.

### E(감성/TPO) 태그 → 매칭 룰 / RAG 임베딩

각 아이템에 "오피스 룩", "로맨틱한 데이트 룩", "데일리 룩", "캐주얼한" 같은 TPO·감성 키워드가 이미 붙어 있다. 그대로 룰 기반 필터(사용자가 "소개팅룩 추천해줘"라고 하면 E 태그에 "데이트" 계열이 포함된 아이템만 후보로 좁힘)로 쓰거나, E 태그 텍스트를 문장 임베딩해 벡터DB에 넣어 사용자 발화와 코사인 유사도 검색을 하는 RAG 방식으로도 활용 가능. 별도 매핑 사전 불필요.

### C(색상) 태그 → 날씨/계절 기반 색상 추천 룰

색상 설명에 "가을에 입기 좋은 색상", "시원해 보이는 소라색" 처럼 계절감·온도감이 함께 서술된 사례가 다수. 날씨 데이터(기온·계절)와 연동해 "여름=시원한 톤(소라·화이트) 우선, 겨울=따뜻한 톤(카멜·베이지) 우선" 같은 룰의 학습/검증 데이터로 쓸 수 있다.

### F(디자인) + M(소재) 태그 → 기온별 아이템 필터링

소재 설명에 "면 100%", "울 세탁 권장", "얇은 플레인 조직" 등 계절·두께 정보가 있다. "영상 10도 이하엔 울 소재 아우터 우선" 같은 룰의 근거 데이터로 활용.

### T/B/O/S 4-슬롯 구조 → 코디 조합 로직 그대로 이식

이 데이터는 이미 상의(T)/하의(B, 원피스 포함)/아우터(O)/신발(S) 슬롯으로 아이템을 태깅해 두었고, 실제 `<AC>` 라인에서도 "아우터+상의+하의+신발" 또는 "아우터+원피스+신발" 조합이 반복된다. 우리 추천 엔진의 "완성 코디 = 슬롯별 아이템 조합" 로직을 설계할 때 그대로 쓸 수 있다.

### ddata + Dialogue Act → SFT 데이터

7,236 세션의 `ASK_*` / `EXP_RES_*` / `USER_SUCCESS` / `USER_FAIL` / `CONFIRM_*` 라벨은 그대로 AI 캐릭터의 파인튜닝(SFT) 데이터나 few-shot 예시로 활용 가능. 특히 `USER_FAIL` 뒤에 대안이 다시 제시되는 패턴이 "추천 거절 시 대안 제시" 로직 학습에 유용.

### ac_eval_t1.wst.dev → 추천 성능 벤치마크

201개 평가 세션의 top-3 정답 조합(R1/R2/R3)은 우리 추천 로직의 recall@3·hit@1을 정량 측정하는 벤치마크로 즉시 사용 가능.

### 이미지(3,351장) → 시각 예시 / 멀티모달 데이터

각 아이템 코드에 매핑된 실 이미지가 있어, CLIP류 멀티모달 임베딩 모델 학습·검증에 사용 가능. 단, 이미지들이 스튜디오 제품샷이라 사용자 옷장 사진 도메인과는 차이가 있어, 파인튜닝 소스보다 파이프라인 검증용으로 적합.

### 주의사항

- 텍스트 파일은 **EUC-KR** + **형태소 결합(_) 토큰** → 전처리 필수.
- 이미지와 메타데이터의 **커버리지가 카테고리별로 불일치**(전체 이미지 3,351장 중 메타 2,603개) → 결측 처리 필요.
- 2020년 ETRI PoC 산출물이라 패션 트렌드 자체는 5~6년 전 기준. 트렌드 학습보다는 **"대화 구조·태깅 체계·색상/소재 서술 방식"** 참고용으로 더 적합하다.

## 10. 초보자용 최소 분석 루틴

처음에는 이것만 하면 된다.

1. ddata.wst.txt를 `encoding='cp949'`으로 연다.
2. `INTRO`로 시작하는 첫 세션 ~30턴을 한 화면에 본다. 화자/대화행위 태그가 어떻게 달라지는지만 눈으로 익힌다.
3. 같은 세션의 mdata 줄을 찾는다 — `<AC>` 행의 SW-009, SK-053, CT-019, SE-039 각각의 F/M/C/E 속성을 본다.
4. `<AC> CT-019 SW-009 SK-053 SE-039` 같이 4코드가 한 줄에 들어간 행을 찾으면, 그게 최종 코디다.
5. img/ 폴더에서 SW-009.jpg, CT-019.jpg 같은 코드를 받아 시각적으로 본다. 카테고리 라벨(T/O/S 슬롯)과 자코드를 매칭 확인.
6. ac_eval_t1.wst.dev에서 `; 0` 세션의 R1 줄을 읽고 "이 코디가 왜 1등인지"를 mdata의 E 태그로 추론해 본다.

```text
ddata → 한 세션 30턴
→ <AC> 줄의 아이템 코드 메모
→ mdata에서 각 코드의 F/M/C/E 속성 조회
→ img/에서 실제 사진 확인
→ ac_eval의 R1/R2/R3이 어떤 어울림인지 어휘로 추론
```

이 6단계면 ddata의 본질이 거의 잡힌다.

## 11. 규모와 주의사항

S3 실측치:

| 항목 | 값 |
|---|---|
| 전체 객체 | 3,354 |
| 전체 용량 | ≈ 331MB |
| mdata.wst.txt.2020.6.23 (행 수) | 64,632줄 |
| 고유 아이템 (mdata) | 2,603개 |
| ddata.wst.txt.2020.6.23 (행 수) | 154,662줄 |
| 대화 세션 수 (INTRO/CLOSING 카운트) | 7,236 |
| 평균 턴/세션 | ≈ 21 |
| ac_eval_t1.wst.dev (라인 수) | 1,990줄 |
| 평가 세션 수 | 201 |
| 이미지 수 | 3,351장 (13 카테고리) |

주의사항:

- **인코딩**: 모든 텍스트는 EUC-KR(CP949). UTF-8로 열면 전부 깨진다.
- **형태소 결합**: `코디_해`, `포함_된` 처럼 `_`로 어절이 결합돼 있어, RAG/임베딩 사용 시엔 어절 복원이나 토큰 분리 같은 전처리가 필요하다.
- **이미지↔메타데이터 불완전**: 메타 2,603개 < 이미지 3,351장. 카테고리별로는 CT(310)/OP(176)는 일치하지만 BL(208/148), KN(376/235), SE(194/130) 등에서 메타데이터가 부족하다. 조인 후 결측 처리가 필수.
- **이미지 도메인**: 스튜디오 제품샷. 사용자 "옷장 사진"과는 거리가 있어 파인튜닝에는 신중하게 접근.
- **트렌드 시점**: 2020년 PoC 산출물이라 트렌드 자체가 최신은 아니다. 구조/태깅/문장 패턴 위주로 활용.
- **카테고리 코드의 슬롯 의미**: OP는 mdata 슬롯이 'B'이지만 대화에서는 상의+하의 통합으로 자주 쓰인다 — 단순 슬롯 매핑이 항상 맞지는 않음.

## 12. 이번에 내려받은 샘플

작업 폴더:

```text
C:\Users\Playdata\AppData\Local\Temp
```

파일:

```text
11_ddata.txt               # 8,601,472 bytes (ddata.wst.txt.2020.6.23 전체)
11_mdata_head.txt          # 2,379,544 bytes (mdata.wst.txt.2020.6.23 전체 — 헤드만 본 척 표기했었지만 동일)
```

두 파일 모두 EUC-KR 인코딩임을 메타 식별 도구로 확인했다(`file` 명령 결과 "ISO-8859 text" → ASCII 호환 바이트 스트림이면서 한글 영역 바이트 포함).

이 두 파일로 다음을 확인했다:

- ddata의 첫 세션 30턴 구성 — `INTRO → EXP_RES_SITUATION → <AC> → ASK_TYPE → <AC> → CONFIRM_SHOW → USER_SUCCESS → CLOSING` 패턴
- 같은 세션의 USER_FAIL → 대안 제시 흐름 (턴 7, 8, 10, 11 → 9, 11 → 12)
- mdata의 BL-001 속성 20종 (F 6 / M 3 / C 2 / E 9), BL-002의 시작 줄
- 슬롯-카테고리 매핑 (`T BL`, `S SE` 등)

`img/` 폴더의 사진(.jpg)이나 `ac_eval_t1.wst.dev`는 이번 세션에서 따로 받지 않았다(다음 세션에서 받는 것을 권장).

## 13. 출처 및 확인 근거

출처:

- S3: `s3://skn28-cozy/11. 한국전자통신연구원_자율성장 인공지능 기술검증(PoC)을 위한 패션 코디 데이터셋/`
- 제공: ETRI(한국전자통신연구원) PoC 결과물
- 라이선스: S3 metadata 미확인, ETRI/AI Hub 라이선스 정책 적용 가정
- Confluence: https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/12419142 (내용 거의 없는 placeholder였음)
- 시각화 아티팩트 (통일 디자인): `data/11_PoC_패션코디/artifact.html` — 11번 아티팩트 CSS로 재작성 (2026-07-09) — 기존 https://claude.ai/code/artifact/ba7fb7bd-3b22-49be-92ea-70bfc3feec43 도 동일 콘텐츠

확인 근거:

- `aws s3 ls --recursive --summarize`로 3,354 객체, 약 331MB 실측.
- `aws s3api list-objects-v2`로 `img/` 하위 키를 모두 추출해 접두어(BL/CD/.../VT)별 카운트, 카테고리별 이미지 수 = 208/206/.../194 합 3,351 확인.
- ddata.wst.txt.2020.6.23을 직접 내려받아 (i) 첫 세션 30턴 발췌, (ii) INTRO/CLOSING 태그 카운트 = 각각 7,236회로 일치 확인.
- mdata.wst.txt.2020.6.23을 직접 내려받아 BL-001(20속성, F 6 / M 3 / C 2 / E 9), SE-039(5속성), SW-001(3속성) 발췌.
- ddata/mdata 헤더 인코딩이 UTF-8이 아닌 EUC-KR임을 별도 메타/파일 매직 확인.
- 4컬럼(턴번호/화자/발화/대화행위) 구조와 `<CO>/<US>/<AC>` 3종 화자 확인.
