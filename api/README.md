# API 서버 (Django REST Framework)

패션 추천 서비스 백엔드. CLAUDE.md 권장 구조(설정 분리 + apps/)를 따른다.

```
api/
├── manage.py                  # 기본 settings: config.settings.dev
├── requirements.txt
├── config/
│   ├── settings/
│   │   ├── base.py            # 공통 (루트 .env 로드, DB, DRF, JWT, OAuth)
│   │   ├── dev.py             # DEBUG=True, Browsable API
│   │   └── prod.py            # AWS 배포용 (HTTPS, 시크릿 필수화)
│   ├── urls.py                # /admin, /api/v1/
│   └── asgi.py / wsgi.py      # 기본 settings: config.settings.prod
└── apps/
    ├── catalog/               # naver_product / naver_product_size (collector/naver가 사용)
    ├── weather/               # weather_* 6개 테이블 (collector/weather가 사용)
    └── users/                 # 사용자 + 소셜 로그인
        ├── models.py          # User(커스텀), SocialAccount
        ├── serializers.py
        ├── views.py           # SocialLoginView, MeView
        ├── urls.py
        ├── services/
        │   ├── oauth.py       # naver/kakao/google code→token→profile
        │   └── accounts.py    # 프로필 → User/SocialAccount 매핑
        └── tests.py           # OAuth mock 테스트
```

## 실행

환경변수는 **프로젝트 루트의 `.env`** 를 사용한다 (`base.py`가 자동 로드).

```bash
cd api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 루트 .env에 POSTGRES_*, DJANGO_SECRET_KEY, *_OAUTH_* 값 설정 후
python manage.py migrate               # users 0001은 커밋돼 있음 (모델 변경 시에만 makemigrations)
python manage.py runserver

python manage.py test apps.users   # 테스트
```

## Docker (통합 compose)

루트 `docker-compose.yml`이 db/api/collector를 profiles로 관리한다.

```bash
# 프로젝트 루트에서
docker compose --profile api up -d --build      # db + api
docker compose --profile all up -d --build      # db + api + collector 2종
# 또는 .env에 COMPOSE_PROFILES=api 지정 후: docker compose up -d
```

컨테이너 기동 시 `migrate` → `collectstatic` → gunicorn(8000) 순으로 실행된다.
로컬 http 테스트 시 `.env`에 `DJANGO_SECURE_SSL_REDIRECT=false`
(또는 `DJANGO_SETTINGS_MODULE=config.settings.dev`)를 설정한다.

## 소셜 로그인 API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/v1/auth/{naver\|kakao\|google}/login/` | body `{code, redirect_uri, state}` → JWT(access/refresh) + user. kakao/google은 `redirect_uri` 필수, naver는 `state` 필수 |
| POST | `/api/v1/auth/token/refresh/` | body `{refresh}` → 새 access |
| GET/PATCH | `/api/v1/users/me/` | 내 정보 조회/수정 (Bearer 토큰 필요) |

흐름: 프론트가 제공사 로그인 → authorization code 수신 → 백엔드로 전달 →
백엔드가 토큰 교환·프로필 조회 → `SocialAccount` upsert → 자체 JWT 발급.
같은 (provider, provider_user_id)는 항상 같은 User로 연결되고,
이메일이 같아도 제공사가 다르면 자동 통합하지 않는다(보안상 명시적 연결만).

## 스키마 소유권 (collector 연동)

collector가 쓰는 테이블의 스키마는 전부 Django migration이 관리한다:
`apps/catalog`(naver_product, naver_product_size), `apps/weather`(weather_* 6개).
collector는 raw SQL upsert만 하므로 **모델 변경 시 collector의 INSERT 컬럼 목록도 함께 갱신**해야 한다.
기존에 collector의 init_schema로 테이블이 이미 생성된 DB라면 최초 1회
`python manage.py migrate --fake-initial`로 이력을 동기화한다 (신규 DB는 일반 migrate).
주의: fake-initial은 인덱스/제약 이름을 검사하지 않으므로, 기존 DB의 인덱스 이름이
마이그레이션 정의(`ix_naver_product_tag_status` 등)와 다르면 이후 스키마 변경 시 문제가 될 수 있다.
수집 데이터가 소량이면 볼륨을 초기화하고 신규 migrate로 시작하는 것이 가장 깔끔하다.

## 배포 메모

- prod 실행: `DJANGO_SETTINGS_MODULE=config.settings.prod` (wsgi/asgi 기본값).
- 시크릿은 AWS Secrets Manager/SSM으로 주입. `DJANGO_SECRET_KEY` 없으면 기동 실패하도록 되어 있다.
- 배포 전: `migrate`, `collectstatic`, 헬스체크 확인 (CLAUDE.md 8장).
