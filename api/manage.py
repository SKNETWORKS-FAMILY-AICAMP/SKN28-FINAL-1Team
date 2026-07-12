#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django를 임포트하지 못했습니다. 가상환경 활성화 및 "
            "`pip install -r requirements.txt` 여부를 확인하세요."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
