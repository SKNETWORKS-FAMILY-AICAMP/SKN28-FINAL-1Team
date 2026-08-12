"""채팅과 채팅 추천 API가 공유하는 OpenAPI 문서 상수."""

CHAT_TAG = "채팅"

CHAT_IDENTITY_GUIDE = (
    "회원은 Swagger 우측 상단 **Authorize**에 access JWT를 입력합니다. "
    "비회원은 먼저 `POST /api/v1/chat/guest/`를 호출하면 Swagger가 받은 "
    "HttpOnly 게스트 쿠키를 이후 요청에 자동 전송합니다."
)

CHAT_UUID_GUIDE = (
    "문서의 UUID는 형식 예시입니다. 실제 테스트에서는 앞선 API 응답에서 받은 "
    "`session_id`, `run_id`, `attachment_id`, `result_id`, `card_id`, `job_id`를 "
    "각 경로 변수에 복사해야 합니다."
)

CHAT_SSE_GUIDE = (
    "SSE는 연결을 계속 유지하는 응답이라 Swagger의 일반 JSON 화면에서 확인하기 "
    "불편할 수 있습니다. Swagger 테스트에서는 먼저 상태 조회 API를 반복 호출하고, "
    "필요할 때 events URL을 브라우저 EventSource 또는 curl `-N`으로 확인합니다."
)
