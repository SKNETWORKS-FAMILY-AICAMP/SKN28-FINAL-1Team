# 쇼핑 상품 이미지+텍스트 임베딩 worker

네이버·11번가 collector가 **새로 INSERT한 상품**을 DB 적재 직후 작업으로
등록하고, 별도 GPU worker가 다음 순서로 처리한다.

```text
collector 상품 INSERT
  → product_embedding_job(pending)
  → 외부 이미지 다운로드·검증
  → S3 고정 키에 JPEG 원본 저장
  → Marqo-FashionSigLIP 이미지 임베딩(768d)
  → BGE-M3 한국어 텍스트 임베딩(1024d)
  → Qdrant products_v1 upsert
  → 상품·작업 상태 completed
```

기존 DB 상품은 `product_embedding_job` 행이 없으므로 자동 처리되지 않는다.
운영 신규 파이프라인을 먼저 검증·배포한 뒤 별도 백필 기능으로 등록해야 한다.

## 태깅과 재임베딩

collector의 기본 태깅 모드는 OpenAI Batch이므로 최초 저장 시 태그가 완성되지
않을 수 있다. 신규 상품은 DB 적재 직후 카테고리·상품명·규칙 태그로 먼저
이미지+텍스트 임베딩된다. Batch 태깅이 완료되면 해당 신규 상품의 기존 작업만
generation을 올려 다시 처리한다. 작업 행이 없는 과거 상품은 이 과정에서도
자동 등록되지 않는다.

## Qdrant 스키마

- 컬렉션: `PRODUCT_QDRANT_COLLECTION`(기본 `products_v1`)
- named vector:
  - `image`: Marqo-FashionSigLIP, 모델 출력 차원(기본 768)
  - `text`: BGE-M3 dense, 모델 출력 차원(기본 1024)
- point ID: UUID5(`shopping-product:{source}:{external_product_id}`)
- `source=naver|eleven` payload로 쇼핑몰을 구분한다.
- 기존 ETRI PoC 컬렉션 `fashion_items`와 섞지 않는다.

## 필수 설정

루트 `.env`에 다음 값을 설정한다.

```dotenv
QDRANT_URL=http://<qdrant-host>:6333
QDRANT_API_KEY=<configured-api-key>
PRODUCT_QDRANT_COLLECTION=products_v1

PRODUCT_IMAGE_S3_BUCKET=<product-image-bucket>
PRODUCT_IMAGE_S3_PREFIX=products

PRODUCT_IMAGE_EMBED_MODEL=hf-hub:Marqo/marqo-fashionSigLIP
PRODUCT_TEXT_EMBED_MODEL=BAAI/bge-m3
PRODUCT_TEXT_MODEL_REVISION=<huggingface-commit-hash>
PRODUCT_EMBEDDING_VERSION=marqo-fashionSigLIP+bge-m3-v1
PRODUCT_INDEXER_MAX_RETRIES=2
```

RunPod에서는 S3·Qdrant·PostgreSQL에 필요한 자격증명을 환경변수/시크릿으로
주입한다. 자격증명을 이미지에 포함하지 않는다.

## 실행

마이그레이션을 먼저 적용한다.

```bash
cd api
python manage.py migrate
```

RunPod 등 GPU 환경에서 worker를 실행한다.

```bash
cd indexer
pip install -r requirements.txt
python product_indexer.py --once --batch-size 2
python product_indexer.py --batch-size 32
```

Docker:

```bash
docker build -f indexer/Dockerfile.product-indexer -t skn28-product-indexer indexer/
docker run --gpus all --env-file .env skn28-product-indexer --once --batch-size 2
```

통합 compose에서 GPU 런타임을 사용할 수 있으면:

```bash
docker compose --profile embedding up -d --build
```

## 상태와 재시도

- 작업: `pending → processing → completed | failed`
- 기본값은 최초 1회 + 재시도 2회(총 3회)다.
- 재시도 대기는 30초, 60초처럼 지수 증가한다.
- 한 상품이 실패해도 다음 작업을 계속 처리한다.
- worker 비정상 종료로 `processing`에 남은 작업은 기본 30분 후 복구한다.
- 잘못된 이미지, 존재하지 않는 상품, 버전 불일치는 즉시 `failed`로 기록한다.
