#!/usr/bin/env bash
# test/output 폴더 안의 모든 이미지를
# SAM3 + Gemini로 순차 처리하는 스크립트

set -euo pipefail

# 항상 test/sam3 폴더를 기준으로 실행
cd "$(dirname "$0")"

# 입력 이미지와 결과가 저장될 test/output
OUTPUT_DIR="$(realpath ../output)"

# SAM3 가중치
WEIGHTS="${SAM3_WEIGHTS:-$PWD/sam3.pt}"

# output 폴더 확인
if [[ ! -d "$OUTPUT_DIR" ]]; then
    echo "오류: output 폴더가 없습니다: $OUTPUT_DIR" >&2
    exit 1
fi

# SAM3 가중치 확인
if [[ ! -f "$WEIGHTS" ]]; then
    echo "오류: SAM3 가중치가 없습니다: $WEIGHTS" >&2
    exit 1
fi

# GEMINI_API_KEY가 현재 환경에 없으면 test/.env에서 읽기
if [[ -z "${GEMINI_API_KEY:-}" && -f ../.env ]]; then
    set -a
    source ../.env
    set +a
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "오류: GEMINI_API_KEY가 설정되지 않았습니다." >&2
    echo "예: export GEMINI_API_KEY=\"본인의_API_KEY\"" >&2
    exit 1
fi

# output 폴더 최상위에 있는 이미지만 가져오기
mapfile -d '' IMAGES < <(
    find "$OUTPUT_DIR" \
        -maxdepth 1 \
        -type f \
        \( \
            -iname '*.jpg' -o \
            -iname '*.jpeg' -o \
            -iname '*.png' -o \
            -iname '*.webp' \
        \) \
        -print0 |
    sort -z
)

IMAGE_COUNT="${#IMAGES[@]}"

if [[ "$IMAGE_COUNT" -eq 0 ]]; then
    echo "오류: 테스트할 이미지가 없습니다: $OUTPUT_DIR" >&2
    exit 1
fi

echo "========================================"
echo "SAM3 + Gemini 일괄 테스트"
echo "이미지 폴더: $OUTPUT_DIR"
echo "이미지 수: $IMAGE_COUNT"
echo "가중치: $WEIGHTS"
echo "========================================"

SUCCESS_COUNT=0
FAIL_COUNT=0
CURRENT_INDEX=0

for IMG_PATH in "${IMAGES[@]}"; do
    CURRENT_INDEX=$((CURRENT_INDEX + 1))
    IMG_NAME="$(basename "$IMG_PATH")"

    echo
    echo "[$CURRENT_INDEX/$IMAGE_COUNT] 처리 시작: $IMG_NAME"

    if docker run --rm --gpus all \
        -e GEMINI_API_KEY \
        -e GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash}" \
        -e SAM3_WEIGHTS=/app/sam3.pt \
        -v "$WEIGHTS":/app/sam3.pt:ro \
        -v "$OUTPUT_DIR":/data:ro \
        -v "$OUTPUT_DIR":/app/output \
        sam3-gemini-test \
        "/data/$IMG_NAME" \
        --out output
    then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "[$CURRENT_INDEX/$IMAGE_COUNT] 처리 완료: $IMG_NAME"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "[$CURRENT_INDEX/$IMAGE_COUNT] 처리 실패: $IMG_NAME" >&2
    fi
done

echo
echo "========================================"
echo "전체 테스트 종료"
echo "성공: $SUCCESS_COUNT"
echo "실패: $FAIL_COUNT"
echo "결과: $OUTPUT_DIR/sam3_gemini/"
echo "========================================"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
    exit 1
fi