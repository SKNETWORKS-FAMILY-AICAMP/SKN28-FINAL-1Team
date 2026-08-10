# Pursuit 추구미 API (SKN28-FINAL-1Team)

> `pursuit-api-spec.md` + `Pursuit 추구미 API 백엔드 연동 가이드.md` + `[FINAL_PROJECT] ...md` + `세션 핸드오프...md` + `프로젝트 컨텍스트...md` 5개 문서를 하나로 통합. 겹치는 내용 제거, 최신 상태(verifier 검증 완료 시점)로 정리.
> 마지막 업데이트: 2026-07-23

---

## 1. 한 줄 요약 / 현재 상태

취준 포트폴리오 프로젝트(SKN28-FINAL-1Team)의 "추구미(Pursuit)" 화면 백엔드 API. 11개 카테고리(계절/스타일/색상/넥라인/상의핏/상의기장/소매길이/팬츠핏/팬츠기장/스커트기장/스커트타입, **총 96개 옵션**)에 대해 "선호/기피" 두 모드로 선택을 저장·조회한다.

- 프론트: `mobile/src/screens/PursuitPreferenceScreen.tsx` (사용자 구현, `MOCK_CATEGORY_OPTIONS` 하드코딩 → 백엔드 연동으로 대체 예정)
- 백엔드: `api/apps/users/` (코드 6개 파일 + 마이그레이션 완료, DB 적용 완료, verifier 검증 완료)
- **남은 것**: critical 1건(cross-group dedup 미구현) 수정 + 프론트 연동 + PR

> ⚠️ 옛 문서들은 옵션 총개수를 "98개"로 적었으나 실제 시드는 **96개**가 맞다 (4+16+29+14+4+4+4+7+4+4+6=96). 이 문서는 96으로 정정됨.

---

## 2. 핵심 정책

1. **2-모드 토글**: `preferred`(기본) ↔ `avoided`. 같은 옵션을 두 모드에서 동시에 가질 수 없음.
2. **Cross-group 중복 제거**: 한 옵션이 `preferred.X[]`와 `avoided.X[]` 양쪽에 있으면 모두 제거(서로 모순). "최신 선택 우선" 정책의 백엔드 안전망.
   - 프론트에서 `handleSelectOption`이 모드 변경 시 자동 제거하지만, 네트워크 끊김/여러 탭/직접 API 호출 등으로 양쪽에 같은 옵션이 들어올 수 있어 백엔드도 한 번 더 검증.
   - **현재 미구현 — verifier가 발견한 critical 버그** (§7 참고).
3. **선택 모두 optional**: 아무것도 안 골라도 저장 가능.
4. **PUT 시 전체 교체**: 누락된 카테고리는 빈 배열로 정규화. 부분 업데이트 없음.

---

## 3. 데이터 모델

### 3-1. `PreferenceOption` (옵션 마스터, 신규)

화면에 칩으로 표시되는 모든 옵션의 정적 목록. 사용자가 직접 추가/수정하지 않음 (관리자가 마이그레이션 시드로 관리).

| 필드 | 타입 | 설명 |
|---|---|---|
| `category` | `CharField(choices=PREFERENCE_CATEGORIES, max_length=50)` | "seasons", "styles", ... 11종 |
| `code` | `CharField(max_length=50)` | 머신용 ID (예: "spring", "minimal", "black") |
| `label` | `CharField(max_length=50)` | 화면용 한글 이름 (예: "봄", "미니멀", "블랙") |
| `order` | `PositiveIntegerField(default=0)` | 카테고리 내 표시 순서 |
| `meta` | `JSONField(default=dict, blank=True)` | `{"color_hex": "#000000"}` (색상) 또는 `{"icon": "round-neck"}` (아이콘) |
| `created_at`, `updated_at` | auto | |

- **제약**: `(category, code)` UNIQUE
- **Table**: `preference_options`
- **시드 개수**: 96개

### 3-2. `Pursuit` (사용자 선택, 통째 교체)

사용자당 1행. nested JSON 통째로 저장.

| 필드 | 타입 | 설명 |
|---|---|---|
| `user` | `OneToOneField(User, on_delete=CASCADE, related_name="pursuit")` | 1:1, 같은 파일 안이라 `User` 직접 참조 |
| `payload` | `JSONField(default=dict, blank=True)` | `{"preferred": {...}, "avoided": {...}}` |
| `created_at`, `updated_at` | auto | |

**Table**: `pursuits`

```json
{
  "preferred": {
    "seasons": ["spring"], "styles": ["minimal", "casual"], "colors": ["black", "navy"],
    "necklines": ["round"], "top_fits": ["normal"], "top_lengths": ["crop"], "sleeves": ["long"],
    "pants_fits": ["wide"], "pants_lengths": ["long_pants"], "skirt_lengths": [], "skirt_types": []
  },
  "avoided": {
    "seasons": [], "styles": [], "colors": ["neon"], "necklines": [], "top_fits": [],
    "top_lengths": [], "sleeves": [], "pants_fits": ["skinny"], "pants_lengths": [],
    "skirt_lengths": [], "skirt_types": []
  }
}
```

> `preferred`/`avoided` 모두 **11개 카테고리 키를 항상 포함** (없는 키는 빈 배열로 정규화).

### 3-3. 카테고리 11개 (단일 진실 공급원: `apps/users/constants.py`)

```python
PREFERENCE_CATEGORIES = [
    ("seasons",       "계절"),
    ("styles",        "스타일"),
    ("colors",        "색상"),
    ("necklines",     "넥라인"),
    ("top_fits",      "상의핏"),
    ("top_lengths",   "상의기장"),
    ("sleeves",       "소매길이"),
    ("pants_fits",    "팬츠핏"),
    ("pants_lengths", "팬츠기장"),
    ("skirt_lengths", "스커트기장"),
    ("skirt_types",   "스커트타입"),
]
```

| # | key | label | 개수 | 비고 |
|---|---|---|---|---|
| 1 | seasons | 계절 | 4 | spring, summer, autumn, winter |
| 2 | styles | 스타일 | 16 | minimal, casual, street, ... |
| 3 | colors | 색상 | 29 | 각 `meta.color_hex` 포함 |
| 4 | necklines | 넥라인 | 14 | 각 `meta.icon` 포함 |
| 5 | top_fits | 상의핏 | 4 | normal, slim, loose, oversized |
| 6 | top_lengths | 상의기장 | 4 | crop, short, regular, long |
| 7 | sleeves | 소매길이 | 4 | long, short, three_quarter, sleeveless |
| 8 | pants_fits | 팬츠핏 | 7 | wide, jogger, straight, ... |
| 9 | pants_lengths | 팬츠기장 | 4 | short_shorts, shorts, seven_part, long_pants |
| 10 | skirt_lengths | 스커트기장 | 4 | mini, midi, long, maxi |
| 11 | skirt_types | 스커트타입 | 6 | aline, pleats, flare, hline, mermaid, balloon |
| | **합계** | | **96** | |

> 새 카테고리 추가 시: (1) `constants.py`에 추가 (2) 마이그레이션 시드에 옵션 추가 (3) 프론트 화면/타입에도 추가.

---

## 4. API 명세

**Base URL**: `https://frog-was-entrance-maintaining.trycloudflare.com/api/docs/`
**Auth**: `Authorization: Bearer <JWT>` 필수, 없으면 401

### 4-1. `GET /api/v1/preference-options/` — 옵션 마스터

```json
{
  "categories": [
    { "key": "seasons", "label": "계절", "options": [
      { "code": "spring", "label": "봄", "meta": {} },
      { "code": "summer", "label": "여름", "meta": {} }
    ]},
    { "key": "colors", "label": "색상", "options": [
      { "code": "black", "label": "블랙", "meta": {"color_hex": "#000000"} }
    ]}
  ]
}
```
> 카테고리는 `PREFERENCE_CATEGORIES` 순서, 옵션은 `order` ASC.

```bash
curl -X GET https://frog-was-entrance-maintaining.trycloudflare.com/api/v1/preference-options/ \
  -H "Authorization: Bearer <access_token>"
```

### 4-2. `GET /api/v1/users/me/pursuit/` — 내 선택 조회

**저장 있음**: `{ "preferred": {...11개 키...}, "avoided": {...11개 키...} }`
**저장 없음** (404 아님, 200 + 빈 payload): 11개 키 모두 빈 배열.

### 4-3. `PUT /api/v1/users/me/pursuit/` — 내 선택 저장 (upsert, 전체 교체)

```bash
curl -X PUT https://frog-was-entrance-maintaining.trycloudflare.com/api/v1/users/me/pursuit/ \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"preferred": {"seasons":["spring"], ...}, "avoided": {"seasons":[], ...}}'
```

**검증 규칙**:
- `preferred`, `avoided` 모두 필수 (없으면 400)
- 각 그룹은 11개 카테고리 키 **모두** 있어야 함 (누락 시 400)
- 알 수 없는 카테고리 키 있으면 400
- 각 값은 문자열 배열 (빈 배열 OK)
- 동일 옵션이 양쪽에 있으면 모두 제거 후 저장 (cross-group dedup — **현재 미구현**)

**응답 (200)**: `{ "preferred": {...}, "avoided": {...} }`
> ⚠️ 옛 문서들은 `{"ok": true, ...}` 형태라고 적었으나 실제 코드엔 `ok` 키 없음. **코드 기준으로 HTTP status로 성공 판단** (§7 결정 필요 항목 참고).

**400 예시**:
```json
{
  "preferred": ["preferred에 누락된 카테고리: ['colors', 'necklines']"],
  "avoided":   ["avoided에 알 수 없는 카테고리: ['xyz']"]
}
```

---

## 5. 백엔드 구현

### 5-1. 파일 구조

```
api/apps/users/
├── constants.py                 # PREFERENCE_CATEGORIES (신규)
├── models.py                    # Pursuit + PreferenceOption (수정)
├── services/pursuit.py          # 옵션 그룹핑 + get/upsert (신규)
├── serializers.py               # 4개 시리얼라이저 추가
├── views.py                     # PreferenceOptionsView + PursuitView 추가
├── urls.py                      # 2개 path 추가
└── migrations/0007_pursuit.py   # 재작성 (drop+create, 96개 시드)
```

### 5-2. `services/pursuit.py` 핵심 함수

```python
def get_options_grouped_by_category() -> OrderedDict[str, dict]:
    """11개 카테고리별로 옵션 그룹핑. PREFERENCE_CATEGORIES 순서."""

def get_pursuit(user) -> dict:
    """user의 payload. 없으면 11개 키 전부 빈 배열인 dict 반환 (DB 저장 X)."""

def upsert_pursuit(user, *, preferred: dict, avoided: dict) -> Pursuit:
    """update_or_create로 통째 교체."""
```

### 5-3. 미구현 cross-group dedup (다음 세션 1순위 작업)

위치: `api/apps/users/services/pursuit.py`의 `upsert_pursuit` 시작 부분.

```python
overlap = set()
for key, _ in PREFERENCE_CATEGORIES:
    p_set = set(preferred.get(key, []) or [])
    a_set = set(avoided.get(key, []) or [])
    overlap |= p_set & a_set
if overlap:
    for key, _ in PREFERENCE_CATEGORIES:
        preferred[key] = [c for c in (preferred.get(key, []) or []) if c not in overlap]
        avoided[key]   = [c for c in (avoided.get(key,   []) or []) if c not in overlap]
```

검증 시나리오: `preferred.seasons=["spring"]`, `avoided.seasons=["spring"]` → 저장 후 양쪽 다 `[]`.

---

## 6. 프론트 연동 가이드

`mobile/src/screens/PursuitPreferenceScreen.tsx`에서 손볼 곳:

```typescript
useEffect(() => {
  // 1) 옵션 마스터 받아오기 → MOCK_CATEGORY_OPTIONS 대체
  const options = await api.get('/preference-options/');
  // 2) 저장된 사용자 선택 받아오기 → preferences state 초기화
  const saved = await api.get('/users/me/pursuit/');
}, []);

const handleSave = async () => {
  await api.put('/users/me/pursuit/', {
    preferred: { /* 11개 키, 각 value는 string[] */ },
    avoided:   { /* 11개 키, 각 value는 string[] */ },
  });
};
```

`MOCK_CATEGORY_OPTIONS` 하드코딩 제거하고 위 응답으로 대체. `handleSelectOption`의 "최신 선택 우선" 로직은 이미 프론트에 있음 — 백엔드가 한 번 더 검증(§5-3)하는 것뿐.

---

## 7. 검증 결과 (Coder + Verifier, 2026-07-23)

- **Coder** (코드 리뷰): 0 critical, 2 medium, 6 low → 수정은 사용자가 직접 타이핑하기로 하고 보류
- **Verifier** (스펙/통합 검증): 18 PASS, 1 critical FAIL, 2 medium, 6 low

| 심각도 | 내용 | 위치 / 조치 |
|---|---|---|
| 🔴 CRITICAL | cross-group dedup 미구현 (§1-3 정책 위반) | `services/pursuit.py:98-117` — §5-3 코드 추가 필요 |
| 🟡 MEDIUM | PUT 응답에 `ok` 키 없음 (스펙 vs 코드 불일치) | **사용자 결정 필요**: 코드에 `ok` 추가 vs 문서에서 제거 (권장: 문서 쪽 정리, HTTP status로 충분) |
| 🟡 MEDIUM | 옛 문서 "98개" → "96개" 정정 | 본 문서에서 이미 정정 완료 |
| 🟢 LOW | `CATEGORY_CHOICES` 중복 정의 (constants.py ↔ models.py) | `models.py`에서 `PREFERENCE_CATEGORIES` import로 통일 |
| 🟢 LOW | 정수 coerce로 문자열 검증 약화 | |
| 🟢 LOW | 카테고리 간 동일 code (short, long) | |
| 🟢 LOW | 시드 reverse 시 pursuits 테이블 drop 안 됨 | |
| 🟢 LOW | `services/__init__.py` 비어있음 | `from apps.users.services import accounts, body_inference, oauth, pursuit` 추가 |
| 🟢 LOW | urls.py 코멘트 typo `payloa` → `payload` | |

18 PASS 항목: 카테고리/시드 정합성, code 중복 없음, meta 구조, URL/trailing slash, JWT+IsAuthenticated, PUT 검증(누락/미지 카테고리 거부, 배열/빈문자열 검증), 같은 그룹 내 중복 제거, GET/PUT 정규화, UNIQUE 제약, 시드 idempotent, User 직접 참조 규칙, `manage.py check`/`makemigrations --dry-run` 통과.

---

## 8. 진행 상황 / 다음 할 일

### 완료 ✅
- 모델 redesign (5필드 → nested payload) + `PreferenceOption` 마스터
- `constants.py`, `services/pursuit.py`, `serializers.py`(4개), `views.py`(2개), `urls.py`(2개)
- `migrations/0007_pursuit.py` 재작성 (drop + create + 96개 시드)
- DB 정리 + 마이그레이션 적용, Docker 재빌드
- DRF `default=` + `required=` 버그 수정
- Python 스크립트 직접 테스트 3/3 통과
- URL 명칭 정정: `style-preferences` → `pursuit`
- Coder 리뷰 + Verifier 통합 검증 완료

### 남은 것 ⏳ (우선순위 순)
| # | 작업 | 우선순위 |
|---|---|---|
| 1 | cross-group dedup 추가 (§5-3) | 🔴 |
| 2 | PUT 응답 `ok` 키 — 코드/문서 중 정할 것 | 🟡 사용자 결정 |
| 3 | `CATEGORY_CHOICES` 중복 제거 | 🟢 |
| 4 | `services/__init__.py` re-export | 🟢 |
| 5 | urls.py typo 수정 | 🟢 |
| 6 | 프론트 `PursuitPreferenceScreen.tsx` 연동 | 🟡 |
| 7 | 통합 테스트 + PR (`feat(users): 사용자 추구미 API 추가`) | 🟢 |

---

## 9. 알려진 함정

1. **`User` 직접 참조**: 같은 `apps/users/models.py` 안이므로 OK. 다른 앱에서 참조 시엔 `settings.AUTH_USER_MODEL` 우회 (`BodyMeasurement` 참고).
2. **Docker 이미지 재빌드 필수**: `api/Dockerfile`이 `COPY . /app/`로 박아넣고 볼륨 마운트 없음. 코드 수정 후 `docker compose up -d --build` 필요, `restart`만으론 반영 안 됨.
3. **컨테이너 → 호스트 파일 자동 동기화 안 됨**: 컨테이너 안 `makemigrations`로 만든 파일은 `docker cp skn28-api:/app/apps/users/migrations/0007_pursuit.py api/apps/users/migrations/0007_pursuit.py`로 수동 복사.
4. **DRF `default=` + `required=` 동시 지정 불가**: `required=True`인 필드엔 `default` 키워드 자체를 빼야 함.
5. **`DJANGO_SETTINGS_MODULE`**: 컨테이너는 `config.settings.swagger`로 실행. Python 스크립트 테스트 시 동일 설정 필요.
6. **Swagger UI 깨짐** (본 작업과 무관한 선행 버그): `apps/api_docs/extensions.py`에서 `SocialLoginView` 처리 중 AssertionError. 우회: Python 스크립트로 서비스 레이어 직접 호출.

---

## 10. 자주 쓰는 명령어

```powershell
cd "C:\Users\Playdata\Desktop\SKN28-FINAL-1Team"

# 재빌드 / 상태
docker compose up -d --build
docker compose ps
docker compose logs --tail=30 api

# DB 정리 (옛 5필드 pursuits 테이블 잔재 있을 때만)
docker compose exec db psql -U postgres -d fashion_db -c "DROP TABLE IF EXISTS pursuits CASCADE;"
docker compose exec db psql -U postgres -d fashion_db -c "DELETE FROM django_migrations WHERE app='users' AND name='0007_pursuit';"

# 마이그레이션
docker compose exec api python manage.py migrate
docker compose exec db psql -U postgres -d fashion_db -c "SELECT category, COUNT(*) FROM preference_options GROUP BY category ORDER BY category;"
# 기대: 4/16/29/14/4/4/4/7/4/4/6 = 총 96

# 컨테이너 → 호스트 파일 복사
docker cp skn28-api:/app/apps/users/migrations/0007_pursuit.py api/apps/users/migrations/0007_pursuit.py

# 서비스 레이어 직접 테스트 (JWT 없이)
docker compose exec api python -c "
import os, django
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.swagger'
django.setup()
from apps.users.services import pursuit
from django.contrib.auth import get_user_model
User = get_user_model()
u, _ = User.objects.get_or_create(username='testuser', defaults={'nickname':'테스트'})
print(pursuit.get_pursuit(u))
pursuit.upsert_pursuit(u, preferred={'seasons':['spring'],'styles':['minimal']}, avoided={'seasons':[],'styles':[]})
print(pursuit.get_pursuit(u))
"
```

---

## 11. 왜 이렇게 만들었는가 (설계 결정)

- **`Pursuit.payload` 단일 JSONField (vs 11개 컬럼쌍)**: 카테고리 추가 시 마이그레이션 없이 데이터만 추가 가능. DB 레벨 쿼리(예: "봄 선호 유저 전체")는 Python 필터로 대체 — 추천 로직이 아직 Python 레벨이라 지금은 유연성 우선, 추후 필요하면 재검토.
- **`PreferenceOption` 마스터 테이블 (vs 프론트 하드코딩)**: 옛엔 프론트 `MOCK_CATEGORY_OPTIONS`에 하드코딩 → 옵션 변경마다 프론트도 동시 수정 필요했음. 백엔드 시드로 단일화.
- **GET 빈 응답 (vs 404)**: `BodyMeasurementView`와 동일 정책. 프론트 분기 단순화.
- **URL `/pursuit/` (vs `/style-preferences/`)**: 프론트 화면명 `PursuitPreferenceScreen.tsx`와 일치, "style-preferences"는 일반 환경설정으로 헷갈릴 수 있어 배제.

---

_이 문서는 이전 5개 문서(가이드/스펙/UpNote노트/핸드오프/프로젝트컨텍스트)를 통합한 것. 원본은 삭제됨._
