#!/usr/bin/env bash
# SAM 3 + Gemini 태깅 테스트 이미지 빌드
set -euo pipefail
cd "$(dirname "$0")"

docker build -f Dockerfile.sam3_gemini -t sam3-gemini-test .
echo "빌드 완료: sam3-gemini-test"
