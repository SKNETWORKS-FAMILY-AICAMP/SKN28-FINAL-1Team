# Fashion RAG 임베딩·리트리버 설계

- **작성일**: 2026-07-13
- **선행 문서**: `fashion-rag-embedding-pipeline_1.md` (인프라: RunPod GPU + S3 + EC2 Qdrant), `local/개인맞춤룩추천_기능설계서.md`
- **대상 기능**: ① 오늘의 룩(날씨+설정) ② 추구미 추천(채팅+설정) ③ 옷장 추천(채팅+설정)

---

## 1. 설계 요약

세 기능 모두 **"필터 빌더 → 메타데이터 하드 필터 → 벡터 유사도 랭킹 → 슬롯별 후보 반환"**이라는 동일한 리트리버 파이프라인을 공유하고, 기능별 차이는 **필터 조건과 쿼리 벡터의 출처**뿐이다. 따라서 리트리버는 하나만 구현하고, 기능별로는 얇은 어댑터만 둔다.

임베딩은 **아이템(상품·옷장) 임베딩**과 **스타일링 지식 문서 임베딩** 두 축으로 나눈다. 아이템은 이미지·텍스트 멀티모달, 지식 문서는 한국어 텍스트 단일 모달이다.

```
                        ┌──────────── Qdrant ────────────┐
naver_product (PG) ──►  │ products   (image + text 벡터)  │ ◄── 채팅 쿼리 텍스트 임베딩
사용자 옷장 사진   ──►  │ wardrobe   (image + text 벡터)  │ ◄── 옷장 아이템 참조 벡터
스타일링 지식 md  ──►  │ knowledge  (text 벡터)          │ ◄── TPO·체형·날씨 질의
                        └─────────────────────────────────┘
```

---

## 2. 임베딩 설계

### 2-1. 모델 선택: 이미지·텍스트 이원화

| 용도 | 모델 | 차원 | 이유 |
|---|---|---|---|
| 아이템 **이미지** 벡터 | Marqo-FashionSigLIP | 768 | 패션 도메인 특화 CLIP 계열. 옷장 사진 ↔ 상품 이미지 간 시각 유사도에 최적 |
| 아이템 **텍스트** 벡터 / 채팅 쿼리 | BGE-M3 (또는 multilingual-e5-large) | 1024 | FashionSigLIP의 텍스트 타워는 영어 중심이라 **한국어 채팅 쿼리·한국어 태그 문장에 부적합**. 다국어 임베딩 모델로 분리 |
| 지식 문서 청크 | BGE-M3 (동일 모델 재사용) | 1024 | 쿼리와 같은 공간이어야 검색 가능. 모델 하나로 운영 단순화 |

핵심 판단: **한국어 텍스트 검색과 이미지 유사도 검색은 요구 특성이 달라 한 모델로 합치지 않는다.** FashionSigLIP 하나로 텍스트까지 처리하려면 태그·쿼리를 영어로 번역해야 하는데, 번역 품질이 검색 품질의 상한이 되고 latency도 늘어난다. Qdrant의 named vector로 한 포인트에 두 벡터를 붙이면 저장 구조는 복잡해지지 않는다.

> BGE-M3는 dense와 sparse(lexical) 벡터를 동시에 출력하므로, 이후 하이브리드 검색(4-5절)으로 확장할 때 모델 교체 없이 가능하다.

### 2-2. 임베딩 입력 텍스트 직렬화

텍스트 벡터의 품질은 **태그를 자연어 문장으로 어떻게 직렬화하느냐**가 좌우한다. `naver_product`의 태그 컬럼을 고정 템플릿으로 문장화한다.

```python
def serialize_product(p: NaverProduct) -> str:
    """태그 → 임베딩용 자연어 문장. 필드 순서 고정(재현성)."""
    parts = [
        f"{p.category_large} {p.category_small}",
        f"{'/'.join(p.style)} 스타일" if p.style else None,
        f"{'/'.join(p.color)} 색상" if p.color else None,
        f"{p.fit} 핏" if p.fit else None,
        f"{'/'.join(p.material)} 소재" if p.material else None,
        f"{'/'.join(p.season)}에 적합" if p.season else None,
        f"{'/'.join(p.usage)}" if p.usage else None,
        p.title,  # 브랜드·구체 아이템명 보존
    ]
    return ", ".join(x for x in parts if x)
# 예: "상의 셔츠, 미니멀/댄디 스타일, 화이트 색상, 오버핏 핏, 면 소재, 봄/가을에 적합, 옥스포드 셔츠"
```

주의점: raw `title`만 임베딩하면 쇼핑몰 특유의 키워드 나열("[무료배송] 남녀공용 오버핏...")이 벡터를 오염시킨다. 정제된 `title`(title_raw가 아닌 쪽)을 쓰고, 태그 문장을 앞에 배치해 태그가 벡터를 지배하게 한다.

### 2-3. Qdrant 컬렉션 스키마

```python
# 컬렉션: products
client.create_collection(
    collection_name="products",
    vectors_config={
        "image": VectorParams(size=768, distance=Distance.COSINE),
        "text":  VectorParams(size=1024, distance=Distance.COSINE),
    },
)
# payload 인덱스 — 하드 필터에 쓰이는 필드는 반드시 인덱스 생성
for field, schema in [
    ("category_large", "keyword"), ("category_small", "keyword"),
    ("layer_role", "keyword"), ("season", "keyword"),   # 배열 → keyword 인덱스로 any-match
    ("style", "keyword"), ("color", "keyword"),
    ("fit", "keyword"), ("pattern", "keyword"),
    ("lprice", "integer"),
]:
    client.create_payload_index("products", field_name=field, field_schema=schema)
```

- **point ID** = `naver_product_id` 기반 UUID5. 재실행 시 같은 ID로 upsert → 멱등성 확보 (파이프라인 문서 2-3절의 재시도 요구 충족).
- **payload**에는 필터 필드 + 응답 구성에 필요한 최소 필드(title, image_url, lprice, brand, link)만 넣는다. 원본은 PG가 소유(단일 진실 공급원), Qdrant는 파생본.
- payload에 `embedding_version: "fashionsiglip-v1/bge-m3-v1"`, `tagged_at`을 기록해 모델 교체 시 선별 재임베딩이 가능하게 한다.

`wardrobe` 컬렉션은 동일 구조 + `user_id`(keyword 인덱스) 추가. `knowledge` 컬렉션은 text 벡터 단일 + `{knowledge_type, body_type, skin_tone, season, occasion}` payload(기능설계서 5-3절).

### 2-4. 상품 배치 임베딩 파이프라인 (RunPod)

```
① PG에서 대상 조회: tagging_status='done' AND (미임베딩 OR embedding_version 불일치)
② S3에서 이미지 배치 다운로드 (s3://skn28-cozy/... — 이미 로컬 캐시에 있으면 스킵)
③ GPU 배치 추론: FashionSigLIP(이미지) + BGE-M3(직렬화 텍스트), batch 128~256
④ Qdrant upsert (500~1000 포인트/배치, 실패 배치 재시도)
⑤ PG에 embedded_at / embedding_version 기록 (재처리 방지 = S3 egress 비용 절감)
```

- 이미지 다운로드와 GPU 추론을 파이프라이닝(prefetch 스레드)하면 GPU 유휴를 줄일 수 있다.
- 이미지 로드 실패(URL 만료 등) 상품은 **text 벡터만으로 upsert**하고 payload에 `has_image_vector: false`를 남긴다. 검색에서 제외하지 않는 것이 커버리지에 유리.
- 코드는 `ml/embedding/`에 두고, S3 경로·Qdrant 호스트·디바이스는 전부 환경변수 (RunPod → AWS 이관 대비).

### 2-5. 옷장 아이템 임베딩 (실시간 단건)

옷장 등록은 배치가 아니라 **업로드 시점 단건 처리**다. 흐름:

```
사진 업로드 → S3 저장 → FashionSigLIP 이미지 벡터
           → Vision LLM 태깅 (collector/naver의 llm_tagger 태그 체계 재사용:
              동일한 SEASONS/STYLES/LAYER_ROLES enum → 상품과 필터 호환)
           → serialize → BGE-M3 텍스트 벡터
           → Qdrant wardrobe upsert (payload: user_id, 태그)
```

- 태그 체계를 상품과 **동일하게** 가져가는 것이 핵심이다. 그래야 "옷장의 이 셔츠와 어울리는 하의를 상품에서 검색" 같은 크로스 컬렉션 질의가 같은 필터 언어로 동작한다. `collector/naver/llm_tagger.py`의 스키마·enum을 공용 모듈로 추출해 재사용한다.
- 단건 SigLIP 추론은 CPU로도 수백 ms 수준이라 API 서버 사이드카(또는 경량 추론 컨테이너)로 충분하다. GPU 상시 운용 불필요.

### 2-6. 지식 문서 임베딩

기능설계서 5-2절의 지식 문서(체형별 가이드, 컬러 매칭, 날씨-의상 매핑, TPO, 조합 규칙)는 md로 작성해 S3 또는 repo `docs/knowledge/`에 버전 관리하고, **의미 단위(권장 300~500자) 청크**로 잘라 BGE-M3로 임베딩한다. 청크마다 메타데이터를 명시적으로 붙인다(문서 헤더에서 상속). 이 컬렉션은 수천 청크 규모라 재임베딩 비용이 무시할 수준 — 문서 수정 시 전체 재빌드가 가장 단순하다.

---

## 3. 리트리버 설계

### 3-1. 공통 파이프라인

```
슬롯 (Orchestrator가 추출한 TPO·날씨·프로필·채팅 조건)
  → FilterBuilder: 슬롯 → Qdrant Filter (must / must_not / should)
  → 쿼리 벡터 결정: 채팅 텍스트 임베딩 or 옷장 아이템 참조 벡터 or 무벡터(필터만)
  → layer_role 슬롯별 검색 (기본 상의 / 하의 / 아우터 / 신발 ...)
  → 상위 K 후보 반환 → Stylist(조합 생성) → Rule Validator
```

리트리버는 LLM을 쓰지 않는 순수 함수형 Tool(기능설계서 원칙 유지). Django `apps/recommend/services/retriever.py`에 서비스 계층으로 두고 `qdrant-client`를 사용한다.

```python
@dataclass
class RetrievalQuery:
    query_text: str | None = None          # 채팅 기반 검색어
    ref_vector: list[float] | None = None  # 옷장 아이템 참조 벡터 (image)
    must: dict[str, list[str]] = field(default_factory=dict)      # {"season": ["여름"]}
    must_not: dict[str, list[str]] = field(default_factory=dict)  # {"color": ["형광","네온"], "fit": ["스키니"]}
    should_boost: dict[str, list[str]] = field(default_factory=dict)
    price_range: tuple[int, int] | None = None
    limit: int = 20

def retrieve_items(q: RetrievalQuery, layer_role: str, collection="products") -> list[Candidate]:
    flt = build_filter(q, layer_role)   # 아래 3-2
    if q.ref_vector is not None:
        return client.query_points(collection, query=q.ref_vector,
                                   using="image", query_filter=flt, limit=q.limit)
    if q.query_text:
        vec = embed_text(q.query_text)  # BGE-M3
        return client.query_points(collection, query=vec,
                                   using="text", query_filter=flt, limit=q.limit)
    # 벡터 없이 필터만: scroll + 자체 스코어(신상순/가격대 등)
    return client.scroll(collection, scroll_filter=flt, limit=q.limit)
```

### 3-2. 필터 정책: 하드 vs 소프트의 구분 기준

**"위반하면 추천이 틀리는 조건"은 must/must_not(하드), "맞으면 더 좋은 조건"은 쿼리 벡터·should(소프트)**로 나눈다.

| 조건 | 처리 | 근거 |
|---|---|---|
| 피하고 싶은 색 (형광/네온) | `must_not: color` | 한 번이라도 위반하면 신뢰 상실. 벡터 유사도에 맡기면 누출됨 |
| 피하고 싶은 핏 (오버핏/스키니) | `must_not: fit` | 동일 |
| 계절/기온 적합성 | `must: season` (+ warmth 매핑) | 한여름에 니트 추천은 오답 |
| layer_role (슬롯 구성) | `must: layer_role` | 조합 구성의 전제 |
| 추구 스타일 (미니멀 등) | `must: style`(any-of) **+ 쿼리 텍스트에도 포함** | 태그 누락 상품 구제를 위해 벡터에도 반영. 후보 부족 시 must → should 완화 |
| 피부톤 팔레트, 체형 권장 실루엣 | should / 쿼리 텍스트 | 선호이지 금칙이 아님. 하드로 걸면 후보 고갈 |
| 가격대 | `must: lprice range` | 사용자 설정 시 |

```python
def build_filter(q: RetrievalQuery, layer_role: str) -> Filter:
    must = [FieldCondition(key="layer_role", match=MatchValue(value=layer_role))]
    for k, vals in q.must.items():
        must.append(FieldCondition(key=k, match=MatchAny(any=vals)))
    if q.price_range:
        must.append(FieldCondition(key="lprice", range=Range(gte=q.price_range[0], lte=q.price_range[1])))
    must_not = [FieldCondition(key=k, match=MatchAny(any=vals)) for k, vals in q.must_not.items()]
    return Filter(must=must, must_not=must_not)
```

**후보 고갈 대비 단계적 완화(relaxation ladder)**: 필터 적용 결과가 K 미만이면 should성 must부터 하나씩 풀어 재검색한다 (style must → should → 제거 순). must_not(기피 조건)은 **끝까지 유지**한다.

### 3-3. 기능별 어댑터

**① 오늘의 룩 (날씨 + 설정)**

1. `weather_tool` 결과 → 룰 테이블로 필터 변환. 기온 구간 → `season`+권장 `material`/`layer_role` 구성 (예: 최고 29℃ → 여름, 아우터 슬롯 생략 / 최저 3℃ → 겨울, 아우터 필수). 강수확률 ≥ 60% → `material must_not: ["스웨이드"]` 등. 이 매핑 테이블 자체가 지식 문서(knowledge 컬렉션)와 코드 상수의 이중 원천이 되지 않도록, **코드 상수를 단일 원천**으로 두고 지식 문서는 Stylist의 근거 설명용으로만 검색한다.
2. 채팅이 없으므로 쿼리 벡터는 사용자 설정(추구 스타일·피부톤 팔레트)을 직렬화한 텍스트로 생성: `"미니멀 스타일, 웜톤에 어울리는 색상, 여름 출근룩"`.
3. layer_role별(기본 상의/하의/신발/±아우터) 각각 `retrieve_items` 호출 → Stylist에 전달.

**② 추구미 추천 (채팅 + 설정)**

1. Orchestrator(LLM)가 채팅에서 슬롯 추출: `{추구_스타일:[], 기피_색:[], 기피_핏:[], TPO, 기타_자연어}`. 추출값은 태그 enum(STYLES 등)으로 정규화 — enum 밖 표현("꾸안꾸")은 매핑 테이블 또는 LLM 프롬프트에서 최근접 enum으로 변환.
2. 설정(프로필)의 기피 조건과 채팅의 기피 조건을 **합집합**으로 must_not에 넣는다. 채팅이 설정과 충돌하면(설정은 미니멀인데 "오늘은 스트릿하게") **채팅이 우선**.
3. `query_text` = 채팅 원문 + 정규화 슬롯 병기. 원문을 버리지 않는 것이 뉘앙스("잔잔한", "과하지 않은") 보존에 중요.

**③ 옷장 기반 추천 (채팅 + 설정)**

두 가지 질의 패턴을 구분한다.

- *"내 옷장에서 오늘 뭐 입지"* → `wardrobe` 컬렉션 검색 (must: `user_id`, 날씨 필터). ①과 동일 파이프라인, 컬렉션만 교체.
- *"이 셔츠에 어울리는 하의 추천(구매)"* → **크로스 컬렉션 검색**. 주의: 셔츠의 image 벡터로 하의를 검색하면 "셔츠와 비슷하게 생긴 하의"가 나온다(유사도 ≠ 어울림). 올바른 전략:

  ```
  기준 아이템(셔츠)의 태그를 payload에서 읽음
    → 호환 조건 생성: style 동일/인접, color는 조합 규칙(톤온톤 등)으로 후보 팔레트 산출,
      layer_role="하의", season 동일
    → 이 조건으로 products에서 필터 + 텍스트 쿼리("미니멀 화이트 셔츠에 어울리는 하의") 검색
    → Stylist가 기준 아이템과의 조합으로 최종 선별
  ```

  즉 **"어울림"은 벡터 유사도가 아니라 태그 호환 규칙 + Stylist 판단**으로 푼다. 벡터는 스타일 무드 정렬용 보조.

### 3-4. 네이버 쇼핑 검색 API의 위치 (실시간 fallback)

벡터스토어는 수집 시점 스냅샷이므로 커버리지 구멍이 생긴다. 다음 조건에서 네이버 검색 API를 실시간 fallback으로 쓴다: 필터+완화 후에도 후보 < K일 때, 또는 브랜드·구체 상품명 질의(벡터 검색이 약한 영역)일 때. 흐름은 `검색 API 호출 → attribute_extractor 규칙 태깅(경량) → 후보 합류`로 하고, LLM 태깅·임베딩·Qdrant 적재는 **비동기 후속 처리**로 넘겨 응답 latency(p95 < 5초)를 지킨다. 이렇게 하면 fallback이 곧 카탈로그 증분 수집이 된다.

### 3-5. 확장: 하이브리드 검색과 리랭킹 (2차)

1차 구현은 "필터 + dense 벡터"로 충분하다. 품질 병목이 확인되면:

- **하이브리드**: BGE-M3 sparse 벡터를 Qdrant sparse vector로 추가 → 브랜드명·고유명사 recall 개선. RRF로 dense/sparse 융합.
- **리랭킹**: 상위 50 → bge-reranker-v2-m3로 상위 10 재정렬. latency +100~300ms이므로 캐시와 함께 도입.

둘 다 컬렉션 스키마에 벡터 추가만 필요하므로, 1차 스키마 설계 단계에서 named vector 구조를 잡아두면 마이그레이션이 쉽다.

---

## 4. Django 통합 및 인터페이스

```
api/apps/recommend/
├── services/
│   ├── retriever.py      # retrieve_items / build_filter (본 문서 3절)
│   ├── filter_rules.py   # 기온→필터 룰 테이블, 색 조합 팔레트 규칙
│   └── embedder.py       # BGE-M3 텍스트 임베딩 클라이언트 (추론 서버 or 로컬)
ml/
├── embedding/            # 배치 임베딩 파이프라인 (RunPod 실행)
└── common/tag_schema.py  # SEASONS/STYLES/LAYER_ROLES enum — collector와 공용
```

- Qdrant 접속 정보(`QDRANT_URL`, `QDRANT_API_KEY`)는 `.env` → settings 주입.
- 쿼리 텍스트 임베딩은 요청마다 발생하므로 Redis 캐시(동일 슬롯 조합 키, TTL 짧게) + 모델 워밍업 적용.

## 5. 평가

- 태그 조합별 골든 쿼리셋(예: "여름/미니멀/형광 기피" × 20개) 구축 → precision@k, 기피 조건 누출률(must_not 위반 = 0이어야 함), 필터 완화 발동률 측정.
- 임베딩 모델 비교(FashionSigLIP text vs BGE-M3)는 동일 골든셋으로 A/B 후 확정.

## 6. 미확정/확인 필요

1. **S3 `skn28-cozy` 폴더 구조 실측 확인** — 본 문서는 "이미지 + JSON 원본" 가정으로 작성. 실제 prefix 구조(카테고리별? 수집일자별?)에 맞춰 2-4절 ②의 배치 목록 조회 방식을 확정해야 함.
2. 텍스트 임베딩 모델 확정 (BGE-M3 vs multilingual-e5 vs OpenAI API — 셀프호스팅 여부 포함)
3. 옷장 태깅용 Vision LLM 비용/모델 (기존 OPENAI_MODEL 재사용 여부)
4. warmth_level 필드 추가 여부 — 현재 naver_product에 없음. season만으로 시작하고 필요 시 태깅 확장 권장.

---

_마지막 업데이트: 2026-07-13_
