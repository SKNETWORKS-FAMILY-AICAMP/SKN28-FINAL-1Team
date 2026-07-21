from django.apps import AppConfig


class ApiDocsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api_docs"

    def ready(self) -> None:
        from apps.api_docs import extensions  # noqa: F401,PLC0415
