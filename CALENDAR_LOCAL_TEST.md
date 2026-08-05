# 캘린더 로컬 테스트 가이드

캘린더 사진 등록부터 기존 옷장 이미지 프로세서 처리, `WardrobeItem` 생성,
캘린더 자동 연결까지 로컬에서 검증하는 절차다.

## 1. 테스트 범위

이 문서에서는 다음 흐름을 검증한다.

```text
캘린더 사진 등록 API
→ 캘린더·옷장 S3 원본 저장
→ WardrobeUploadJob 생성
→ wardrobe:jobs enqueue
→ 기존 image-processor worker 처리
→ 기존 wardrobe callback 호출
→ WardrobeItem 생성
→ CalendarWardrobeItem N:N 자동 연결
→ 캘린더 COMPLETED
```

프론트엔드 없이 API만 호출하며, 캘린더 전용 queue·consumer·callback은 사용하지
않는다.

## 2. 사전 준비

- Docker Desktop
- Conda `final` 환경
- PostgreSQL, Redis, Qdrant용 Docker 이미지
- 실제 S3 버킷과 접근 가능한 AWS 자격증명
- Gemini API 키
- 테스트할 JPG, PNG, WebP 또는 HEIC 이미지 한 장

로컬 E2E 테스트도 S3와 Gemini를 실제 호출한다. 자동 테스트만 실행할 때는 S3와
Gemini가 필요하지 않다.

## 3. 환경변수 설정

저장소 루트의 `.env`에 아래 값을 설정한다. 실제 키와 비밀번호는 커밋하지 않는다.

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=fashion_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me

REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=change-me
WARDROBE_JOB_QUEUE=wardrobe:jobs

WARDROBE_S3_BUCKET=your-local-test-bucket
CALENDAR_S3_BUCKET=your-local-test-bucket
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

WARDROBE_CALLBACK_URL=http://localhost:8000/api/v1/internal/wardrobe/callback/
WARDROBE_INTERNAL_TOKEN=local-calendar-test-token

GEMINI_API_KEY=...
WORKER_EMBED_ENABLED=0
```

로컬에서는 `WARDROBE_S3_BUCKET`과 `CALENDAR_S3_BUCKET`에 같은 버킷을 사용해도
된다. 객체는 각각 `wardrobe/`, `calendar/` prefix로 분리된다.

`WORKER_EMBED_ENABLED=0`은 FashionSigLIP/BGE 모델 다운로드와 임베딩을 생략한다.
의류 추출·이미지 생성·태깅에는 Gemini API가 계속 사용된다.

## 4. 자동 테스트

자동 테스트는 S3·Redis·Gemini 호출을 mock 처리한다. PostgreSQL 테스트 DB는
필요하므로 DB 컨테이너를 먼저 실행한다.

```bash
cd /e/workspace/SKN28-FINAL-1Team
docker compose up -d db

conda activate final
export PYTHONUTF8=1

cd api
python manage.py test apps.style_calendar.tests --verbosity 2
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py sqlmigrate style_calendar 0002
```

정상 기준은 다음과 같다.

- 캘린더 테스트 69개 통과
- Django system check 오류 없음
- 추가 마이그레이션 변경 없음
- `0002` SQL에 `wardrobe_upload_job_id`의 UNIQUE FK 추가와 `calendar_item`
  테이블 제거가 표시됨

## 5. E2E 테스트용 인프라 실행

첫 번째 Git Bash에서 실행한다.

```bash
cd /e/workspace/SKN28-FINAL-1Team
docker compose up -d db redis qdrant
docker compose ps
```

`db`, `redis`, `qdrant`가 실행 중인지 확인한다.

## 6. API 실행

두 번째 Git Bash에서 실행한다.

```bash
cd /e/workspace/SKN28-FINAL-1Team/api

conda activate final
export PYTHONUTF8=1
export DJANGO_SETTINGS_MODULE=config.settings.swagger_noauth

python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

`swagger_noauth`는 로컬 개발용 자동 로그인 설정이다. 소셜 로그인 없이 보호된 API를
호출할 수 있다. 운영 환경에서는 사용하지 않는다.

- Swagger UI: <http://localhost:8000/api/docs/>

## 7. 캘린더 사진 등록

세 번째 Git Bash에서 실행한다. 사진 경로와 날짜는 로컬 환경에 맞게 변경한다.

```bash
curl -X POST "http://localhost:8000/api/v1/calendars/photo/" \
  -F "image=@/e/test-images/outfit.jpg" \
  -F "date=2026-08-20" \
  -F "schedule=로컬 테스트" \
  -F "tpo=데이트" \
  -F "hashtags=테스트"
```

정상 응답은 HTTP `202 Accepted`이며 응답의 `id`가 캘린더 UUID다.

```json
{
  "id": "캘린더 UUID",
  "date": "2026-08-20",
  "source_type": "PHOTO_UPLOAD",
  "status": "REGISTERED",
  "wardrobe_items": []
}
```

같은 사용자의 같은 날짜 캘린더가 이미 있으면 `409 Conflict`가 반환된다. 이 경우
다른 날짜로 다시 요청한다.

## 8. 기존 옷장 Queue 사용 확인

worker를 실행하기 전에 `wardrobe:jobs` 길이를 확인한다.

```bash
cd /e/workspace/SKN28-FINAL-1Team

docker compose exec redis sh -lc \
  'redis-cli -a "$REDIS_PASSWORD" LLEN wardrobe:jobs'
```

worker가 아직 소비하지 않았다면 일반적으로 `1`이 출력된다. 별도의
`calendar:jobs` queue는 사용하지 않는다.

## 9. 기존 image-processor worker 실행

네 번째 Git Bash에서 실행한다.

```bash
cd /e/workspace/SKN28-FINAL-1Team/image-processor

conda activate final
export PYTHONUTF8=1
export WORKER_EMBED_ENABLED=0

python worker.py
```

worker 로그에서 다음 단계를 확인한다.

1. `wardrobe:jobs` 작업 수신
2. 원본 이미지 S3 다운로드
3. 패션 아이템 열거·이미지 생성·태깅
4. 옷장 S3 경로에 아이템 결과와 manifest 저장
5. `/api/v1/internal/wardrobe/callback/` 호출
6. queue ack

## 10. 처리 상태 확인

사진 등록 응답의 캘린더 UUID를 사용한다.

```bash
curl "http://localhost:8000/api/v1/calendars/캘린더_UUID/processing-status/"
```

정상 완료 예시는 다음과 같다.

```json
{
  "calendar_id": "캘린더 UUID",
  "status": "COMPLETED",
  "processing_required": true,
  "is_terminal": true,
  "result_available": true,
  "item_counts": {
    "total": 2,
    "extracted": 2,
    "failed": 0
  },
  "failure": null
}
```

worker가 아직 처리하지 않았다면 `REGISTERED` 상태가 유지되는 것이 정상이다.

## 11. 자동 옷장 등록·캘린더 연결 확인

캘린더 상세 조회:

```bash
curl "http://localhost:8000/api/v1/calendars/캘린더_UUID/"
```

미확정 옷장 아이템 조회:

```bash
curl "http://localhost:8000/api/v1/wardrobe/items/?confirmed=false"
```

다음을 확인한다.

- 이미지 프로세서가 찾은 옷마다 실제 `WardrobeItem`이 생성됨
- 생성된 아이템의 `confirmed`가 `false`임
- 캘린더 상세의 `wardrobe_items`에 같은 옷장 아이템 ID가 있음
- 캘린더 대표 이미지는 사용자가 올린 원본 사진을 유지함
- 직접 선택한 기존 옷장 아이템이 있었다면 자동 생성 아이템이 그 뒤에 추가됨

## 12. DB 직접 확인

```bash
cd /e/workspace/SKN28-FINAL-1Team

docker compose exec db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT
    ce.id AS calendar_id,
    ce.date,
    ce.status AS calendar_status,
    wuj.id AS job_id,
    wuj.status AS job_status,
    COUNT(cwi.id) AS linked_item_count
FROM calendar_entry ce
LEFT JOIN wardrobe_upload_job wuj
    ON wuj.id = ce.wardrobe_upload_job_id
LEFT JOIN calendar_wardrobe_item cwi
    ON cwi.calendar_id = ce.id
GROUP BY ce.id, ce.date, ce.status, wuj.id, wuj.status
ORDER BY ce.created_at DESC
LIMIT 10;
"'
```

정상 완료된 사진 캘린더는 `calendar_status=COMPLETED`, `job_status=DONE`이며
`linked_item_count`가 처리 성공 아이템 수만큼 증가한다.

## 13. 장애 확인

### 캘린더가 REGISTERED에서 멈춤

- worker 실행 여부 확인
- `REDIS_URL`과 `REDIS_PASSWORD` 확인
- `wardrobe:jobs`와 processing queue 확인

```bash
docker compose exec redis sh -lc \
  'redis-cli -a "$REDIS_PASSWORD" LLEN wardrobe:jobs'

docker compose exec redis sh -lc \
  'redis-cli -a "$REDIS_PASSWORD" LLEN wardrobe:jobs:processing'
```

### 사진 등록 API가 503 반환

- `WARDROBE_S3_BUCKET`, `CALENDAR_S3_BUCKET` 확인
- AWS 자격증명과 S3 Put/Get/Copy/Delete/List 권한 확인
- Redis 연결과 비밀번호 확인

### callback이 403 반환

API와 worker가 읽는 `WARDROBE_INTERNAL_TOKEN` 값이 같은지 확인한다.

### callback 연결 실패

`WARDROBE_CALLBACK_URL`이 다음 로컬 주소인지 확인한다.

```text
http://localhost:8000/api/v1/internal/wardrobe/callback/
```

### dead queue 확인

```bash
docker compose exec redis sh -lc \
  'redis-cli -a "$REDIS_PASSWORD" LRANGE wardrobe:jobs:dead 0 -1'
```

## 14. 테스트 종료

API와 worker는 각각 `Ctrl+C`로 종료한다. Docker 서비스는 다음 명령으로 중지한다.

```bash
cd /e/workspace/SKN28-FINAL-1Team
docker compose stop db redis qdrant
```

데이터까지 삭제하려면 별도 합의 없이 `docker compose down -v`를 실행하지 않는다.
`-v`는 PostgreSQL·Redis·Qdrant 볼륨 데이터를 삭제한다.
