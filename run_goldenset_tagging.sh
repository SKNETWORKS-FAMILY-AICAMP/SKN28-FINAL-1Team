#!/usr/bin/env bash
# ============================================================
#  골든셋 태깅  —  ★ API 서버에서 실행 ★
# ============================================================
# S3의 코디 manifest에 presentation_group / style / season / occasion을 붙인다.
# 원본 사진을 Gemini가 보고 판단하며, 결과는 같은 manifest.json에 되쓴다.
#
# GPU가 필요 없다. Gemini API와 S3만 쓴다.
#
#   ./run_goldenset_tagging.sh                  # 미태깅분만
#   ./run_goldenset_tagging.sh --limit 3 --dry-run   # 시험 (저장 안 함)
#   ./run_goldenset_tagging.sh --force          # 전량 다시 태깅
#
# 끝나면 GPU 서버에서 ./run_goldenset_sync.sh 를 돌려 Qdrant에 반영한다.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE_FILE=docker-compose.golden_set.yml

# 시크릿을 .env로 내보낸다 (compose 보간 + 컨테이너 주입 양쪽에 쓰인다).
infisical export --env=dev --format=dotenv \
  | sed "s/^\([^=]*\)='\(.*\)'$/\1=\2/" > .env

# golden-set-scan 서비스의 이미지를 그대로 쓰고 커맨드만 바꾼다.
# --rm: 1회성 작업이라 컨테이너를 남기지 않는다.
docker compose -f "$COMPOSE_FILE" run --rm --build \
  golden-set-scan python -m ml.golden_set.tag_manifests "$@"
