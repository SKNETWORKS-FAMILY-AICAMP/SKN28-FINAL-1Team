"""Qdrant 컬렉션 초기화 커맨드.

    python manage.py init_qdrant             # 없는 컬렉션만 생성 (멱등)
    python manage.py init_qdrant --recreate  # 전부 삭제 후 재생성 (데이터 유실!)
    python manage.py init_qdrant --check     # 상태만 출력하고 변경 없음

PG의 `migrate`에 해당하는 역할. 배포 시 migrate 후에 함께 실행한다.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.recommend.services.qdrant import (
    collection_specs,
    ensure_collections,
    get_client,
)


class Command(BaseCommand):
    help = "Qdrant 컬렉션을 스키마 정의(services/qdrant.py)대로 생성한다."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="기존 컬렉션을 삭제하고 재생성한다. 저장된 벡터가 전부 사라진다.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="변경 없이 컬렉션 존재 여부와 포인트 수만 출력한다.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        client = get_client()
        try:
            existing = {c.name for c in client.get_collections().collections}
        except Exception as exc:  # 연결 실패를 명확한 메시지로
            raise CommandError(
                f"Qdrant에 연결할 수 없습니다 (QDRANT_URL 확인): {exc}"
            ) from exc

        if options["check"]:
            for spec in collection_specs():
                if spec.name in existing:
                    info = client.get_collection(spec.name)
                    self.stdout.write(
                        f"  {spec.name}: OK (points={info.points_count})"
                    )
                else:
                    self.stdout.write(f"  {spec.name}: 없음")
            return

        if options["recreate"]:
            confirm = input(
                "기존 컬렉션과 모든 벡터가 삭제됩니다. 계속하려면 'yes' 입력: "
            )
            if confirm != "yes":
                self.stdout.write("취소했습니다.")
                return

        created = ensure_collections(client, recreate=options["recreate"])
        if created:
            self.stdout.write(self.style.SUCCESS(f"생성: {', '.join(created)}"))
        else:
            self.stdout.write("모든 컬렉션이 이미 존재합니다. 변경 없음.")
