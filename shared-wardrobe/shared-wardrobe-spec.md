# 공유 옷장 (Shared Wardrobe) 상세 설계 명세서

- **작성일**: 2026-08-10
- **작성자**: 전하영 (Jira SCRUM-282/283 관련)
- **상태**: 기획 및 설계 완료 (구현 시작 단계)

---

## 1. 개요 및 비즈니스 정책

공유 옷장 서비스는 친구, 연인, 또는 가족 단위의 소그룹이 **하나의 가상 옷장 방을 공유하며 각자의 옷 아이템을 등록·대여·조합 추천에 공동 활용**할 수 있도록 지원하는 핵심 공유 기능입니다.

### 1.1 핵심 비즈니스 룰 (Business Rules)
1. **방 생성 및 초대코드 발급**:
   * 사용자가 방을 개설하면 **6자리의 영대문자+숫자 난수 초대코드**가 생성됩니다.
   * 초대코드의 기본 유효기간은 **24시간**입니다.
   * 초대코드가 만료되거나 방장의 필요에 의해 **초대코드 재발급**을 진행하면, 기존 코드는 무효화되고 새로운 6자리 코드가 발급됩니다.
2. **참여 및 동기화**:
   * 초대받은 멤버는 카카오톡 공유 링크(웹 리다이렉트 딥링크)를 통해 진입하거나 수동으로 6자리 코드를 입력해 방에 가입합니다.
3. **방장 탈퇴 및 방 유지 정책**:
   * 초대한 방장(Owner)이 방을 나가더라도 **공유방이 즉시 폭파되지 않습니다.**
   * 남은 멤버가 1명이라도 있다면 방은 계속 유지되며, 필요시 남은 인원 중 가장 먼저 가입한 멤버에게 방장 권한(`owner` 역할)이 자동으로 위임됩니다.
   * 모든 멤버가 퇴장하여 참여자 수가 0명이 될 때만 방이 최종 폐쇄(Delete)됩니다.
4. **탈퇴 시 아이템 처리 정책 (사용자 선택)**:
   * 멤버가 방을 탈퇴할 때 두 가지 옵션 중 하나를 반드시 선택해야 합니다:
     * **옵션 A (전체 삭제)**: 내가 해당 공유 옷장에 등록해 두었던 옷 아이템들을 모두 함께 삭제하고 퇴장합니다.
     * **옵션 B (아이템 유지)**: 몸만 빠져나가고 내가 등록한 옷들은 공유방에 그대로 유지시켜, 남아있는 친구들이 계속 코디 조합이나 대여에 활용할 수 있도록 기부하고 나갑니다.

---

## 2. 데이터베이스 스키마 설계 (Django Models)

### 2.1 공유 옷장 방 모델 (`SharedWardrobeRoom`)
공유방의 고유 정보와 초대 상태를 관리합니다.

| 필드명 | 데이터 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUIDField | Primary Key, default=uuid4 | 방 고유 식별자 |
| `title` | CharField(100) | Not Null | 방 이름 (예: "우리집 옷장") |
| `invite_code` | CharField(6) | Unique, Nullable | 6자리 초대코드 (만료 시 Null 가능) |
| `code_expires_at` | DateTimeField | Nullable | 초대코드 만료 시각 (생성 시점 + 24시간) |
| `created_at` | DateTimeField | auto_now_add=True | 방 생성 일시 |

### 2.2 방 참여 멤버십 모델 (`SharedWardrobeMember`)
방에 참여한 사용자 목록과 권한 관계를 기록합니다.

| 필드명 | 데이터 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | Primary Key | 레코드 고유 ID |
| `room` | ForeignKey | SharedWardrobeRoom, on_delete=CASCADE | 소속된 공유 옷장 방 |
| `user` | ForeignKey | User, on_delete=CASCADE | 참여한 사용자 |
| `role` | CharField(10) | default='member' | 역할 권한 (`owner` / `member`) |
| `joined_at` | DateTimeField | auto_now_add=True | 방 참여 일시 |

### 2.3 공유 옷장 옷 아이템 모델 (`SharedWardrobeItem`)
공유 옷장 방에 등록된 개별 의류 아이템 정보입니다.

| 필드명 | 데이터 타입 | 제약 조건 | 설명 |
|---|---|---|---|
| `id` | UUIDField | Primary Key, default=uuid4 | 아이템 고유 식별자 |
| `room` | ForeignKey | SharedWardrobeRoom, on_delete=CASCADE | 소속된 공유 옷장 방 |
| `registered_by` | ForeignKey | User, on_delete=SET_NULL, Nullable | 아이템을 등록한 사용자 |
| `name` | CharField(100) | Not Null | 옷 이름 |
| `category` | CharField(20) | Not Null | 카테고리 (outer, top, bottom, dress 등) |
| `image_url` | URLField | Not Null | 옷 사진 S3 경로 |
| `status` | CharField(20) | default='available' | 공유 상태 (`available` / `borrowed` / `private`) |
| `created_at` | DateTimeField | auto_now_add=True | 옷 등록 일시 |

---

## 3. API 엔드포인트 명세 (API Specifications)

### 3.1 방 생성 (POST)
* **URL**: `/api/v1/shared-wardrobes/`
* **요청 바디**:
  ```json
  {
    "title": "가족 공유 옷장"
  }
  ```
* **응답 (201 Created)**:
  ```json
  {
    "room_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "title": "가족 공유 옷장",
    "invite_code": "X8A2F9",
    "code_expires_at": "2026-08-11T17:30:00+09:00",
    "role": "owner"
  }
  ```

### 3.2 초대코드 재발급 (POST)
* **URL**: `/api/v1/shared-wardrobes/{room_id}/refresh-code/`
* **설명**: 기존 코드를 파기하고 24시간 동안 유효한 새 6자리 코드를 발급합니다. (방장 `owner` 권한 필요)
* **응답 (200 OK)**:
  ```json
  {
    "room_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "invite_code": "K9F2A4",
    "code_expires_at": "2026-08-12T17:30:00+09:00"
  }
  ```

### 3.3 방 참여 (POST)
* **URL**: `/api/v1/shared-wardrobes/join/`
* **요청 바디**:
  ```json
  {
    "invite_code": "K9F2A4"
  }
  ```
* **응답 (200 OK)**:
  ```json
  {
    "room_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "title": "가족 공유 옷장",
    "status": "joined"
  }
  ```

### 3.4 방 탈퇴 / 멤버 퇴장 (DELETE)
* **URL**: `/api/v1/shared-wardrobes/{room_id}/leave/`
* **요청 바디**:
  ```json
  {
    "delete_my_items": true 
  }
  ```
  *(참고: `delete_my_items`가 true이면 등록한 옷 일괄 제거, false이면 옷 유지 후 사용자 정보만 삭제)*
* **응답 (204 No Content)**: 성공 시 바디 없음.

---

## 4. 모바일 연동 및 리다이렉트 흐름 (UX Flow)

### 4.1 카카오톡 공유 메시지 구조
카카오톡 템플릿의 공유 버튼 클릭 시, 하이브리드 리다이렉트 웹페이지 주소를 인계합니다:
* **전송 링크**: `https://skn-1st-mobile.expo.app/invite?code=K9F2A4`

### 4.2 스무스한 접속 흐름 (Web Redirect to App Scheme)
1. 초대받은 사용자가 링크 터치.
2. Expo Go 또는 앱의 Universal Link 스키마(`myapp://join?code=K9F2A4`)가 모바일에 내장되어 있을 경우, 웹 브라우저가 이를 가로채어 **앱 내부의 공유방 입장 확인 화면으로 즉시 전환** 시킵니다.
3. 앱 미설치자의 경우, 웹뷰에서 "앱스토어 이동 안내" 또는 "웹에서 6자리 코드 복사하기" 팝업을 노출하여 사용자 가이드라인을 유지합니다.
