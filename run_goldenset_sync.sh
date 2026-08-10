#!/usr/bin/env bash
# ============================================================
#  골든셋 → Qdrant 동기화  —  ★ GPU 서버에서 실행 ★
# ============================================================
# S3의 manifest를 단일 출처로 삼아 골든셋 **전체**를 Qdrant에 다시 쓴다.
# 태그를 새로 붙였거나 payload 구성을 바꿨을 때 전량을 같은 상태로 맞춘다.
#
# GPU 서버에서 돌리는 이유: 코디 이미지 임베딩(FashionSigLIP)과 텍스트
# 임베딩(BGE-M3)을 계산한다. CPU에서도 되지만 느리다.
# 아이템 벡터는 S3에 있는 것을 재사용하므로 다시 계산하지 않는다.
#
#   ./run_goldenset_sync.sh                     # 전량 반영
#   ./run_goldenset_sync.sh --limit 3 --dry-run # 시험 (적재 안 함)
#   ./run_goldenset_sync.sh --require-tags      # 태그 없는 코디는 제외
#
# 먼저 API 서버에서 ./run_goldenset_tagging.sh 를 돌려 태그를 붙여 두어야
# 성별·계절 필터가 동작한다.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE_FILE=docker-compose.gpu.yml

infisical export --env=gpu --format=dotenv \
  | sed "s/^\([^=]*\)='\(.*\)'$/\1=\2/" > .env

# golden-set 서비스의 이미지(GPU 예약 포함)를 쓰고 커맨드만 바꾼다.
docker compose -f "$COMPOSE_FILE" run --rm --build \
  golden-set python -m ml.golden_set.sync_qdrant "$@"
