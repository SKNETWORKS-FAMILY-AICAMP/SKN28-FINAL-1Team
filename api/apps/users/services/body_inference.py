"""사진 기반 신체치수 측정 (mock 구현).

실제 추론 모델이 준비되기 전까지의 임시 구현이다.

- 사진 등록 API가 트랜잭션을 '진행중'으로 만든 뒤 start_measurement()를 호출하면,
  백그라운드 스레드가 FAKE_DELAY_SECONDS(10초) 뒤 상세 둘레 수치를 하드코딩
  값으로 갱신하고 트랜잭션을 '성공'으로 마친다.
- 키·몸무게는 사용자 입력값이므로 절대 갱신하지 않는다 (상세 수치만 추론 대상).
- 스레드 방식은 개발용 임시 수단이다. AWS 이관 시 Celery/SQS 등 외부 워커로
  교체하는 것을 전제로, 호출부(views)는 start_measurement() 인터페이스만 사용한다.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from decimal import Decimal

from django.db import close_old_connections, connections
from django.db import transaction as db_transaction

from apps.users.models import BodyMeasurement, BodyPhotoTransaction

logger = logging.getLogger(__name__)

# mock 처리 소요 시간 (초)
FAKE_DELAY_SECONDS = 10

# 상세 둘레 수치 mock 값 (cm). 키(height)·몸무게(weight)는 포함하지 않는다.
FAKE_DETAIL_MEASUREMENTS: dict[str, Decimal] = {
    "chest": Decimal("95.0"),
    "waist": Decimal("80.0"),
    "hip": Decimal("94.0"),
    "thigh": Decimal("55.0"),
    "calf": Decimal("37.5"),
    "arm": Decimal("30.0"),
    "shoulder": Decimal("44.5"),
}


def start_measurement(transaction_id: uuid.UUID) -> None:
    """측정 트랜잭션 처리를 백그라운드에서 시작한다 (mock: 10초 뒤 성공)."""
    thread = threading.Thread(
        target=_run_fake_measurement,
        args=(transaction_id,),
        name=f"body-photo-tx-{transaction_id}",
        daemon=True,
    )
    thread.start()


def _run_fake_measurement(transaction_id: uuid.UUID) -> None:
    """스레드 본체. 10초 대기 후 성공 처리, 예외 발생 시 실패 처리."""
    time.sleep(FAKE_DELAY_SECONDS)
    # 스레드마다 DB 커넥션이 새로 열리므로 만료 커넥션 정리 후 시작, 끝나면 닫는다.
    close_old_connections()
    try:
        complete_measurement(transaction_id)
    except Exception:
        logger.exception("사진 측정 mock 처리 실패 (tx=%s)", transaction_id)
        BodyPhotoTransaction.objects.filter(pk=transaction_id).update(
            status=BodyPhotoTransaction.Status.FAILED
        )
    finally:
        connections.close_all()


def complete_measurement(transaction_id: uuid.UUID) -> None:
    """상세 수치를 mock 값으로 갱신하고 트랜잭션을 성공 처리한다.

    스레드 없이도 동작을 검증할 수 있도록 분리했다 (tests에서 직접 호출).
    이미 진행중이 아닌 트랜잭션은 건드리지 않는다 (중복 실행 방지).
    """
    with db_transaction.atomic():
        tx = BodyPhotoTransaction.objects.select_for_update().get(pk=transaction_id)
        if tx.status != BodyPhotoTransaction.Status.IN_PROGRESS:
            return

        measurement, _ = BodyMeasurement.objects.get_or_create(user_id=tx.user_id)
        for field, value in FAKE_DETAIL_MEASUREMENTS.items():
            setattr(measurement, field, value)
        # 키·몸무게(height/weight)는 update_fields에 넣지 않아 절대 변경되지 않는다.
        measurement.save(update_fields=[*FAKE_DETAIL_MEASUREMENTS, "updated_at"])

        tx.status = BodyPhotoTransaction.Status.SUCCEEDED
        tx.save(update_fields=["status", "updated_at"])
