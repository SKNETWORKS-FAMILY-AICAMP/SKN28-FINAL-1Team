"""로컬 이미지 두 장으로 가상 착장 결과를 확인한다."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.recommend.services.mixed_outfit_render import OutfitRenderError
from apps.recommend.services.virtual_try_on import (
    VirtualTryOnService,
    load_body_profile,
    reference_from_bytes,
)
from apps.users.models import User


class Command(BaseCommand):
    help = "전신 사진과 코디 이미지로 Qwen 가상 착장 테스트를 실행합니다."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser) -> None:
        parser.add_argument("--person", required=True, help="사용자 전신 사진 경로")
        parser.add_argument("--outfit", required=True, help="추천 코디 이미지 경로")
        parser.add_argument(
            "--garment",
            action="append",
            default=[],
            help="원본 의류 이미지 경로(여러 번 지정 가능, 최대 5장)",
        )
        parser.add_argument(
            "--mode",
            choices=["person", "mannequin"],
            default="person",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="마네킹에 반영할 로컬 DB 사용자 ID",
        )
        parser.add_argument("--output", default="virtual_try_on_result.png")
        parser.add_argument(
            "--quality-profile",
            choices=["fast", "quality"],
            default="fast",
            help="fast는 4-step Lightning, quality는 기본 Qwen 30-step",
        )
        parser.add_argument("--seed", type=int)
        # 이전 테스트 명령과의 호환을 위해 받기만 한다.
        parser.add_argument("--mannequin-output")

    def handle(self, *args, **options) -> None:
        try:
            person = Path(options["person"]).read_bytes()
            outfit = Path(options["outfit"]).read_bytes()
        except OSError as exc:
            raise CommandError(f"입력 이미지를 읽지 못했습니다: {exc}") from exc
        if len(options["garment"]) > 5:
            raise CommandError("--garment는 최대 5장까지 지정할 수 있습니다.")
        try:
            garments = tuple(
                reference_from_bytes(
                    f"garment-{index}",
                    Path(path).read_bytes(),
                )
                for index, path in enumerate(options["garment"], start=1)
            )
        except OSError as exc:
            raise CommandError(f"원본 의류 이미지를 읽지 못했습니다: {exc}") from exc

        body_profile = {}
        if options["user_id"] is not None:
            if options["mode"] != "mannequin":
                raise CommandError("--user-id는 --mode mannequin에서만 사용할 수 있습니다.")
            try:
                user = User.objects.get(pk=options["user_id"])
            except User.DoesNotExist as exc:
                raise CommandError("사용자를 찾을 수 없습니다.") from exc
            body_profile = load_body_profile(user)
            self.stdout.write(f"저장 체형 반영: user_id={user.pk}")

        service = VirtualTryOnService(
            profile=options["quality_profile"],
            seed=options["seed"],
        )
        try:
            if options["mode"] == "mannequin":
                mannequin = service.build_mannequin(
                    person,
                    body_profile=body_profile,
                )
                if options["mannequin_output"]:
                    mannequin_path = Path(options["mannequin_output"])
                    mannequin_path.parent.mkdir(parents=True, exist_ok=True)
                    mannequin_path.write_bytes(mannequin.content)
                result = service.dress_mannequin(
                    mannequin.content,
                    outfit,
                    garments=garments,
                )
            else:
                result = service.fit_person(person, outfit, garments=garments)
        except OutfitRenderError as exc:
            raise CommandError(str(exc)) from exc

        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(result.content)
        self.stdout.write(self.style.SUCCESS(f"착장 결과: {output_path.resolve()}"))
