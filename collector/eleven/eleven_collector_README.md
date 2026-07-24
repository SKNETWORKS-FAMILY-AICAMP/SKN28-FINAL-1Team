# 11번가 ProductSearch collector

11번가 일반 ProductSearch XML API로 상품을 수집하고 PostgreSQL에 upsert한다.
스키마는 Django catalog migration이 소유하며 collector는 DDL을 실행하지 않는다.

수집 흐름은 다음과 같다.

1. 카테고리조회 응답 전체를 eleven_category에 동기화한다.
2. 네이버 수집기와 같은 패션 키워드로 ProductSearch를 호출한다.
3. 카테고리 경로를 공통 추천 분류로 매핑하고 실패하면 키워드 분류를 쓴다.
4. 제목 규칙 추출 후 `.env`의 `ELEVEN_TAGGING_PROVIDER`에 따라 OpenAI 또는 Claude로 태깅한다.
5. 호출별 XML은 eleven_api_response, 상품은 eleven_product에 저장한다.

## 소량 테스트

루트 `.env`에 `11ST_API_KEY`, 선택한 태깅 provider 인증값, PostgreSQL 설정을
준비하고 migration을 적용한 뒤 실행한다.

OpenAI를 사용할 때:

    ELEVEN_TAGGING_PROVIDER=openai
    OPENAI_API_KEY=...
    OPENAI_MODEL=gpt-4o-mini

Claude를 사용할 때:

    ELEVEN_TAGGING_PROVIDER=claude
    CLAUDE_CODE_OAUTH_TOKEN=...
    ELEVEN_CLAUDE_MODEL=
    INSTALL_CLAUDE_CLI=true

`ANTHROPIC_API_KEY`를 설정하면 OAuth 토큰 대신 Anthropic API 과금으로도 Claude를
사용할 수 있다. Claude 태거는 현재 텍스트 전용이며 상품 이미지는 사용하지 않는다.

    python eleven_collector_db.py --job sync-categories --dry-run
    python eleven_collector_db.py --job collect --keyword "반팔 티셔츠" --limit 1

LLM 호출 없이 API와 DB 저장만 확인하려면 다음 명령을 사용한다.

    python eleven_collector_db.py --job collect --keyword "반팔 티셔츠" --limit 1 --skip-llm

Docker에서는 루트에서 실행한다.

    docker compose --profile eleven up -d --build

`INSTALL_CLAUDE_CLI`는 이미지 빌드 옵션이므로 값을 바꾼 뒤에는
`eleven-collector` 이미지를 다시 빌드해야 한다.

API 키는 요청 원문이나 로그에 저장하지 않는다. dry-run도 API 호출 감사 기록은
eleven_api_response에 저장하지만 상품과 카테고리는 upsert하지 않는다.
