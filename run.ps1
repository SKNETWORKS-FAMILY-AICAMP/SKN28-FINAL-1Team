# 1단계: Infisical에서 시크릿을 .env 파일로 내보내기 (실패 시 중단)
Set-Location -LiteralPath $PSScriptRoot

infisical export --env=dev --output-file=./.env
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2단계: Docker Compose 실행 (.env를 읽어 컨테이너에 주입)
docker compose -f docker-compose.yml -f docker-compose.swagger.yml --profile all up -d --build
