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

## 배포 메모

- prod 실행: `DJANGO_SETTINGS_MODULE=config.settings.prod` (wsgi/asgi 기본값).
- 시크릿은 AWS Secrets Manager/SSM으로 주입. `DJANGO_SECRET_KEY` 없으면 기동 실패하도록 되어 있다.
- 배포 전: `migrate`, `collectstatic`, 헬스체크 확인 (CLAUDE.md 8장).
