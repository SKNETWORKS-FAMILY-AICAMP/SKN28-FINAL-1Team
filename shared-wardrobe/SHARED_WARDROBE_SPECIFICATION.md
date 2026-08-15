# 공유 옷장(Shared Wardrobe) 종합 설계 · 구현 명세서

> **프로젝트명**: SKN28-FINAL-1Team (Cozy AI Fashion Recommendation)  
> **문서 버전**: v2.1.0  
> **작성/최종 수정일**: 2026-08-16  
> **관련 저장소 브랜치**: `feature/shared-wardrobe-mybuild` / `main`  
> **Confluence 문서**: [Shared Wardrobe Specification](https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/45744129/Shared+Wardrobe)

---

## 1. 개요 및 목적 (Overview & Objective)

### 1.1 배경 (Context)
기존 개인화 패션 추천 서비스는 단일 사용자의 옷장 데이터에만 국한되어 추천을 생성했습니다. 그러나 실제 패션 소비 및 착장 라이프스타일에서는 가족, 연인, 동거인, 친구 간 **"서로의 옷을 빌려 입거나 코디를 공유하는 행위"**가 일상적으로 일어납니다.

### 1.2 비즈니스 및 기술적 목적 (Objective)
1. **자원 공유 및 활용도 극대화**: 사용자가 보유한 옷을 그룹(가족, 룸메이트, 모임) 단위로 공유하여 자원 활용도를 대폭 향상시킵니다.
2. **AI 추천 시너지 강화**: 개인 옷장 아이템뿐만 아니라 참여 중인 공유 옷장의 아이템까지 AI 착장 추천(Today's Look) 및 가상 피팅 대상에 포함시켜 코디 조합의 가짓수를 획기적으로 확장합니다.
3. **사용자 경험(UX) 최적화**: PC 웹과 모바일 뷰포트에 특화된 반응형 이원화 UI, 미로그인 초대 직통 자동 진입 플로우, 정밀 수직 간격(12px 1:1 대칭) 튜닝을 통해 최상의 UX를 제공합니다.

---

## 2. 핵심 추구 기능 및 비즈니스 규칙 (Core Features & Rules)

### 2.1 공유 옷장 방 생성 및 참여 관리
- **방 개설 및 정원 제약**: 로그인한 사용자는 제한 없이 방을 개설할 수 있으며, 방당 **최대 6명**까지 참여 가능합니다 (동시성 제어를 위해 PostgreSQL `select_for_update` 행 잠금 적용).
- **초대 코드 및 딥링크**: 방 개설 시 6자리 영대문자+숫자 초대 코드가 자동 생성되며, **24시간 유효 기간**을 가집니다. 카카오톡 공유 피드 템플릿과 딥링크(`invite.tsx`)를 통해 손쉽게 초대를 수락할 수 있습니다.
- **초대 링크 접속 UX 직통 처리 (Auth Direct Flow)**:
  - **미로그인 상태**: 초대 링크(`invite?code=XXXXXX`) 클릭 시 **즉시 로그인 페이지(`/login?redirect=...`)로 자동 이동**하며, 로그인 완료 시 자동으로 원래 초대 링크로 복귀하여 방 가입을 완료합니다.
  - **로그인 상태**: 수동 수락 버튼 클릭 대기 없이 **즉시 초대 수락(`joinSharedRoom`)을 실행하고 해당 초대받은 공유 옷장 방(`/(tabs)/closet?tab=shared&room=roomId`)으로 직통 진입**합니다.
- **멤버 고정 색상 매핑**: 멤버의 가입 순서(`joined_at` 인덱스)에 따라 6가지 고정 파스텔 색상(노랑, 하늘, 연두, 핑크, 보라, 주황)을 부여하여 아이템 소유자를 명확하게 구분합니다.
- **방장 권한 자동 위임**: 방장이 방을 나갈 경우 방을 파괴하지 않고, **가입 일시가 가장 빠른 멤버에게 방장 권한이 자동 승계**됩니다. 남은 멤버가 0명일 때만 방이 자동 삭제됩니다.
- **유연한 탈퇴 정책**: 탈퇴 시 등록했던 아이템을 일괄 삭제할지, 또는 방에 남겨두고 공유자만 NULL(기부)로 변경할지 사용자가 선택할 수 있습니다.

### 2.2 비동기 서버 공유 예약 시스템 (Pending Share Reservation)
- **문제 해결**: 업로드 후 AI 누끼/태깅 처리가 끝날 때까지 아이템이 미확정(`confirmed=false`) 상태로 대기하는 동안, 기존의 기기 저장소(`SecureStore`) 공유 예약 방식은 디바이스 변경이나 브라우저 재접속 시 공유가 누락되는 치명적인 문제가 있었습니다.
- **서버 컬럼 이관**: `wardrobe_item` 및 `wardrobe_upload_job` 테이블에 `pending_share_room_id` 컬럼을 신설하여, 이미지 비동기 처리 및 확정 시점(`PATCH /wardrobe/items/{id}/`)에 서버에서 원자적으로 공유 레코드(`shared_room_item`)를 소진/생성하도록 구축했습니다.

### 2.3 다중 방 동시 공유 지원 (`sharedRoomIds`)
- 아이템 1개를 여러 공유 옷장 방에 동시에 등록할 수 있도록 체크박스 다중 선택 드롭다운 UI와 백엔드 배열 수신 파라미터를 구축하였습니다.

### 2.4 반응형 이원화 UX/UI 디자인 (PC Web vs Mobile)
- **PC 웹버전 (`!isMobile`)**:
  - 아이템 상세 화면: 오른쪽 상세 정보 열 내부에 공유 옷장 박스 위치.
  - 아이템 등록/상세: 1행 `[공유 옷장]` 스위치 토글 ➔ **toggle ON 시에만 아래 2행에 '등록/공유할 옷장 선택 [v]' 드롭박스가 깔끔하게 생성**되는 2행 구조 적용.
- **모바일 버전 (`isMobile`)**:
  - 아이템 상세 화면: 사진 영역 상단에 공유 옷장 박스를 배치 (`[1. 공유옷장]` ➔ `[2. 사진]` ➔ `[3. 제목]`).
  - 한 줄(`shareRow`) 스위치 토글 + 오른쪽 드롭다운 버튼 일체형 박스 UI 제공.
  - 방 목록 탭: 방 개수가 여러 개일 때 줄바꿈(행 추가)되지 않고 **가로 한 줄 스크롤 (`flexWrap: 'nowrap'`, `ScrollView horizontal`)**로 매끄럽게 탐색 가능.

### 2.5 상단 레이아웃 수직 간격 대칭 균등화 (12px Equal Spacing)
- **1번째 간격 (Gap 1)**: 카테고리 필터(`전체`, `상의`, `하의` 등) ➔ 공유 옷장 방 목록 가로 스크롤 = **12px** (`chipRow` `paddingBottom: 6` + `roomTabsScrollContent` `marginTop: 6`).
- **2번째 간격 (Gap 2)**: 공유 옷장 방 목록 가로 스크롤 ➔ 초대/참여코드 입력 행 = **12px** (`roomTabsScrollContent` `marginBottom: 12`).
- 두 간격을 1:1 피직스 픽셀 비율로 완전 대칭 배치하여 PC 웹 및 모바일 스크린 모두에서 완벽한 시각적 안정감을 제공합니다.

### 2.6 소유자 뱃지 정돈
- 공유 옷장 타일 및 착장 시트 등에서 사용자 소유자 문구를 `'나님'`에서 `'나'`(사용자 이름 그대로)로 정돈하여 가독성을 향상시켰습니다.

### 2.7 내 옷 공유하기 4x2 갤러리 그리드 모바일 대응
- 공유 옷장에서 내 옷 공유하기 클릭 시 나오는 시트에서 `useWindowDimensions()`를 사용해 화면 폭에 맞춘 타일 높이와 2행 고정 높이(`twoRowsHeight`)를 동적으로 계산하여, **9개 이상 아이템 시에도 4x2 틀 안에서만 깔끔하게 세로 스크롤**되도록 고정했습니다.

---

## 3. 데이터베이스 설계 및 ERD (Database & ERD)

### 3.1 Django 데이터 모델 명세

#### 1. `SharedWardrobeRoom` (`shared_room`) — 공유 옷장 방
| 필드명 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | UUIDField | PK, default=uuid4 | 방 고유 식별자 |
| `title` | CharField(50) | Not Null | 공유 옷장 이름 (예: "우리집 옷장") |
| `invitation_code` | CharField(6) | Unique, Index | 6자리 영대문자+숫자 초대 코드 |
| `invitation_created_at` | DateTimeField | auto_now_add | 초대 코드 생성 일시 (24h 만료 검증용) |
| `created_by` | FK(User) | SET_NULL, Nullable | 최초 방 개설자 |
| `created_at` | DateTimeField | auto_now_add | 방 생성 일시 |

#### 2. `SharedWardrobeMember` (`shared_room_member`) — 공유 방 멤버
| 필드명 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | 멤버십 식별자 |
| `room` | FK(SharedWardrobeRoom) | CASCADE | 소속 방 |
| `user` | FK(User) | CASCADE | 참여 사용자 |
| `role` | CharField(10) | default='member' | `owner` (방장) / `member` (일반) |
| `joined_at` | DateTimeField | auto_now_add | 방 가입 일시 (방장 승계 및 색상 매핑 기준) |

#### 3. `SharedWardrobeItem` (`shared_room_item`) — 공유 아이템 매핑
| 필드명 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | UUIDField | PK, default=uuid4 | 공유 레코드 식별자 |
| `room` | FK(SharedWardrobeRoom) | CASCADE | 소속 방 |
| `wardrobe_item` | FK(WardrobeItem) | CASCADE | 원본 개인 옷 참조 |
| `registered_by` | FK(User) | SET_NULL, Nullable | 공유 등록자 (탈퇴 기부 시 NULL) |
| `status` | CharField(15) | default='available' | `available` (공유가능) / `borrowed` (대여중) / `private` (나만보기) |
| `created_at` | DateTimeField | auto_now_add | 공유 등록 일시 |

#### 4. `WardrobeItem` 신규 추가 예약 컬럼 (`wardrobe_item`)
| 필드명 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `pending_share_room` | FK(SharedWardrobeRoom) | SET_NULL, Nullable | 비동기 이미지 처리 중 공유 예약 방 |
| `pending_share_status` | CharField(15) | Nullable | 비동기 이미지 처리 중 공유 예약 상태 |

---

### 3.2 ERD 다이어그램 (Mermaid Visual Model)

```mermaid
erDiagram
    users ||--o{ wardrobe_item : "소유함"
    users ||--o{ shared_room : "생성함"
    users ||--o{ shared_room_member : "참여함"

    shared_room ||--o{ shared_room_member : "멤버 포함"
    shared_room ||--o{ shared_room_item : "공유 아이템 수록"

    wardrobe_item ||--o{ shared_room_item : "방과 M:N 매핑"
    wardrobe_item }o--o| shared_room : "pending_share_room (미확정 예약 FK)"
    wardrobe_upload_job }o--o| shared_room : "shared_room (업로드 Job 예약 FK)"

    users {
        bigint id PK
        string email
        string nickname
    }

    wardrobe_item {
        uuid id PK
        bigint user_id FK
        string category_large
        string category_small
        string image_url
        boolean confirmed
        uuid pending_share_room_id FK
        string pending_share_status
    }

    wardrobe_upload_job {
        uuid id PK
        bigint user_id FK
        string status
        uuid shared_room_id FK
        string shared_status
    }

    shared_room {
        uuid id PK
        string title
        string invitation_code UK
        bigint created_by_id FK
        datetime created_at
    }

    shared_room_member {
        bigint id PK
        uuid room_id FK
        bigint user_id FK
        string role "owner / member"
        datetime joined_at
    }

    shared_room_item {
        uuid id PK
        uuid room_id FK
        uuid wardrobe_item_id FK
        bigint registered_by_id FK
        string status "available / borrowed / private"
        datetime created_at
    }
```

---

## 4. 백엔드 API 명세 (API Specifications)

모든 API 엔드포인트는 `/api/v1/` 접두사를 사용합니다.

| # | 기능 | HTTP 메서드 및 경로 | 요청 본문 (Body) / 파라미터 | 주요 처리 로직 |
|---|---|---|---|---|
| 1 | 공유 방 목록 조회 | `GET /api/v1/shared-wardrobes/` | None | 내가 가입한 모든 방 목록 및 멤버 정보 반환 |
| 2 | 공유 방 개설 | `POST /api/v1/shared-wardrobes/` | `{ "title": "우리집 옷장" }` | 방 생성 후 6자리 초대 코드 및 개설자 owner 설정 |
| 3 | 초대 코드 재발급 | `POST /api/v1/shared-wardrobes/{room_id}/refresh-code/` | None | owner 전용. 기존 코드 무효화 후 새 24h 코드 발급 |
| 4 | 방 참여 (초대 코드 수락) | `POST /api/v1/shared-wardrobes/join/` | `{ "invite_code": "AB12CD" }` | 6명 정원 및 24h 만료 검증 후 가입 처리 |
| 5 | 공유 방 아이템 목록 | `GET /api/v1/shared-wardrobes/{room_id}/items/` | None | 해당 방에 공유 등록된 옷 목록 반환 |
| 6 | 아이템 공유 등록 | `POST /api/v1/shared-wardrobes/{room_id}/items/` | `{ "wardrobe_item_id": "...", "status": "available" }` | 원본 아이템 참조 기반 공유 레코드 생성 |
| 7 | 아이템 공유 해제 | `DELETE /api/v1/shared-wardrobes/{room_id}/items/{item_id}/` | None | 공유 레코드 삭제 (원본 개인 옷은 보존) |
| 8 | 공유 방 탈퇴 | `DELETE /api/v1/shared-wardrobes/{room_id}/leave/` | `{ "delete_my_items": true/false }` | 방장 자동 위임 로직 실행 및 아이템 삭제/기부 처리 |

---

## 5. 프론트엔드 구현 및 반응형 설계

### 5.1 파일 구조 및 역할
```
mobile/src/
├── app/
│   ├── (tabs)/
│   │   ├── closet.tsx             # 옷장 메인 (내 옷장/공유 옷장 탭, 방 가로 스크롤 칩, 12px 간격 대칭)
│   │   ├── item-detail.tsx        # 옷 상세 (PC웹 2행 드롭다운 / 모바일 상단 1행 일체형 반응형 UI)
│   │   └── saved-look.tsx         # 저장된 코디 (소유자 뱃지 표시)
│   ├── item-add.tsx               # 옷 등록 (PC웹 2행 드롭다운 / 모바일 1행 일체형 반응형 UI)
│   ├── invite.tsx                 # 딥링크 초대 수락 화면 (미로그인 직행 & 로그인 초대방 자동 직통)
│   └── login.tsx                  # 로그인 (redirect 쿼리 파라미터 수신 및 리다이렉트 복귀)
├── components/
│   ├── closet/
│   │   ├── shared-space-flow.tsx  # 공유 방 멤버 아바타 및 카카오 피드 초대 링크 (12px 마진 대칭)
│   │   ├── shared-item-add-sheet.tsx # 내 옷 공유하기 4x2 갤러리 그리드 시트
│   │   └── item-tag-sheet.tsx     # 태그 및 속성 편집 시트
│   └── ui/
│       └── search-filter-bar.tsx  # 카테고리 필터 칩 바 (paddingBottom: 6px 튜닝)
└── hooks/
    └── use-breakpoint.ts          # isMobile, isDesktop 뷰포트 반응형 훅
```

---

## 6. 검증 및 프로덕션 배포 현황

### 6.1 검증 결과 (Automated & Manual Verification)
1. **백엔드 단위 테스트**: `PendingShareReservationTests` 5개 케이스 포함 `apps.wardrobe` 전체 33개 테스트 케이스 **100% 통과 (OK)**.
2. **타입 안전성**: `npx tsc --noEmit` 실행 결과 **타입 에러 0개**.
3. **반응형 뷰포트 및 간격 검증**:
   - PC웹 (1280px 이상): 2단 상세 레이아웃 우측열 내 1행 스위치 + toggle ON 시 2행 드롭다운 및 방 목록 가로 스크롤 동작 확인.
   - 모바일 (768px 이하): 사진 상단 1행 일체형 토글 박스, 4x2 갤러리 그리드 스크롤 및 1:1 대칭 수직 갭(12px) 대조 확인.

### 6.2 프로덕션 배포 현황
- **플랫폼**: Expo Application Services (EAS) Production Web
- **배포 URL**: [https://skncozyhy.expo.app](https://skncozyhy.expo.app)
- **최신 번들 커밋**: `feature/shared-wardrobe-mybuild@83202f3`

---
*SKN28-FINAL-1Team Shared Wardrobe Official Specification*
