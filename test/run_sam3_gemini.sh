#!/usr/bin/env bash
# SAM 3 + Gemini 태깅 테스트 실행 (Linux + NVIDIA GPU)
#
# 사용법: ./run_sam3_gemini.sh <이미지경로>
#
# 준비물:
#   1) sam3.pt        — HF gated 가중치. 액세스 승인 후 `python download_sam3.py`로
#                       test/sam3/sam3.pt에 저장하거나 SAM3_WEIGHTS 환경변수로 경로 지정.
#   2) GEMINI_API_KEY — 환경변수로 지정. 없으면 저장소 루트 ../.env 에서 읽는다.
set -euo pipefail
cd "$(dirname "$0")"

if [[ $# -lt 1 ]]; then
    echo "사용법: $0 <이미지경로>" >&2
    exit 1
fi

IMG_PATH="$(realpath "$1")"
IMG_DIR="$(dirname "$IMG_PATH")"
IMG_NAME="$(basename "$IMG_PATH")"

# GEMINI_API_KEY 미설정 시 루트 .env에서 로드 (값은 출력하지 않는다)
if [[ -z "${GEMINI_API_KEY:-}" && -f ../.env ]]; then
    set -a; source ../.env; set +a
fi
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "오류: GEMINI_API_KEY가 설정되지 않았습니다." >&2
    exit 1
fi

WEIGHTS="${SAM3_WEIGHTS:-$PWD/sam3/sam3.pt}"
if [[ ! -f "$WEIGHTS" ]]; then
    echo "오류: SAM 3 가중치가 없습니다: $WEIGHTS" >&2
    echo "python download_sam3.py 로 받거나 SAM3_WEIGHTS로 경로를 지정하세요." >&2
    exit 1
fi

mkdir -p output

docker run --rm --gpus all \
    -e GEMINI_API_KEY \
    -e GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash}" \
    -e SAM3_WEIGHTS=/app/sam3.pt \
    -v "$WEIGHTS":/app/sam3.pt:ro \
    -v "$IMG_DIR":/data:ro \
    -v "$PWD/output":/app/output \
    sam3-gemini-test "/data/$IMG_NAME" --out output

echo "결과: $PWD/output/sam3_gemini/${IMG_NAME%.*}/"
