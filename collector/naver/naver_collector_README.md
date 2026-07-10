# 네이버 쇼핑 의류 상품 Collector

네이버 쇼핑 검색 API로 의류 상품을 수집하고, 컨플루언스
["의류 상품 데이터 카테고리-태그 매핑 문서"](https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/14286849)
스키마에 맞게 분류·태깅해서 PostgreSQL에 저장한다.

## 파이프라인

```
키워드 자동 생성 (keywords.py, 문서 소분류 기반)
  → 네이버 쇼핑 검색 API 호출 + 페이징 (naver_collector_db.py)
  → 노이즈 필터 (category1 ∉ {패션의류, 패션잡화} 제외) + productId 중복 제거
  → 네이버 category1~4 → 문서 분류 매핑 (category_mapping.py, 실패 시 키워드 분류)
  → title 규칙 추출: color/fit/sleeve/pattern/material/length (attribute_extractor.py)
  → LLM 태깅: season/style/usage/layer_* + 누락 속성 (llm_tagger.py, OpenAI)
  → naver_product upsert  ※ 태깅은 insert 전에 수행
```

## 테이블

| 테이블 | 역할 |
| --- | --- |
| `naver_product` | 상품 원본 + 문서 분류/태그. `naver_product_id` unique upsert |
| `naver_product_size` | 사이즈별 치수/측정값 하위 테이블 (`product_id` FK). **스키마만 정의** — 네이버 검색 API는 치수를 제공하지 않으므로 상세페이지 수집·수동 입력 등 별도 경로로 채운다 |

태깅 메타: `tag_source`(필드별 rule/llm 출처), `tagging_status`(pending/tagged/failed),
`tagging_used_image`(이미지 태깅 여부).

## 실행

```bash
pip install -r requirements.naver.txt
cp ../../.env.example ../../.env   # 값 채우기 (NAVER_*, OPENAI_API_KEY, POSTGRES_*)

python naver_collector_db.py --init-schema            # 테이블 생성 (로컬용)
python naver_collector_db.py --job collect            # 전체 키워드 수집+태깅
python naver_collector_db.py --job collect --category-large 상의
python naver_collector_db.py --job collect --keyword "린넨 셔츠" --limit 30 --dry-run
python naver_collector_db.py --job collect --skip-llm # 태깅 없이 수집 (pending 저장)
python naver_collector_db.py --job retag              # pending/failed 재태깅
python naver_collector_db.py --scheduler              # 매일 03:00 KST 자동 수집
```

Docker:

```bash
docker compose -f docker-compose.naver.yml up -d --build
```

## LLM 이미지 태깅 (`NAVER_LLM_IMAGE_MODE`)

- `auto`(기본): 상품명만으로 style/color 판단이 안 되는 경우에만 상품 이미지를 포함해 재시도 → 비용 최소화
- `always`: 항상 이미지 포함 (정확도↑ 비용↑)
- `never`: 텍스트만

## API 제약 (네이버 쇼핑 검색)

- 키워드당 최대 약 1,000건 (`display` 100, `start` ≤ 1000) → 커버리지는 키워드 다양화로 확보.
  `.env`의 `NAVER_KEYWORD_GENDER_PREFIXES=남성,여성` 으로 키워드를 성별 확장할 수 있다.
- 일 25,000 호출 한도. 429 응답 시 지수 백오프 재시도.
- 응답 필드는 title/link/image/lprice/hprice/mallName/productId/productType/brand/maker/category1~4 뿐이므로
  season/style/usage 등 문서 태그는 규칙 추출 + LLM 태깅으로 생성한다.

## 운영 이관 메모 (CLAUDE.md 규칙)

- DDL(`db.py`)은 로컬 개발용. AWS(RDS) 이관 시 Django model/migration으로 옮긴다.
- 시크릿은 .env → AWS Secrets Manager/SSM으로 대체. 코드에 하드코딩 금지.
- RunPod/로컬 전용 경로 없음. DB 접속은 전부 환경변수로 추상화되어 있다.
