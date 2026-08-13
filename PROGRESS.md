# 진행 상태

## 2026-08-13

- Docker Desktop 엔진 29.6.2 실행 확인.
- Infisical CLI 설치 경로 확인.
- 공유 옷장·추천·모바일 파일을 포함한 미해결 병합 충돌 10개 확인.
- 공유 기능, 추천 연결, 런타임 환경을 병렬 조사 중.
- Confluence `공유 옷장(Shared Wardrobe) 설계 · 구현 명세서` v5 확인.
- 구현 기준: 관계 기반 공유, 최대 6명, confirmed 아이템만 공유, DB ID 화이트리스트 방식의 공유 옷 추천 연결.
- 로컬 실행은 `config.settings.swagger_noauth`와 `localhost:8000/api/docs/`를 사용하도록 `run-api.ps1` 갱신.
- `main` 병합 충돌 10개 해소. 공유 UI와 서버 추천 카드 경로를 함께 보존.
- 공유 정책 보강: confirmed 아이템만 공유, 방 삭제 owner-only, migration graph merge.
- 추천 연결: 개인·공유 available 아이템 ID를 DB에서 계산해 Qdrant whitelist 검색에 전달.
- 모바일: 실제 클립보드와 카카오 공유 SDK 연결, 추천 목업 제거 후 서버 채팅 추천 사용.
- 검증: Django 공유·추천 120개 테스트 통과, TypeScript 검사 통과.
- 실행: Infisical dev 주입 완료, Docker API 스택 기동, Swagger/공유/추천 API 모두 HTTP 200.
- 로컬 주소: 앱 `http://localhost:8081`, Swagger `http://localhost:8000/api/docs/`.
- 공유방 사용자 정의 카테고리 DB 추가: `shared_wardrobe_category`, `shared_wardrobe_item_category`.
- `wardrobe.0008_shared_wardrobe_categories`를 개발 DB에 적용하고 두 테이블 생성 확인.
- 공유 옷장 카테고리 `GET/POST/DELETE /api/v1/shared-wardrobes/{room_id}/categories/` 구현.
- 모바일 카테고리 관리 저장 버튼을 공유방별 API와 연결하고 추가·삭제 후 DB 목록 재조회.
- 검증: 모바일 TypeScript 통과, 공유 옷장 API 테스트 10개 통과, Swagger HTTP 200.
- 로컬 백엔드 옷 등록에 Gemini 직접 태깅 활성화(`LOCAL_GEMINI_TAGGING=1`, 로컬 저장소 한정).
- Gemini 인증키를 URL 쿼리에서 `x-goog-api-key` 헤더로 이동하고 모델을 `gemini-3.5-flash`로 갱신.
- 백엔드 샘플 업로드 실측 성공: 트렌치코트가 아우터/코트/베이지로 분석되어 약 6.7초 내 DONE 저장.

## 2026-08-14

- Infisical dev 주입으로 Docker API, PostgreSQL, Redis, Qdrant 및 백엔드 worker 기동 확인.
- health live/ready와 Swagger HTTP 200, Django system check 이상 없음.
- Gemini 직접 태깅이 S3 원본도 임시 다운로드해 처리하도록 보강하고 실제 API 업로드를 검증함.
- 실제 업로드 결과: HTTP 201, job DONE, 원본 파일명·완료시각·태그된 WardrobeItem 1개 DB 저장 확인.
- 빈 파일명과 실패 콜백의 빈 오류 메시지를 수정하고 회귀 테스트 추가.
- 공유 옷 등록→DB 저장→다른 멤버 조회→공유 해제 시 개인 원본 보존 흐름 확인.
- 공유 옷 room+item 유니크 제약 및 private 아이템 접근 차단 추가; wardrobe migration 0009 개발 DB 적용.
- 옷장·공유 옷장 Docker 테스트 28개 통과.
- 카카오 모바일 TypeScript 및 Expo native config 생성 통과; 실제 메시지 전송은 실기기·카카오 콘솔 설정 확인 필요.
- 기존 b55f89bf job은 PENDING이며 연결된 S3 원본이 404라 완료 불가. 기존 Redis 옷장 큐 적체는 GPU 워커 검증 범위에서 제외.
- 카카오 공유 정책 확정: 네이티브 모바일은 초대 문구를 먼저 복사한 뒤 카카오톡 공유 SDK를 열고, PC 웹은 카카오/OS 공유창 없이 문구만 복사.
- 모바일 TypeScript, Expo native config introspect, Expo web production export 통과.
- Swagger/OpenAPI 옷장·공유 옷장 관련 경로 20개 노출 확인.
- 옷 상세 GET 및 add-to-closet 응답 스키마를 보강하고, 공유 카테고리 DELETE의 category_id를 Swagger query 입력으로 노출.
- 옷장·공유 옷장·Swagger 회귀 테스트 37개 통과; 실행 서버 schema에서 수정 operation/parameter 반영 확인.
- 현재 브라우저 제어 연결이 없어 Swagger UI 버튼 직접 클릭은 미검증. 동일 API 요청 및 OpenAPI 계약 검증으로 대체했으며 UI 클릭과 실제 카카오 앱 전환은 실기기에서 최종 확인 필요.
- 공유방 전체 API 생명주기 테스트 추가: 생성→목록→상세→수정→초대코드 재발급→익명 미리보기→참여→멤버 조회→탈퇴.
- Swagger 핵심 옷장·공유 옷장 operation 27개의 summary/tag/response 전수 검사 추가.
- 누락됐던 공유방 목록·상세·수정 및 공유 아이템 상태 PATCH Swagger 설명 보강.
- 옷장·공유 옷장·Swagger 테스트 38개 통과, 최신 Docker API 반영 후 ready/docs/schema 모두 HTTP 200.
- 브라우저 세션 목록이 계속 비어 있고 Android SDK(adb/emulator)도 없어 UI 직접 클릭·카카오 앱 전환 검증은 환경 준비 전까지 진행 불가.
- 공유 카드 상세 404 수정: 카드 클릭 시 SharedWardrobeItem ID 대신 원본 WardrobeItem ID 전달.
- 공유방 멤버는 공유된 옷 상세 GET 가능, 외부인은 404이며 타인 옷 상세는 읽기 전용 UI로 제한.
- 검증: TypeScript 통과, 공유 옷장 테스트 11개 통과, 상세 권한 200/404 확인.
- 카카오 공유용 `EXPO_PUBLIC_KAKAO_JAVASCRIPT_KEY`가 Infisical dev에 존재함을 값 노출 없이 확인.
- Expo를 Infisical 주입 상태로 8081에 재기동하고 `run-mobile.ps1` 실행 경로 추가.
- Kakao JavaScript SDK를 2.8.0으로 갱신. 로컬 앱 HTTP 200 확인.
