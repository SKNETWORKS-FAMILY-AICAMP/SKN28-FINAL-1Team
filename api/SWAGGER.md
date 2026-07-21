# Swagger / OpenAPI

기존 실행 설정과 코드는 변경하지 않고 Swagger 전용 설정을 별도로 제공한다.
`config.urls`의 전체 URL 패턴을 포함하므로 앞으로 루트 URL에 연결되는 DRF API도
서버 재시작 후 문서에 자동으로 나타난다.

## 로컬 실행

```powershell
pip install -r requirements.txt
$env:DJANGO_SETTINGS_MODULE = "config.settings.swagger"
python manage.py runserver
```

Linux/macOS에서는 다음과 같이 실행한다.

```bash
pip install -r requirements.txt
DJANGO_SETTINGS_MODULE=config.settings.swagger python manage.py runserver
```

## Docker 실행

프로젝트 루트에서 Swagger 오버레이를 함께 지정한다.

```bash
docker compose -f docker-compose.yml -f docker-compose.swagger.yml --profile api up -d --build
```

## 문서 URL

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- OpenAPI schema: `http://localhost:8000/api/schema/`

Swagger 설정은 개발 환경 설정을 확장하므로 운영 환경 설정으로 사용하지 않는다.
