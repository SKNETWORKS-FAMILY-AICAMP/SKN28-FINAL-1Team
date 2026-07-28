# SKN28-FINAL-1Team — AI 개인화 패션 추천 서비스

사용자의 옷장을 출발점으로 날씨·TPO·체형을 고려한 개인화 패션 추천을 제공하는 AI 서비스.
서비스 기획·아키텍처는 [docs/프로젝트_소개.md](docs/프로젝트_소개.md), 개발 규칙은 [CLAUDE.md](CLAUDE.md) 참고.

> 이 문서는 **현재 구현된 범위**만 다룬다. 추천 엔진(RAG)·ml/ 모듈은 아직 개발 전이다.

## 현재 구현 상태

| 컴포넌트 | 상태 | 설명 |
| --- | --- | --- |
| `api/` Django REST API | ✅ | 소셜 로그인(네이버/카카오/구글) + JWT 발급, 내 정보 조회/수정 |
| `api/apps/catalog·weather` | ✅ | collector 테이블의 스키마 소유 (Django migration) |
| `collector/naver/` | ✅ | 네이버 쇼핑 API 상품 수집 + 규칙/LLM 태깅 → PostgreSQL |
| `collector/weather/` | ✅ | 기상청 APIHub 실황·단기·중기 예보 수집 → PostgreSQL |
| `docker-compose.yml` | ✅ | db + migrate + api + collector 2종 통합 (profiles 선택 실행) |
| `apps/recommend`, `ml/` | ⬜ | 예정 |

## 기술 스택

Python 3.11 · Django/DRF · simplejwt · PostgreSQL 16 · OpenAI API(상품 태깅) · Docker Compose

## 디렉터리 구조

```
├── docker-compose.yml       # 통합 compose (profiles: api / weather / naver / all)
├── .env.example             # 환경변수 템플릿 → 루트 .env 하나로 전체 관리
├── api/                     # Django REST API 서버 (README 참고)
│   ├── config/settings/     # base / dev / prod 분리
│   └── apps/
│       ├── users/           # 소셜 로그인 + JWT
│       ├── catalog/         # naver_product, naver_product_size 스키마
│       └── weather/         # weather_* 6개 테이블 스키마
├── collector/
│   ├── naver/               # 상품 수집기 (README 참고)
│   └── weather/             # 날씨 수집기 (README 참고)
└── docs/                    # 기획·아키텍처 문서
```

**스키마 소유권**: 모든 테이블의 DDL은 Django migration(`api/apps/*`)이 관리한다.
collector는 raw SQL upsert만 수행하며, 실행 전 migrate가 선행되어야 한다.

## 빠른 시작 (Docker)

```bash
infisical login                                    # 최초 1회, US(app.infisical.com) 리전 선택
infisical export --env=dev --output-file=./.env    # Infisical → 루트 .env 생성 (compose가 이 파일을 읽는다)

docker compose --profile api up -d --build      # db + migrate + api (:8000)
docker compose --profile naver up -d --build    # db + migrate + 네이버 수집기
docker compose --profile all up -d --build      # 전부
```

- 실행 순서는 자동 보장: `db(healthy) → migrate(Django migration) → api/collector`
- `.env`에 `COMPOSE_PROFILES=api,naver`를 지정하면 `docker compose up -d`만으로 동작
- **API 실행 모드는 `DJANGO_SETTINGS_MODULE`로 제어** (구 `docker-compose.swagger.yml`은 병합·폐기됨):
  `config.settings.prod`(기본) / `dev` / `swagger`(+Swagger UI `/api/docs/`) / `swagger_noauth`(+인증 우회, 로컬 전용).
  `.env`는 Infisical로 관리되므로 모드 변경은 Infisical의 dev 환경 값 수정 또는
  일회성 실행 시 셸 환경변수 오버라이드(`DJANGO_SETTINGS_MODULE=config.settings.swagger docker compose up -d`)로 한다.
  ⚠️ `swagger_noauth`는 인증이 꺼지므로 운영 환경에 절대 설정 금지.
- 호스트 5432 포트가 사용 중이면 `POSTGRES_HOST_PORT`로 db 공개 포트를 변경
- 어떤 프로필이든 migrate가 api 이미지로 실행되므로 `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` 필요
- 컨테이너는 루트 `.env` 파일에서 값을 읽으므로(compose `env_file`), `infisical run -- docker compose up`만으로는 시크릿이 컨테이너에 전달되지 않는다. 반드시 위처럼 `infisical export`로 `.env`를 먼저 생성한다. 원리는 [docs/guide/INFISICAL_GUIDE.md](docs/guide/INFISICAL_GUIDE.md)를 따른다.
- `.env`는 `infisical export`로만 생성/갱신하고 손으로 편집하지 않는다. Infisical 값 변경 후에는 export를 다시 실행하고 `docker compose up -d --force-recreate`로 반영한다. 커밋 금지.

## 로컬 개발 (Docker 없이)

```bash
# DB만 컨테이너로
docker compose --profile db up -d

cd api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver          # 기본 settings: config.settings.dev

python manage.py test apps.users    # 테스트
```

collector 실행 (migrate 선행 필수):

```bash
cd collector/naver
pip install -r requirements.naver.txt
python naver_collector_db.py --job collect --keyword "린넨 셔츠" --limit 30 --dry-run
```

## 주요 API (구현분)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/v1/auth/{naver\|kakao\|google}/login/` | authorization code → JWT 발급 |
| POST | `/api/v1/auth/token/refresh/` | refresh → 새 access 토큰 |
| GET/PATCH | `/api/v1/users/me/` | 내 정보 조회/수정 |

상세 문서: [api/README.md](api/README.md) ·
[collector/naver/naver_collector_README.md](collector/naver/naver_collector_README.md) ·
[collector/weather/weather_collector_README.md](collector/weather/weather_collector_README.md)

## 환경변수

api·collector·compose가 필요한 시크릿은 Infisical로 관리한다.

```bash
infisical run --env=dev -- <실행할 명령>            # 로컬 직접 실행 (runserver, 스크립트 등)
infisical export --env=dev --output-file=./.env    # Docker Compose 실행 전 .env 생성
```

- Infisical 프로젝트: `skn28-final-1team`
- Organization ID: `1da5b459-505d-46da-88eb-34c4d5485486`
- Project ID / workspaceId: `a9752e10-915a-410e-a714-e89f540ce5e8`
- Project ID는 Infisical URL의 `/projects/secret-management/<Project ID>/overview` 부분이나 프로젝트 Settings 탭에서 확인한다.
- Organization ID는 URL의 `/organizations/<Organization ID>/...` 부분이나 Organization Settings에서 확인한다.

주요 그룹: `POSTGRES_*`(DB), `DJANGO_*`/`JWT_*`(api), `*_OAUTH_*`(소셜 로그인),
`NAVER_CLIENT_*`(쇼핑 검색 API), `OPENAI_*`(상품 태깅), `KMA_*`(기상청).
자세한 항목과 설명은 `.env.example` 주석 참고. **실제 `.env`는 커밋 금지.**


# 카테고리별 자동 비율 상품 이미지 생성

## 파일 배치

```text
SKN28-FINAL-1Team/
├─ .env
├─ common/
│  └─ product_image_generator.py
└─ test/
   └─ generate_product_images.py
```

## `.env`

```env
OPENAI_API_KEY=sk-실제키
OPENAI_IMAGE_MODEL=gpt-image-1
```

## 설치

```bash
python -m pip install openai python-dotenv pillow
```

## 바지만 다시 생성

현재 test 폴더에서 실행할 경우:

```bat
python -m generate_product_images output\grounded_sam2\sample\items.json --mode ecommerce --only-category 하의 --size auto --overwrite
```

프로젝트 루트에서 실행할 경우:

```bat
python -m test.generate_product_images test\output\grounded_sam2\sample\items.json --mode ecommerce --only-category 하의 --size auto --overwrite
```

## 전체 다시 생성

```bat
python -m generate_product_images output\grounded_sam2\sample\items.json --mode ecommerce --size auto --overwrite
```
