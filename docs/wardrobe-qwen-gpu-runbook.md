# Qwen 옷장 태깅 GPU 배포·장애 확인

대상 서비스는 `docker-compose.gpu.yml`의 `wardrobe-item-tagger`다. 시크릿은 루트
`.env` 또는 Infisical로 주입하며 로그·Git에 값을 출력하지 않는다.

## 배포

API가 `processing` 콜백을 받을 수 있도록 API를 먼저 배포한 뒤 GPU 워커를 갱신한다.

```bash
git checkout openweight
git pull --ff-only origin openweight

docker compose -f docker-compose.gpu.yml build wardrobe-item-tagger
docker compose -f docker-compose.gpu.yml up -d \
  --no-deps --force-recreate wardrobe-item-tagger
```

버전과 기동 상태를 확인한다.

```bash
docker exec skn28-wardrobe-item-tagger python -c \
  'import torch, transformers; print(torch.__version__, transformers.__version__)'
docker compose -f docker-compose.gpu.yml ps wardrobe-item-tagger
docker logs --since 5m --tail=100 skn28-wardrobe-item-tagger
```

기준 버전은 PyTorch `2.6.0+cu124`, Transformers `4.57.6`이다. 새 사진 한 장을
등록해 상태가 `PENDING → PROCESSING → DONE`으로 바뀌는지 확인한다. 기존 dead
queue 작업은 자동 재실행되지 않으므로 배포 검증에는 새 `job_id`를 사용한다.

## 실패 상태와 큐 확인

워커는 세 번 실패하면 작업을 `wardrobe:item-jobs:dead`로 옮기고 API에 `FAILED`
콜백을 보낸다. API 상태 응답의 `error_message`와 워커 로그를 함께 확인한다.

```bash
docker exec skn28-wardrobe-item-tagger python -c '
import config
from services.queue import _redis
r = _redis()
for key in (config.PENDING_KEY, config.PROCESSING_KEY, config.DEAD_KEY):
    print(key, r.llen(key))
'
```

`PENDING`이 20분을 넘으면 상태 조회 시 `FAILED(processing_timeout)`로 바뀌고,
아직 소비되지 않은 Redis 대기 작업도 제거된다.

## 자주 발생하는 장애

### `torch.load`가 PyTorch 2.6 이상을 요구

실행 컨테이너가 이전 이미지인지 확인한다.

```bash
git rev-parse --short HEAD
head -n 1 image-processor/Dockerfile.qwen
docker exec skn28-wardrobe-item-tagger python -c 'import torch; print(torch.__version__)'
```

버전이 다르면 `build --pull --no-cache` 후 `up --force-recreate`한다.

### `no space left on device`

```bash
df -h / /home /var/lib/docker
docker system df
docker builder prune -af
docker image prune -f
```

빌드 캐시와 dangling 이미지만 제거한다. PostgreSQL·Qdrant·Hugging Face 데이터가
삭제될 수 있으므로 `docker volume prune`과 `docker system prune -a --volumes`는
사용하지 않는다.

### PostgreSQL이 `unhealthy`

```bash
docker logs --tail=200 skn28-postgres
```

`POSTGRES_PASSWORD is not specified`가 나오면 `.env`의 `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`가 비어 있지 않은지 확인하고 DB 컨테이너만
재생성한다. 기존 데이터가 필요한 환경에서는 볼륨을 삭제하지 않는다.

```bash
docker compose -f docker-compose.yml --profile api up -d --force-recreate db
docker compose -f docker-compose.yml --profile api up -d api
```

