docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.swagger.yml \
  --profile all \
  up -d --build