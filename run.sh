#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# 1단계: Infisical에서 시크릿을 .env 파일로 내보내기 (실패 시 중단)
infisical export --env=dev --output-file=./.env

# 2단계: Docker Compose 실행 (.env를 읽어 컨테이너에 주입)
# docker-compose.override.yml은 개인 로컬 설정용(gitignored)이라 있을 때만 포함
compose_files=(-f docker-compose.yml)
[ -f docker-compose.override.yml ] && compose_files+=(-f docker-compose.override.yml)
compose_files+=(-f docker-compose.swagger.yml)

docker compose "${compose_files[@]}" --profile all up -d --build
