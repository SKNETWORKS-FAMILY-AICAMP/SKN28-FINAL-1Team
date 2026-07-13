# Fashion RAG 설계 확장: S3 원본 데이터셋 기반 스타일 추천

- **작성일**: 2026-07-13
- **선행 문서**: `fashion-rag-embedding-pipeline_1.md` (인프라), `fashion-rag-embedding-retriever_2.md` (임베딩·리트리버), `local/개인맞춤룩추천_기능설계서.md`
- **목적**: 문서 2의 미확정 사항 1번("S3 `skn28-cozy` 폴더 구조 실측 확인")을 해소하고, 버킷에 실재하는 원본 데이터셋을 기준으로 **스타일 추천 RAG 구성을 확장**한다.
- **실측 방법**: 2026-07-13 boto3로 전체 prefix·라벨 샘플·스키마 직접 확인 (스크립트는 재실행 가능)

---

## 1. 실측 결과 요약과 선행 문서 정정

### 1-1. 핵심 발견

버킷에는 문서 1·2가 가정한 "네이버 크롤링 이미지+JSON 원본"이 **없다**. 실제 내용물은 **외부 공개 패션 데이터셋 12종**(AI Hub 6종, ETRI 2종, HuggingFace/Kaggle 2종, 사이즈코리아, 샘플)이다.

이에 따라 선행 문서를 다음과 같이 정정한다.

| 항목 | 기존 가정 (문서 1·2) | 실측 후 정정 |
|---|---|---|
| S3 역할 | 네이버 수집 이미지·JSON 원본 저장소 | **공개 데이터셋 저장소** (룩·지식·체형 데이터의 원천) |
| 상품 임베딩 이미지 소스 (문서 2의 2-4절 ②) | "S3에서 이미지 배치 다운로드" | `naver_product.image_url`(네이버 CDN)에서 직접 다운로드. S3는 다운로드 결과의 **캐시 적재처**로만 사용 |
| 버킷 리전 (문서 1의 3절 "AWS Seoul") | 서울 | **`ap-southeast-2`(시드니) 실측**. Qdrant EC2·서비스 리전 결정 시 전송 비용·지연 고려 필요 |

### 1-2. 스타일 추천 관점에서 열리는 확장 3가지

실측된 데이터셋들은 문서 2의 2축(아이템 카탈로그 + 지식 문서) 설계에 없던 원천을 제공한다.

1. **룩(코디) 축 신설** — K-Fashion은 룩 단위 스타일 라벨 + 착장별 상세 속성을 가진 전신 이미지 데이터다. "스타일(추구미)은 개별 아이템이 아니라 조합에서 나온다"는 문제를 룩 컬렉션 검색으로 풀 수 있다. (→ 3절, 4절)
2. **지식 문서의 데이터 기반 자동 생성** — 기능설계서 5-2절의 지식 문서는 수작업 작성을 가정했다. K-Fashion 라벨 통계·Polyvore 조합 데이터에서 스타일 프로파일·조합 규칙을 **집계로 추출**해 knowledge 청크와 Rule Validator 상수의 근거로 쓸 수 있다. (→ 5절)
3. **체형·사이즈 축 강화** — 의류통합데이터(모델 신체치수 + 착용 이미지 + 의류 실측치수 + 원단), 사이즈코리아(한국인 인체치수 통계)로 체형별 착장 사례 검색과 body_classifier 규칙의 정량 근거를 확보한다. (→ 5-3절)

---

## 2. 버킷 인벤토리 실측

### 2-1. 전체 목록과 활용 판정

전수 집계 실측(2026-07-13): **총 6,405,835 객체, 1.58TB** — 문서 1의 "한 자리수 TB급" 가정과 부합.

| Prefix | 데이터셋 정체 | 구성·규모 (실측) | 스타일 추천 활용 | 우선순위 |
|---|---|---|---|---|
| `01_의류통합데이터/` | AI Hub 의류 통합 데이터 (착용 이미지·치수·원단) | jpg 49.6만 + 라벨 json 49.5만, 333.6GB. 상품별 front/back/wear 컷 | 체형별 착장 사례, 사이즈·원단 지식 | **P1** |
| `03_패션 상품 및 착용 영상/` | AI Hub 패션 상품 및 착용 영상 | 이미지 17.7만(Item-Image/Model-Image) + 라벨 json 35.3만(Item/Model × Parse/Pose), 53.5GB | 라벨이 세그·포즈 중심이라 RAG 직접 활용 낮음. 상품컷↔착용컷 쌍은 옷장 사진 도메인 갭 실험 자산 | 비대상(ml) |
| `05_huggingface_polyvore_outfits/` | Polyvore Outfits (HF, CC-BY 4.0) | 39객체 4.0GB. 아웃핏 구성 json, compatibility/FITB, 아이템 메타 json(100MB), 이미지는 parquet 내부(`item_id`+bytes) | 조합 호환성 통계·스코어러 학습 | P2 |
| `10.한국_신체_3D_스캐닝_데이터/` | AI Hub 한국 신체 3D 스캐닝 | 106.9만 객체 289.6GB (png/obj/mtl) | RAG 비대상 — Body Analysis 학습용(ml) | 비대상 |
| `11. 한국전자통신연구원_...패션 코디 데이터셋/` | ETRI 자율성장 AI 패션 코디 (FASCODE PoC) | 아이템 이미지 3,351장(BL/SK/CT/SE-### 코드 체계) + 코디봇 대화 `ddata.wst.txt`(8.8MB) + 아이템 속성 `mdata.wst.txt`(2.3MB, EUC-KR), 0.3GB | Orchestrator·Stylist few-shot, 평가 골든셋 | P2 |
| `12.한국전자통신연구원_FASCODE/` | ETRI Fashion-How 2024 (subtask1~4) | 5.5만 객체 6.4GB. 이미지 + 감성 라벨 csv (Daily/Gender/Embellishment, BBox) + npy 피처 + baseline 코드 | RAG 비대상 — 태깅 모델 학습·평가용(ml) | 비대상 |
| `20.한국인_전신_형상_및_치수_측정_데이터/` | AI Hub 한국인 전신 형상·치수 | 215.8만 객체 572.5GB (jpg 115.8만 + json 99.6만 + ply). 전신 사진 부위 폴리곤 + 성별·나이 | RAG 비대상 — 전신 판별·체형 분류 학습용(ml) | 비대상 |
| `22.사이즈코리아/` | Size Korea 인체치수조사 5~8차 | xlsx 4개, 58.8MB | body_classifier 규칙 근거, 사이즈 지식 청크 | **P1** |
| `23_연도별_패션선호도파악_추천데이터/` | AI Hub 연도별 패션 선호도 | jpg 7.8만 + 라벨 json 18.4만(이미지당 다수 응답), 273.5GB. 시대별(1970~2019)·성별 | 레트로 무드 룩 소스, 데모그래픽 선호 통계 | P2 |
| `26_K_Fashion/` | AI Hub K-Fashion 이미지 | **jpg 32.8만 + 라벨 json 90.4만, 21.6GB.** 스타일 폴더별 룩 이미지 + 상세 라벨 | **룩 컬렉션 + 스타일 통계의 핵심 원천** | **P0** |
| `4_HM_Personalized_Fashion_Recommendations/` | Kaggle H&M | 이미지 10.5만 + `articles.csv`(상품 메타 25컬럼, 영어), 28.5GB. **transactions/customers 없음** | 협업필터링 불가. 영어권 카탈로그 — 활용도 낮음 | 보류 |
| `sample/` | 01 데이터셋 샘플 (26객체) | 개발용 소표본 | 파서 개발·테스트용 | — |

> 인벤토리 집계 스크립트는 `scripts/`에 두고 업로드 변동 시 재실행한다. 용량의 대부분(약 70%)은 RAG 비대상인 신체 데이터(10·20번)가 차지하므로, RAG 파이프라인이 실제로 읽는 범위는 훨씬 작다. **주의: K-Fashion은 라벨(90.4만)이 이미지(32.8만)의 약 2.75배로 불일치** — 라벨 중복 적재 또는 이미지 부분 업로드 가능성이 있어 manifest 구축 시 조인 성공률을 검증해야 한다(10절).

### 2-2. 데이터셋별 실측 스키마 (활용 대상만)

**① 26_K_Fashion — 룩 단위 스타일 라벨 (P0)**

경로: `26_K_Fashion/K-Fashion 이미지/Training/라벨링데이터/<스타일>/<id>.json` (실측 폴더: 기타·레트로·로맨틱·리조트·매니시·모던·밀리터리·섹시·소피스트케이티드·스트리트)

```jsonc
// 실측 예 (좌표 생략)
{
  "스타일": [{"스타일": "레트로", "서브스타일": "소피스트케이티드"}],   // 룩 단위
  "상의":   [{"카테고리": "블라우스", "색상": "베이지", "옷깃": "보우칼라",
             "소매기장": "긴팔", "소재": ["시폰"], "프린트": ["도트"], "핏": "루즈"}],
  "하의":   [{"카테고리": "팬츠", "색상": "블랙", "기장": "발목",
             "소재": ["우븐"], "프린트": ["무지"], "핏": "와이드"}],
  "아우터": [{}], "원피스": [{}]                                        // 착장 없으면 빈 객체
}
```

착장 파트(상의/하의/아우터/원피스)별로 카테고리·색상·서브색상·기장·소매기장·소재[]·프린트[]·넥라인·옷깃·디테일[]·핏을 제공한다. **룩 수준 스타일 + 아이템 수준 속성 + 전신 이미지**가 한 레코드에 있는 유일한 데이터셋 — looks 컬렉션(4절)과 스타일 통계(5절)의 원천. 라벨 결측이 흔하므로(색상만 있는 레코드 등) 파서는 필드 단위 옵셔널로 설계한다. 이미지는 `K-Fashion 이미지/Training/원천데이터/...`(라벨의 `이미지 파일명`으로 조인)에 있다.

**② 01_의류통합데이터 — 착용 이미지 + 신체치수 + 의류 실측치수 + 원단 (P1)**

경로: `01_의류통합데이터/{Training,Validation}/{01.원천데이터,02.라벨링데이터}/T{S,L}_{상품,모델}_<대분류>_<소분류>/<파일명>.(jpg|json)`. 파일명에 촬영 타입이 인코딩됨: `..._front|back|wear_02top_01blouse_woman`.

```jsonc
// 라벨 실측 요약 (annotation 폴리곤 생략)
{
  "metadata.model":   { "gender": "FEMALE", "age": "40대", "usually_size": "M",
                        "body_height": "160", "waist_size": "79", "hip_seize": "94",
                        "shoulders_width": "41", "weight": "56", ... },       // 착용 모델 실측 신체치수
  "metadata.clothes": { "type": "02top_01blouse", "season": "summer",
                        "fiber_composition": "Polyester", "elasticity": "none at all",
                        "transparency": "contain", "color": "White",
                        "sleeve_length_type": "long sleeves", "topneck_color_design": "band collar",
                        "washing_method": "Washing30", ... },
  "metadata.top":     { "front_length": "62.0", "chest_size": "100.0",
                        "shoulder_width": "41.0", "sleeve_length": "49.0", ... }  // 의류 실측 치수(cm)
}
```

착용(wear) 컷 ↔ 모델 신체치수의 연결이 핵심 가치: "키 160·어깨 41 체형이 이 블라우스를 입은 모습"이라는 **체형별 착장 사례**를 검색할 수 있다. `metadata.top.*` 치수는 기존 `NaverProductSize` 테이블과 같은 언어(총장·어깨너비·가슴단면 등)라 사이즈 적합성 판단에 바로 연결된다.

**③ 22.사이즈코리아 — 한국인 인체치수 통계 (P1)**

`5차(2003~04)`~`8차(2020~24)` 인체치수조사 xlsx. 성별·연령대별 키·몸무게·어깨너비·허리둘레 등 실측 분포 → body_classifier(기능설계서 3.4절)의 BMI 규칙을 **한국인 퍼센타일 기반**으로 교정하고, "한국 30대 남성 평균 어깨너비 ..." 같은 사이즈 지식 청크의 정량 근거로 쓴다.

**④ 05_polyvore — 아웃핏 호환성 (P2)**

`{disjoint,nondisjoint}/{train,valid,test}.json`(아웃핏 = set_id + 아이템 목록), `compatibility_*.txt`(정/부정 조합 쌍), `fill_in_blank_*.json`, `polyvore_item_metadata.json`(아이템별 title·description·semantic_category — 영어). 이미지는 `data/*/*.parquet` 내부에 `item_id`+bytes로 저장(실측: validation 14,657행) → 사용하려면 추출 스크립트 필요. **"어울림"의 대규모 정답 쌍**이라는 점이 유일무이 — 조합 스코어러(5-2절) 학습·평가용. 서구권 편향이 있으므로 규칙 추출보다 모델 학습·평가 데이터로 취급한다.

**⑤ 11. ETRI 패션 코디 — 추천 대화 시나리오 (P2)**

- `ddata.wst.txt`: 코디봇↔사용자 멀티턴 대화. 발화마다 의도 태그(`ASK_TYPE`, `EXP_RES_COLOR`, `USER_FAIL` 등)와 추천 아이템 코드(`<AC> SK-016`)가 붙음. 형태소 분리 표기("추천_해 주 세 요")라 전처리 필요.
- `mdata.wst.txt`: 아이템 코드(BL-001 등) → F(형태)/M(소재)/C(색상)/E(감성) 속성 문장. **EUC-KR 인코딩 실측** — 파싱 시 주의.
- 활용: Orchestrator 슬롯 추출·되물음 전략, Stylist 응답 패턴의 few-shot 예제와 평가 시나리오 골든셋. 벡터 검색 코퍼스로는 부적합(대화체 + 아이템 코드 의존).

**⑥ 23_연도별_패션선호도 — 시대별 스타일 + 선호 설문 (P2)**

`.../02.라벨링데이터/TL_{man,woman}_{1970..2019}/<이미지별>.json`. 이미지당 다수 응답자의 선호 설문(Q1~Q5)과 응답자 프로필(성별·연령대·직업·소득·평소 스타일 r_style1~5)이 붙는다. 활용: (a) 레트로·빈티지 추구미의 룩 이미지 소스(looks 컬렉션에 `era` payload로 편입), (b) 데모그래픽별 스타일 선호 프라이어 통계.

---

## 3. RAG 구성 확장 아키텍처

문서 2의 3컬렉션에 **looks를 신설**해 4컬렉션 체제로 확장한다.

```
                          ┌───────────────── Qdrant ─────────────────┐
naver_product (PG)   ──►  │ products  (image+text)   ◄── 채팅 쿼리    │
사용자 옷장 사진      ──►  │ wardrobe  (image+text)   ◄── 옷장 참조    │
지식 md + 자동생성 청크 ─►  │ knowledge (text)         ◄── 근거 질의    │
S3: K-Fashion·연도별  ──►  │ looks     (image+text)   ◄── 추구미 질의  │  ★신설
                          └───────────────────────────────────────────┘
S3: 의류통합·사이즈코리아 ──► (통계 집계) ──► knowledge 청크 + Rule Validator 상수
S3: Polyvore              ──► 조합 스코어러 학습·평가 (2차)
S3: ETRI 대화             ──► Orchestrator/Stylist few-shot + 평가셋 (벡터스토어 밖)
S3: 3D스캔·전신형상·FASCODE·착용영상 ─► ml/ 학습용 (RAG 비대상)
```

설계 원칙: **S3 데이터셋은 전부 "원천"이며 서비스 응답에 직접 노출하지 않는다.** 추천 결과로 사용자에게 보여주는 것은 여전히 products(구매 가능 상품)와 wardrobe(사용자 소유)뿐이다. looks·knowledge는 검색·설명 근거의 내부 자산이다 (라이선스 리스크 격리 — 9절).

---

## 4. looks 컬렉션 설계

### 4-1. 스키마

```python
client.create_collection(
    collection_name="looks",
    vectors_config={
        "image": VectorParams(size=768,  distance=Distance.COSINE),  # FashionSigLIP — 룩 전신 이미지
        "text":  VectorParams(size=1024, distance=Distance.COSINE),  # BGE-M3 — 라벨 직렬화 문장
    },
)
# payload 인덱스
for field, schema in [
    ("style", "keyword"), ("substyle", "keyword"),
    ("source_dataset", "keyword"),          # kfashion / era_pref ...
    ("era", "integer"), ("gender", "keyword"),
    ("part_categories", "keyword"),         # ["블라우스","팬츠"] — 구성 아이템 카테고리
    ("colors", "keyword"), ("fits", "keyword"),
]:
    client.create_payload_index("looks", field_name=field, field_schema=schema)
```

- point ID = `uuid5(NAMESPACE, f"{source_dataset}:{원본 파일 식별자}")` — 문서 2와 동일한 멱등 upsert 규칙.
- payload에 착장 파트별 속성 전문(`parts: {상의: {...}, 하의: {...}}`)과 `s3_key`를 보존한다. 룩→아이템 분해 검색(7절)이 payload만으로 가능해야 LLM 왕복이 줄어든다.
- 1차는 K-Fashion만 적재한다. 23번(연도별)은 스타일 enum이 달라(hippie 등 시대 스타일) 매핑 정리 후 `source_dataset="era_pref"`로 증분 적재.

### 4-2. 라벨 직렬화 (문서 2의 2-2절과 동일 원칙)

```python
def serialize_look(label: dict) -> str:
    """K-Fashion 라벨 → 임베딩용 문장. 스타일 → 파트 순서 고정."""
    st = label["스타일"][0]
    parts = [f"{st.get('스타일')} 스타일" + (f", {st['서브스타일']} 서브스타일" if st.get("서브스타일") else "")]
    for part in ("아우터", "상의", "하의", "원피스"):
        for item in label.get(part, []):
            if not item:
                continue
            parts.append(", ".join(x for x in [
                f"{part} {item.get('카테고리', '')}".strip(),
                f"{item['색상']} 색상" if item.get("색상") else None,
                f"{item['핏']} 핏" if item.get("핏") else None,
                f"{'/'.join(item['소재'])} 소재" if item.get("소재") else None,
                f"{'/'.join(item['프린트'])} 프린트" if item.get("프린트") else None,
                f"{item['기장']} 기장" if item.get("기장") else None,
            ] if x))
    return ". ".join(parts)
# 예: "레트로 스타일, 소피스트케이티드 서브스타일. 상의 블라우스, 베이지 색상, 루즈 핏, 시폰 소재, 도트 프린트. 하의 팬츠, 블랙 색상, 와이드 핏, 우븐 소재, 발목 기장"
```

### 4-3. 스타일 태그 정합 — 크로스 컬렉션 검색의 전제

K-Fashion 스타일 enum과 collector `STYLES`(llm_tagger)가 다르므로, 매핑 없이는 looks에서 찾은 스타일로 products를 필터할 수 없다. 매핑 테이블을 `ml/common/tag_schema.py`(문서 2의 4절에서 계획한 공용 모듈)에 상수로 둔다.

| K-Fashion | collector STYLES (매핑 초안) | 비고 |
|---|---|---|
| 스트리트 | 스트릿 | 표기 차이 |
| 레트로 | 빈티지 | |
| 로맨틱 | 러블리, 페미닌 | 1:N — any-of 필터 |
| 리조트 | 리조트 | |
| 매니시 | 댄디 | |
| 모던 | 미니멀, 시크 | 1:N |
| 소피스트케이티드 | 포멀, 시크 | 1:N |
| 밀리터리 | 아웃도어 | 근사 — 팀 검토 |
| 섹시 | 시크 | 근사 — 팀 검토 |
| 기타 | (매핑 제외) | |

> 방향 주의: 이 표는 **looks → products 필터 변환용**(K-Fashion이 소스)이다. 역방향(사용자 발화의 스타일 표현 → enum 정규화)은 문서 2의 3-3절 ② 그대로 Orchestrator가 담당한다. 매핑은 근사가 섞여 있으므로 하드 필터가 아닌 should(부스트)로 시작하고, 골든셋 평가(문서 2의 5절) 후 하드 여부를 정한다.

---

## 5. 지식의 데이터 기반 자동 생성

수작업 지식 문서(기능설계서 5-2절)를 대체하는 게 아니라, **정량 근거가 필요한 지식을 집계로 생산**해 보강한다. 산출물은 두 형태: ① knowledge 컬렉션 청크(자연어 + 메타데이터), ② Rule Validator·filter_rules의 코드 상수.

### 5-1. 스타일 프로파일 청크 (K-Fashion 집계, P0)

스타일별 착장 속성 분포를 집계해 청크화한다.

```
집계: GROUP BY 스타일 → 파트별 카테고리/핏/색상/소재 상위 빈도
청크 예 (자연어 + 메타데이터):
  "스트리트 스타일 상의는 티셔츠·맨투맨 비중이 높고 오버사이즈·루즈 핏이 지배적이다.
   하의는 데님·조거 팬츠가 많으며 와이드·노멀 핏 위주다. 색상은 블랙·화이트 등 무채색 기반에
   포인트 색을 얹는 조합이 흔하다."          ← 수치는 집계 결과로 채움
  payload: {knowledge_type: "style_profile", style: "스트릿", source: "kfashion-agg-v1"}
```

Stylist가 "왜 이 조합이 스트릿인가"를 설명할 때의 검색 근거가 되고, Orchestrator의 스타일 → 속성 슬롯 확장(예: 추구미 "스트릿" → fit should=[오버사이즈]) 근거도 된다. 집계 스크립트 버전(`source`)을 payload에 남겨 재현성을 확보한다.

### 5-2. 조합 규칙 통계 (K-Fashion 공출현 + Polyvore, P0→P2)

- **K-Fashion 공출현(P0)**: 한 룩 안의 (상의 속성 × 하의 속성) 쌍 빈도 집계 → "와이드 하의와 함께 입는 상의는 크롭·노멀 기장이 다수, 루즈 상의+와이드 하의 조합은 소수" 같은 실루엣 균형 통계. Rule Validator의 금칙(와이드+와이드 지양 등)을 감이 아닌 빈도 근거로 채택/기각하고, 문서 2의 3-3절 ③(옷장 크로스 컬렉션 "어울림")의 호환 조건 생성 테이블로 쓴다.
- **Polyvore(P2)**: compatibility 정/부정 쌍으로 조합 스코어러(이미지 쌍 → 호환 점수)를 학습·평가. Stylist가 만든 조합의 사후 검증에 붙인다. 서구권 데이터이므로 K-Fashion 통계와 충돌 시 K-Fashion 우선.

### 5-3. 체형·사이즈 지식 (01 의류통합 + 사이즈코리아, P1)

- 사이즈코리아 xlsx → 성별·연령대별 주요 치수 퍼센타일 테이블(코드 상수) + "한국인 체형 분포" 청크. body_classifier의 규칙 임계값을 이 테이블에서 유도한다.
- 01 의류통합 → (모델 신체치수, 의류 카테고리·실측치수, 착용 이미지) 트리플. 1차 활용은 **치수 적합 지식 청크**("어깨 41cm 체형에 어깨단면 41~43cm 상의가 정사이즈, 45cm+는 오버핏 연출" 류의 통계). 2차로 wear 컷을 별도 컬렉션(`fit_examples`)으로 임베딩해 "나와 비슷한 체형의 착장 사례" 검색을 검토한다 — 신체치수 payload range 필터 + 이미지 벡터 검색 조합.

### 5-4. 생성 파이프라인 원칙

```
S3 원본 → 파서(ml/datasets/) → 집계 스크립트(scripts/knowledge_gen/) → ① md 청크 → knowledge 임베딩
                                                                      → ② 상수 py → filter_rules/validator
```

- 집계 산출 md는 `docs/knowledge/generated/`에 커밋해 **사람이 리뷰·수정 가능한 중간 산출물**로 둔다 (LLM이 통계를 문장화하되, 수치는 집계값 그대로). 문서 2의 2-6절 "문서 수정 시 전체 재빌드" 원칙 동일 적용.
- 코드 상수와 knowledge 청크의 이중 원천 문제는 문서 2의 3-3절 ① 원칙 유지: **판단은 코드 상수, 설명 근거는 청크**.

---

## 6. 적재 파이프라인 확장 (문서 1 흐름 재사용)

### 6-1. manifest 우선 구축

S3 list는 느리고(수십만 객체) 반복 비용이 크다. 데이터셋별로 **manifest(parquet/jsonl: s3_key, 원본 id, 라벨 요약, 이미지-라벨 조인 키)를 1회 구축**해 S3에 저장하고, 임베딩 배치·집계 스크립트는 manifest만 읽는다. 문서 2의 2-4절 ①(PG에서 대상 조회)의 데이터셋판이며, 재처리 방지(= egress 절감) 원칙도 동일하다.

### 6-2. 데이터셋 어댑터 구조

```
ml/
├── datasets/                  # 데이터셋별 파서 — 공통 인터페이스로 통일
│   ├── base.py                # iter_records() -> LookRecord | FitRecord ...
│   ├── kfashion.py            # 라벨 파싱 + 이미지 조인 + serialize_look
│   ├── closet_integrated.py   # 01 의류통합: 모델/의류 메타 파싱
│   ├── era_preference.py      # 23 연도별
│   └── polyvore.py            # parquet 이미지 추출 포함
├── embedding/                 # 문서 2의 배치 파이프라인 — products와 looks 공용
└── common/tag_schema.py       # enum + K-Fashion 매핑 테이블 (4-3절)
```

### 6-3. 실무 주의사항 (실측에서 확인된 것)

- **경로 인코딩**: prefix에 한글·공백·`.`이 섞여 있고(예: `11. 한국전자통신연구원_...`), Windows에서 AWS CLI 출력이 cp949로 깨지는 것을 실측 확인. **모든 접근은 boto3로** 하고 키는 manifest에 저장된 값을 그대로 사용한다 (수기 입력 금지).
- **인코딩**: ETRI mdata는 EUC-KR. 파서에서 인코딩 명시.
- **라벨 결측**: K-Fashion 라벨은 필드 단위 결측이 흔함. 직렬화는 결측 무시, payload는 있는 필드만.
- **부분 업로드·불일치 가능성**: K-Fashion 스타일 폴더 10/23종, 라벨 수(90.4만) ≫ 이미지 수(32.8만) 등 — manifest 구축 시 라벨-이미지 조인 성공률을 기대 규모와 대조해 리포트.
- **리전**: 버킷은 `ap-southeast-2`. RunPod 임베딩은 어차피 인터넷 egress라 영향이 적지만, 집계·전처리 스크립트를 EC2에서 돌린다면 같은 리전에 두는 것이 전송비 0원이다. Qdrant EC2 리전(서울 가정)과 다르다는 점을 인프라 결정에 반영.

---

## 7. 리트리버 확장: 룩 기반 2단 검색

문서 2의 3-3절 ②(추구미 추천)를 다음처럼 업그레이드한다. 기존 파이프라인(필터 → 벡터 → 슬롯별 후보)은 그대로 두고, **looks 검색이 앞단에 추가**된다.

```
채팅 "Y2K 느낌으로 꾸미고 싶어"
  ① looks 검색: query_text 임베딩 → looks.text (+style should 필터) → 상위 M 룩
  ② 룩 분해: 상위 룩들의 payload.parts에서 파트별 속성 분포 추출
      → 슬롯별 필터·쿼리 보강 (예: 하의 must {category_small: 팬츠/청바지}, should {fit: 와이드})
  ③ products 검색: 보강된 슬롯으로 문서 2의 retrieve_items 그대로 호출
  ④ Stylist: 참조 룩(이미지·속성)을 근거로 조합 생성 + "이 룩처럼 ~" 설명
```

- ①에서 벡터만으로 부족한 신조어 스타일("Y2K", "발레코어")은 K-Fashion enum에 없어도 **룩 이미지·직렬화 문장의 의미 공간에서 잡히는 것**이 이 단계의 존재 이유다. enum 정규화 실패 시의 fallback이기도 하다.
- ②는 LLM 없이 payload 집계로 수행(순수 함수형 Tool 원칙 유지). Stylist에는 상위 룩 이미지 URL(내부용 presigned)과 속성 요약만 전달한다.
- 옷장 추천의 "이 셔츠에 어울리는 하의"(문서 2의 3-3절 ③)도 동일 패턴: 기준 아이템 속성으로 looks를 필터 검색(해당 속성의 상의가 포함된 룩) → 그 룩들의 하의 속성 분포 → products 필터. **"어울림 = 실제 룩에서의 공출현"**으로 근거가 데이터에 생긴다.
- ETRI 대화 데이터는 이 흐름의 **평가 골든셋**으로 변환한다: (사용자 요청 발화 → 정답 아이템 속성) 쌍을 추출해 슬롯 추출 정확도·추천 방향 일치율을 측정.

---

## 8. 단계별 로드맵

| 단계 | 작업 | 산출물 |
|---|---|---|
| **P0** | K-Fashion manifest + 파서 → looks 컬렉션 적재, 스타일 프로파일·공출현 집계 → knowledge 청크·상수, 스타일 매핑 테이블 팀 확정 | looks 검색 가능, 추구미 2단 검색(7절) 1차 동작 |
| **P1** | 사이즈코리아 → body_classifier 상수·사이즈 청크, 01 의류통합 manifest + 치수 적합 지식 | 체형·사이즈 근거 강화 |
| **P2** | 23 연도별 looks 증분 적재(era payload), ETRI 대화 → few-shot·평가셋, Polyvore 조합 스코어러 실험 | 커버리지·검증 강화 |
| 보류 | H&M(활용처 확정 시) / 03·10·12·20은 RAG 비대상 — ml 학습 계획에서 별도 관리 | — |

P0가 끝나면 문서 2의 골든 쿼리셋 평가에 **추구미 쿼리 × looks 경유 여부 A/B**를 추가해 2단 검색의 효과를 정량 확인한다.

---

## 9. 라이선스·거버넌스

- **AI Hub 데이터셋(01·03·10·20·23·26)**: 이용약관상 활용 범위(연구/상업), 출처 표기, **원본 데이터의 대외 서비스 노출 제한** 여부를 데이터셋별로 확인해야 한다. 3절의 원칙(내부 검색·통계 자산으로만 사용, 사용자 노출은 products/wardrobe만)은 이 리스크를 격리하기 위한 것이기도 하다.
- **Polyvore**: CC-BY 4.0 (README 실측) — 출처 표기로 학습·평가 사용 가능.
- **H&M**: Kaggle 대회 데이터 — 대회 목적 외 사용 제한 조항 확인 전 서비스 활용 금지.
- **ETRI(11·12)**: Fashion-How 대회 규정 확인 필요.
- **개인정보**: 01(모델 신체치수+사진), 20(전신 사진), 10(3D 스캔)은 사람 데이터다. 공개 데이터셋이지만 재배포·노출 금지 원칙을 지키고, 파생물(임베딩·통계)에도 개인 식별 정보를 남기지 않는다.

---

## 10. 미확정 / 확인 필요

1. **업로드 완료 여부·정합성**: K-Fashion 스타일 폴더(10/23종)와 라벨-이미지 수 불일치(라벨 90.4만 vs 이미지 32.8만), 각 데이터셋 Validation 스플릿 — 수집 담당자 확인 + manifest 조인 검증.
2. **AI Hub 약관의 서비스 활용 범위** — 상업 서비스 전 필수 확인 (9절).
3. 스타일 매핑 테이블(4-3절) 팀 확정.
4. 23번(연도별) 시대 스타일 enum의 매핑 정책 — looks 적재 시점에 결정.
5. `fit_examples` 컬렉션(5-3절 2차) 도입 여부 — P1 지식 청크 효과를 보고 판단.
6. 버킷-Qdrant EC2 리전 정렬(6-3절) — 인프라 확정 시 반영.

---

_마지막 업데이트: 2026-07-13_
