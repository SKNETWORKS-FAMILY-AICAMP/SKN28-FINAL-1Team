# 11번가 ProductSearch collector

11번가 ProductSearch XML API로 상품을 수집하고 PostgreSQL에 upsert한다.
스키마는 Django catalog migration이 소유하며 collector는 DDL을 실행하지 않는다.

## 수집 및 태깅 흐름

1. 카테고리조회 응답을 `eleven_category`에 동기화한다.
2. 패션 키워드로 ProductSearch를 호출한다.
3. 카테고리 경로를 공통 추천 분류로 매핑한다.
4. 제목 규칙 속성을 추출한다.
5. `.env`의 provider와 mode에 따라 태깅한다.
6. 원본 XML은 `eleven_api_response`, 상품은 `eleven_product`에 저장한다.

| provider | mode | 동작 |
|---|---|---|
| `openai` | `batch` (기본) | pending 저장 → OpenAI Batch 제출 → 스케줄러 폴링 → 결과 반영 |
| `openai` | `sync` | 수집 중 상품별 동기 태깅 |
| `claude` | `sync` | Claude Agent SDK로 상품별 동기 태깅 |

Claude에 `batch`를 설정하면 경고 후 자동으로 `sync`로 전환된다. Batch 요청 생성과
결과 파싱은 공용 `collector/util/tagging/openai_batch.py`를 사용한다.

Batch 상태 흐름은 `pending → queued → tagged | failed`이며 작업 이력은
`eleven_tagging_batch`에 저장한다.

## 환경 설정

OpenAI Batch:

    ELEVEN_TAGGING_PROVIDER=openai
    ELEVEN_TAGGING_MODE=batch
    OPENAI_API_KEY=...
    OPENAI_MODEL=gpt-4o-mini
    ELEVEN_BATCH_MAX_REQUESTS=10000
    ELEVEN_BATCH_POLL_SECONDS=600
    ELEVEN_BATCH_COMPLETION_WINDOW=24h
    ELEVEN_BATCH_INCLUDE_IMAGE=false

OpenAI 동기 태깅:

    ELEVEN_TAGGING_PROVIDER=openai
    ELEVEN_TAGGING_MODE=sync
    OPENAI_API_KEY=...

Claude 동기 태깅:

    ELEVEN_TAGGING_PROVIDER=claude
    ELEVEN_TAGGING_MODE=sync
    CLAUDE_CODE_OAUTH_TOKEN=...
    ELEVEN_CLAUDE_MODEL=
    INSTALL_CLAUDE_CLI=true

`ANTHROPIC_API_KEY`를 설정하면 OAuth 대신 Anthropic API 과금으로 Claude를 사용할 수
있다. Claude 태거는 텍스트 전용이다.

## 실행

Django migration을 먼저 적용한다.

    docker compose --profile eleven up -d --build eleven-collector

일회성 수집은 설정된 mode를 따른다. Batch mode이면 수집 후 자동 제출한다.

    python eleven_collector_db.py --job collect --keyword "반팔 티셔츠" --limit 30

Batch 수동 제출과 결과 확인:

    python eleven_collector_db.py --job batch-submit
    python eleven_collector_db.py --job batch-poll

pending/failed 상품을 선택한 provider로 즉시 동기 재태깅:

    python eleven_collector_db.py --job retag --limit 30

LLM 호출 없이 수집만 확인:

    python eleven_collector_db.py --job collect --keyword "반팔 티셔츠" --limit 1 --skip-llm

`--scheduler`는 매일 카테고리 동기화와 상품 수집을 실행하고, Batch mode에서는
`ELEVEN_BATCH_POLL_SECONDS` 간격으로 진행 중 Batch 결과를 자동 확인한다.

`INSTALL_CLAUDE_CLI`는 이미지 빌드 옵션이므로 값을 변경한 뒤에는 이미지를 다시
빌드해야 한다. API 키는 요청 원문이나 로그에 저장하지 않는다.
