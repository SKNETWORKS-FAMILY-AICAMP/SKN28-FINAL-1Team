from django.apps import AppConfig


class RecommendConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recommend"
    verbose_name = "추천"

    def ready(self) -> None:
        # Django의 `check --deploy`에서 운영 채팅·추천 필수값을 검증한다.
        from apps.recommend import checks  # noqa: F401
