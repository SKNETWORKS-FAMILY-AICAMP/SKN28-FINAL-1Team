# Style 온보딩 API (SKN28-FINAL-1Team)

> `Style 온보딩 백엔드 API 연동 가이드.md` + `style-onboarding-api-spec.md` 2개 문서를 하나로 통합. 겹치는 내용(모델 코드, API 스펙) 제거.
> 담당 범위: `mobile/src/app/style-onboarding.tsx` (프론트) + `api/apps/style/` (백엔드, 신규 앱)

---

## 1. 기능 개요

style-onboarding 화면(무드/색상/핏 취향 선택)을 백엔드 API에 연결. 사용자당 1행, 5개 카테고리를 문자열 배열로 저장.

```
[ 너 (모바일 앱) ]                              [ 백엔드 (Django) ]
       |  "내 무드/색상/핏 저장된 거 있어?"                 |
       |  GET /api/v1/users/me/style/ + JWT ------------->|
       |                          [DB style_preferences에서 꺼냄]
       |  "여기 있어" (없으면 5개 필드 모두 빈 배열)          |
       |  <-------------------------------------------------|
       |  "이 값들로 저장해줘"                              |
       |  PUT /api/v1/users/me/style/ + JWT + 5개 배열 ---->|
       |                          [없으면 새로 생성, 있으면 통째로 갱신]
       |  "OK 저장했어"  <-----------------------------------|
```

---

## 2. 확정된 컨벤션 (프로젝트 코드/설정에서 추출)

| 항목 | 값 | 출처 |
|---|---|---|
| 앱 import 경로 | `apps.<name>` | `apps/users/apps.py` |
| Table name | snake_case 복수형 | `users/models.py` |
| `INSTALLED_APPS` 등록 형식 | `"apps.<name>"` | `config/settings/base.py` |
| URL prefix | `/api/v1/` | `config/urls.py` |
| 인증 | JWT (SimpleJWT), `IsAuthenticated` default | `config/settings/base.py` |
| JSON 응답 key | **snake_case** | `users/views.py` |
| 에러 포맷 | `{"detail": "..."}` | `users/views.py` |
| status code | 200, 201, 202, 400, 401, 404 | `users/views.py` |
| Serializer | `ModelSerializer` 우선, 입력은 `extra_kwargs` | `users/serializers.py` |
| View 스타일 | class-based `APIView`, thin view, 로직은 `services.py`로 | `users/views.py`, `home/views.py` |
| 모델 docstring / `verbose_name` | 첫 줄 요약, `verbose_name`은 한국어 | `users/models.py` |
| 시간 필드 | `created_at=auto_now_add`, `updated_at=auto_now` | `users/models.py` |
| 포매터 / 커밋 | black+ruff / Conventional Commits (`feat(scope): ...`) | `AGENTS.md` |

**가장 가까운 참고 모델**: `BodyMeasurement` + `BodyMeasurementView` — 저장 없으면 200+빈 배열 정책까지 그대로 미러링.

---

## 3. 데이터 구조 (프론트 ↔ 백엔드 매핑)

JSON key는 snake_case. 프론트(`style-onboarding.tsx`)는 camelCase 변수를 쓰므로 API 호출 시점에만 변환.

| 프론트 (TS, camelCase) | 백엔드 (JSON, snake_case) | DB column |
|---|---|---|
| `liked` (Set) | `moods` (array) | `moods` (JSONField) |
| `preferredColors` | `preferred_colors` | `preferred_colors` (JSONField) |
| `avoidedColors` | `avoided_colors` | `avoided_colors` (JSONField) |
| `preferredFits` | `preferred_fits` | `preferred_fits` (JSONField) |
| `avoidedFits` | `avoided_fits` | `avoided_fits` (JSONField) |

**컬럼별 JSONField 선택 이유** (vs 단일 `payload` JSONField): 검색/필터/집계 가능성 + fat-model 원칙에 맞춰 컬럼화. `apps.recommend`가 생기면 카테고리별 쿼리가 필요해질 것을 가정. 필요 없어지면 `payload = JSONField(default=dict)`로 단순화 가능(그땐 마이그레이션 재생성).

### 허용 enum (백엔드/프론트 공유, `apps/style/constants.py`)

```python
ALLOWED_MOODS = frozenset({
    "미니멀", "캐주얼", "스트릿", "클래식", "러블리", "시크",
    "스포티", "빈티지", "로맨틱", "아메카지", "모던", "보이시",
})  # 12개
ALLOWED_PREFERRED_COLORS = frozenset({
    "베이지", "화이트", "블랙", "네이비", "브라운", "그레이", "파스텔", "원색",
})  # 8개
ALLOWED_AVOID_COLORS = frozenset({
    "형광", "네온", "쨍한 원색", "올블랙", "파스텔",
})  # 5개
ALLOWED_PREFERRED_FITS = frozenset({
    "레귤러", "슬림", "오버", "루즈", "크롭",
})  # 5개
ALLOWED_AVOID_FITS = frozenset({
    "오버핏", "스키니", "크롭", "노출", "타이트",
})  # 5개
```

---

## 4. API 명세

**Base path**: `/api/v1`
**Auth**: `Authorization: Bearer <access_token>` (없으면 401 — `noauth` 설정에서만 자동 로그인)

### `GET /api/v1/users/me/style/`

**200 OK — 저장 있음**
```json
{
  "moods": ["미니멀", "모던"],
  "preferred_colors": ["베이지", "블랙"],
  "avoided_colors": ["형광"],
  "preferred_fits": ["레귤러"],
  "avoided_fits": ["스키니"],
  "updated_at": "2026-07-22T10:30:00+09:00"
}
```

**200 OK — 저장 없음** (404 아님): 5개 필드 모두 `[]`, `updated_at: null`

**401**: `{ "detail": "자격 인증데이터가 제공되지 않았습니다." }` (DRF/SimpleJWT 기본 메시지)

### `PUT /api/v1/users/me/style/`

**Request**: 5개 필드 모두 필수 (key 자체는 — 값은 `[]` 가능), 각 값은 허용 enum의 멤버.

**200 OK**: 저장된 값 + `updated_at`

**400 — 잘못된 enum 값**:
```json
{
  "moods": ["moods에 허용되지 않은 값: ['뭐시기']. 허용: ['러블리', '로맨틱', '모던', ...]"],
  "preferred_colors": ["preferred_colors은(는) 배열이어야 합니다."]
}
```

---

## 5. 백엔드 구현 — `api/apps/style/` (신규 앱)

### 폴더 구조

```
api/apps/style/
├── __init__.py
├── apps.py                       # StyleConfig
├── models.py                     # StylePreference
├── constants.py                  # 허용 enum 5개
├── serializers.py                # Input/Response 시리얼라이저
├── views.py                      # StylePreferenceView
├── urls.py                       # /users/me/style/
├── admin.py                      # (선택)
├── services.py                   # 초기엔 비워둠 — 추후 추천/필터 로직
├── tests.py
└── migrations/__init__.py
```

### `apps.py`

```python
from django.apps import AppConfig


class StyleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.style"
    verbose_name = "스타일 취향"
```

### `models.py`

```python
"""사용자 스타일 취향. 무드/색상/핏 5개 카테고리를 사용자당 1행으로 보관한다.

온보딩 화면(STEP 2) 입력값의 단일 진실 공급원이며, 추천 시스템(apps.recommend 예정)
이 이 데이터를 읽어간다. 각 카테고리는 string 배열(JSONField)로 저장한다.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class StylePreference(models.Model):
    """사용자당 1행. 없으면 생성, 있으면 통째로 갱신(upsert)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="style_preference",
    )

    moods = models.JSONField("추구하는 무드", default=list, blank=True)
    preferred_colors = models.JSONField("좋아하는 색", default=list, blank=True)
    avoided_colors = models.JSONField("피하고 싶은 색", default=list, blank=True)
    preferred_fits = models.JSONField("원하는 핏", default=list, blank=True)
    avoided_fits = models.JSONField("피하고 싶은 핏", default=list, blank=True)

    created_at = models.DateTimeField("생성 시각", auto_now_add=True)
    updated_at = models.DateTimeField("수정 시각", auto_now=True)

    class Meta:
        db_table = "style_preferences"
        verbose_name = "스타일 취향"
        verbose_name_plural = "스타일 취향"

    def __str__(self) -> str:
        return f"{self.user_id}의 스타일 취향"
```

> `apps/style` 신규 앱이므로 `settings.AUTH_USER_MODEL` 사용 (같은 파일 안이 아니므로 `users/models.py`의 `User` 직접 참조 규칙과 다름).

### `serializers.py`

```python
from rest_framework import serializers

from apps.style.constants import (
    ALLOWED_AVOID_COLORS, ALLOWED_AVOID_FITS, ALLOWED_MOODS,
    ALLOWED_PREFERRED_COLORS, ALLOWED_PREFERRED_FITS,
)
from apps.style.models import StylePreference

_FIELD_RULES = {
    "moods": ALLOWED_MOODS,
    "preferred_colors": ALLOWED_PREFERRED_COLORS,
    "avoided_colors": ALLOWED_AVOID_COLORS,
    "preferred_fits": ALLOWED_PREFERRED_FITS,
    "avoided_fits": ALLOWED_AVOID_FITS,
}


def _validate_choice_list(value, allowed, field_name: str) -> list[str]:
    """문자열 배열 + enum 멤버십 검증. 중복 제거 후 반환."""
    if not isinstance(value, list):
        raise serializers.ValidationError(f"{field_name}은(는) 배열이어야 합니다.")
    invalid = [v for v in value if not isinstance(v, str) or v not in allowed]
    if invalid:
        raise serializers.ValidationError(
            f"{field_name}에 허용되지 않은 값: {invalid}. 허용: {sorted(allowed)}"
        )
    return list(dict.fromkeys(value))  # 입력 순서 유지하며 중복 제거


class StylePreferenceInputSerializer(serializers.Serializer):
    """PUT 요청 바디 검증. 5개 필드 모두 허용 enum의 문자열 배열, 빈 배열 허용."""

    moods = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    preferred_colors = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    avoided_colors = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    preferred_fits = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    avoided_fits = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    def validate(self, attrs):
        return {
            field: _validate_choice_list(attrs.get(field, []), allowed, field)
            for field, allowed in _FIELD_RULES.items()
        }


class StylePreferenceResponseSerializer(serializers.ModelSerializer):
    """GET 응답. 모든 필드 read-only."""

    class Meta:
        model = StylePreference
        fields = [
            "moods", "preferred_colors", "avoided_colors",
            "preferred_fits", "avoided_fits", "updated_at",
        ]
        read_only_fields = fields
```

### `views.py`

```python
"""스타일 취향 조회/저장 API.

`BodyMeasurement`/`BodyMeasurementView` 패턴을 따른다 — 사용자당 1행,
저장 전에는 모든 필드가 빈 배열인 응답을 200으로 돌려준다 (404 X).
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.style.models import StylePreference
from apps.style.serializers import (
    StylePreferenceInputSerializer,
    StylePreferenceResponseSerializer,
)


class StylePreferenceView(APIView):
    """GET/PUT /api/v1/users/me/style/ — 조회 / 저장(upsert, 전체 교체)."""

    def get(self, request):
        pref = StylePreference.objects.filter(user=request.user).first()
        return Response(StylePreferenceResponseSerializer(pref or StylePreference()).data)

    def put(self, request):
        pref, _ = StylePreference.objects.get_or_create(user=request.user)
        serializer = StylePreferenceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(pref, field, value)
        pref.save()
        return Response(StylePreferenceResponseSerializer(pref).data, status=status.HTTP_200_OK)
```

### `urls.py`

```python
from django.urls import path

from apps.style.views import StylePreferenceView

app_name = "style"

urlpatterns = [
    path("users/me/style/", StylePreferenceView.as_view(), name="style-preference"),
]
```

### `admin.py` (선택, 권장)

```python
from django.contrib import admin

from apps.style.models import StylePreference


@admin.register(StylePreference)
class StylePreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    readonly_fields = ("created_at", "updated_at")
```

### 설정 파일 diff (2곳)

`api/config/settings/base.py` — `INSTALLED_APPS`에 추가:
```diff
     "apps.users",
     "apps.catalog",
     "apps.weather",
     "apps.home",
+    "apps.style",
```

`api/config/urls.py` — `urlpatterns`에 추가:
```diff
     path("api/v1/", include("apps.users.urls")),
     path("api/v1/", include("apps.home.urls")),
+    path("api/v1/", include("apps.style.urls")),
```

---

## 6. 프론트 연동 — `mobile/src/app/style-onboarding.tsx`

손볼 곳 3군데.

### A. import 한 줄 추가 (파일 맨 위)

```diff
- import { useState } from 'react';
+ import { useEffect, useState } from 'react';
```

### B. 화면 켜질 때 저장된 값 불러오기 (useState 선언들 바로 뒤)

```tsx
useEffect(() => {
  fetch('http://localhost:8000/api/v1/users/me/style/', {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data) return;
      setLiked(new Set(data.moods ?? []));
      setPreferredColors(new Set(data.preferred_colors ?? []));
      setAvoidedColors(new Set(data.avoided_colors ?? []));
      setPreferredFits(new Set(data.preferred_fits ?? []));
      setAvoidedFits(new Set(data.avoided_fits ?? []));
    })
    .catch(() => {});
}, []);
```
> `${token}` 자리엔 프로젝트의 토큰 변수 (보통 `useAuth()` 훅에서 받아옴).

### C. `finish()` 함수 — 저장 후 화면 이동

```tsx
const finish = async () => {
  try {
    await fetch('http://localhost:8000/api/v1/users/me/style/', {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        moods: Array.from(liked),
        preferred_colors: Array.from(preferredColors),
        avoided_colors: Array.from(avoidedColors),
        preferred_fits: Array.from(preferredFits),
        avoided_fits: Array.from(avoidedFits),
      }),
    });
  } catch (e) {
    console.warn('style save failed', e);
  }
  if (returnTo === 'my') router.replace('/(tabs)/my');
  else router.replace('/(tabs)/home');
};
```

**포인트**: React state 변수명(`preferredColors` 등)은 그대로 두고, API로 보낼 때만 snake_case로 변환. 저장 실패해도 화면 이동은 일단 시킴 (UX 정책).

---

## 7. 결정 사항 / Trade-off

| 결정 | 선택 | 이유 |
|---|---|---|
| 컬럼별 JSONField vs 단일 payload | **컬럼별 5개** | 검색/필터 가능, 추천 시스템이 카테고리별 쿼리 가능. 단점: enum 추가 시 5개 컬럼 다 봐야 함 |
| PUT vs PATCH | **PUT (전체 교체)** | 화면이 5개 카테고리 토글을 모두 들고 있어 부분 수정 케이스 없음. `update_or_create` 의미와 부합 |
| 저장 없으면 404 vs 200+빈값 | **200 + 빈 배열** | `BodyMeasurementView`와 동일 정책. 프론트 분기 불필요, 온보딩은 한 번 끝나면 다시 안 옴 |

---

## 8. 실행 체크리스트 + 테스트 시나리오

```bash
cd api
mkdir -p apps/style/migrations && touch apps/style/migrations/__init__.py
# §5 파일 작성, §5 설정 diff 적용
python manage.py makemigrations style
python manage.py migrate
ruff check apps/style && black apps/style
pytest apps/style/tests.py -v

# 로컬 noauth 실제 호출 확인
DJANGO_SETTINGS_MODULE=config.settings.noauth python manage.py runserver
curl http://localhost:8000/api/v1/users/me/style/
curl -X PUT http://localhost:8000/api/v1/users/me/style/ \
  -H "Content-Type: application/json" \
  -d '{"moods":["미니멀"],"preferred_colors":["베이지"],"avoided_colors":[],"preferred_fits":[],"avoided_fits":[]}'
```

`apps/style/tests.py` 필수 시나리오:
1. 인증 없이 GET/PUT → 401
2. user A 저장 없음 → GET 200, 5개 필드 모두 `[]`
3. user A PUT 정상 → 200, 저장된 값 반환
4. user A 두 번째 PUT → 200, 통째로 갱신 (이전 값 사라짐)
5. user A PUT에 잘못된 enum → 400
6. user B 저장 후 → user A GET엔 user B 데이터 안 보임 (격리)
7. 같은 user GET 후 PUT → `created_at < updated_at` 갱신 확인

---

## 9. 작업 분할 (학습용 흐름 / agent team)

1. **본인 직접 타이핑** — `apps.py` + `models.py` (복붙 X, 학습 목적)
2. **coder 에이전트** — 오타/스타일/import 검토
3. **verifier 에이전트** — 스펙/프로젝트 컨벤션 검증
4. 수정사항 있으면 확인 후 적용

이후 순서(`constants.py`, `serializers.py`, `views.py`, `urls.py`)도 동일 흐름:

| 순서 | 담당 | 산출물 | 의존 |
|---|---|---|---|
| 1 | style-scaffold | 9개 파일 스캐폴딩 | 없음 |
| 2 | style-migrate | `makemigrations style` + `migrate` | 1 |
| 3 | style-config | `base.py`/`urls.py` diff 적용 | 1 |
| 4 | style-integration-test | `tests.py` 7개 시나리오 | 2, 3 |
| 5 | mobile-style-api | RN 화면 GET/PUT 연동 | 3 |

### 커밋 메시지 예시

```bash
git checkout -b feature/style-preference-api

git commit -m "feat(style): 사용자 스타일 취향 조회/저장 API 추가

- apps/style 신규 앱: StylePreference 모델(user당 1행, 5개 JSONField)
- GET/PUT /api/v1/users/me/style/ — 조회/upsert
- BodyMeasurement 패턴 미러링 (저장 없으면 200+빈 배열)
- 허용 enum 5종은 apps/style/constants.py에 frozenset로 정의"

git commit -m "feat(mobile): style-onboarding 화면에 GET/PUT 연동

- 진입 시 GET으로 저장된 값 prefill
- 저장 버튼에 PUT 호출, JSON key는 snake_case로 매핑"
```

---

_이 문서는 이전 2개 문서(가이드/스펙)를 통합한 것. 원본은 삭제됨._
