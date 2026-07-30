# 쇼핑 상품 이미지+텍스트 임베딩 worker

네이버·11번가 collector가 등록한 신규 상품 중 **태깅이 완료된 작업**만 외부
GPU worker가 선점해 다음 순서로 처리한다. 태깅 로직은 indexer에 포함하지 않는다.
collector는 태깅 결과를 DB에 저장한 뒤 인증된 HTTP API로 drain 시작 신호만
보내며 상품 데이터나 이미지를 HTTP 요청에 포함하지 않는다.
GPU worker는 PostgreSQL에 직접 연결하지 않고 Django `catalog` 내부 API를 통해
작업을 선점하고 상품 데이터 및 처리 상태를 주고받는다. S3와 Qdrant에는 직접
연결한다.

```text
태깅 완료 + product_embedding_job(pending)
  → catalog 내부 API로 작업 선점 + 상품 데이터 조회
  → 외부 이미지 다운로드·검증
  → S3 고정 키에 JPEG 원본 저장
  → catalog 내부 API로 S3 key/checksum 체크포인트
  → Marqo-FashionSigLIP 이미지 임베딩(768d)
  → BGE-M3 한국어 텍스트 임베딩(1024d)
  → Qdrant products_v1 upsert
  → catalog 내부 API로 상품·작업 상태 completed
```

기존 DB 상품은 `product_embedding_job` 행이 없으므로 자동 처리되지 않는다.
운영 신규 파이프라인을 먼저 검증·배포한 뒤 별도 백필 기능으로 등록해야 한다.

## 처리 대상

worker는 `product_embedding_job.status=pending`이면서 원본 상품의
`tagging_status=tagged`인 작업만 가져간다. 아직 태깅되지 않은 작업은 건드리지
않고 다음 일일 실행까지 기다린다. 따라서 Batch와 Sync 어느 모드로 수집하더라도
최종 태그가 저장된 뒤에만 임베딩한다.

이미 DB에 `image_s3_key`와 `image_checksum`이 있고 S3 객체가 유효하면 외부 상품
이미지를 다시 다운로드하거나 업로드하지 않는다. S3 객체가 없거나 체크섬이
일치하지 않을 때만 원본 URL에서 복구한다.

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

# Django API와 GPU worker에 같은 내부 API token을 설정한다.
PRODUCT_INDEXER_INTERNAL_TOKEN=<random-catalog-api-token>
# GPU worker에 Django catalog 내부 API URL을 설정한다.
PRODUCT_CATALOG_API_URL=https://<api-host>/api/v1/internal/catalog/product-embeddings
PRODUCT_CATALOG_API_TIMEOUT_SECONDS=30

# collector와 GPU API에 같은 token을 설정한다.
PRODUCT_INDEXER_TRIGGER_TOKEN=<random-secret-token>
# collector 서버에만 GPU API의 전체 trigger URL을 설정한다.
PRODUCT_INDEXER_TRIGGER_URL=https://<gpu-host>/v1/product-indexer/drain
PRODUCT_INDEXER_TRIGGER_TIMEOUT_SECONDS=10
PRODUCT_INDEXER_TRIGGER_MAX_RETRIES=2

# GPU API bind
PRODUCT_INDEXER_API_HOST=0.0.0.0
PRODUCT_INDEXER_API_PORT=8080
```

RunPod에서는 catalog API·S3·Qdrant에 필요한 자격증명을 환경변수/시크릿으로
주입한다. PostgreSQL 접속 정보는 GPU 서버에 주입하지 않으며 자격증명을
이미지에 포함하지 않는다.

## 실행

마이그레이션을 먼저 적용한다.

```bash
cd api
python manage.py migrate
```

RunPod 등 GPU 환경에서 worker를 직접 실행할 수도 있다.

```bash
cd indexer
pip install -r requirements.txt
python product_indexer.py --once --batch-size 2
python product_indexer.py --drain --batch-size 32
```

GPU 서버용 Docker 이미지는 기본적으로 HTTP API를 실행한다.

```bash
docker build -f indexer/Dockerfile.product-indexer -t skn28-product-indexer indexer/
docker run --gpus all --env-file .env -p 8080:8080 skn28-product-indexer
```

상태 확인:

```bash
curl http://<gpu-host>:8080/health
```

수동 trigger:

```bash
curl -X POST https://<gpu-host>/v1/product-indexer/drain \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"source":"manual","reason":"manual"}'
```

API는 `202 Accepted`를 즉시 반환하고 별도 subprocess가 `--drain`을 수행한다.
이미 같은 GPU API 인스턴스에서 drain이 실행 중이면 `already_running`을 반환한다.
여러 worker가 동시에 실행되더라도 catalog API의 행 잠금으로 같은 작업을 중복
선점하지 않는다.

API를 거치지 않고 Docker에서 일회성 drain을 실행하려면 entrypoint를 덮어쓴다.

```bash
docker run --gpus all --env-file .env --entrypoint python \
  skn28-product-indexer /app/product_indexer.py --drain --batch-size 32
```

`--drain`은 모델을 한 번만 로드하고 준비된 작업을 배치 단위로 모두 처리한 뒤
종료한다. 재시도 대기 시간이 기본 120초 이내인 작업도 같은 실행에서 처리한다.
전체 실행은 기본 120분으로 제한되며 남은 작업은 다음 trigger에서 이어서 처리한다.

운영에서는 GPU API를 HTTPS reverse proxy 또는 private network 뒤에 두고 collector
서버에서만 접근하도록 제한한다. HTTP trigger 장애에 대비해 AWS EventBridge,
EC2 cron 또는 RunPod 스케줄러에서 하루 1회 수동 drain 명령을 실행하는 fallback을
둘 수 있다.

## 상태와 재시도

- 작업: `pending → processing → completed | failed`
- 태깅 완료 작업만 `pending → processing`으로 선점한다.
- 기본값은 최초 1회 + 재시도 2회(총 3회)다.
- 재시도 대기는 30초, 60초처럼 지수 증가한다.
- S3 저장 성공 직후 catalog API로 key/checksum을 남겨 재시도에서 재사용한다.
- 한 상품이 실패해도 다음 작업을 계속 처리한다.
- worker 비정상 종료로 `processing`에 남은 작업은 기본 30분 후 복구한다.
- 잘못된 이미지, 존재하지 않는 상품, 버전 불일치는 즉시 `failed`로 기록한다.
