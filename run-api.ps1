Set-Location -LiteralPath $PSScriptRoot

infisical export --env=dev --output-file=./.env
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 로컬 Swagger에서 토큰 없이 API를 직접 시험하는 전용 설정이다.
$env:DJANGO_SETTINGS_MODULE = "config.settings.swagger_noauth"
docker compose -f docker-compose.yml --profile api up -d --build --force-recreate
