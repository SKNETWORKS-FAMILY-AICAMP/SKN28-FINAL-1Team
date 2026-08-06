"""코디 평가 → 옷장 아이템 등록 연계.

로그인 사용자가 `save_to_wardrobe=true`로 접수하면, 평가에 올린 사진을 기존 옷장
파이프라인(Redis `wardrobe:jobs` → image-processor → 콜백)에도 그대로 흘려보낸다.

crossing-app 호출을 이 모듈 하나로 몰아 둔다. analysis.py가 wardrobe 모델·서비스를
직접 import하면 두 도메인이 얽혀서, 나중에 옷장 파이프라인 계약이 바뀔 때 평가 쪽까지
읽어야 한다.

설계 결정
- **사진을 다시 올리지 않는다.** 접수 때 이미 `outfits/{user}/{analysis}/original.jpg`로
  업로드했으므로 그 키를 옷장 job의 원본으로 그대로 쓴다. 복사하면 같은 사진이 S3에
  두 벌 쌓인다 (무료 플랜을 이미 한 번 소진한 적이 있다).
  대신 큐 페이로드에 source·output 버킷을 명시해, 결과물은 옷장 버킷에 쌓이게 한다.
- **실패해도 평가를 막지 않는다.** 사용자가 요청한 주된 작업은 코디 평가다. 옷장 등록은
  곁가지이므로 job을 FAILED로 남기고 넘어간다 — 무엇이 실패했는지는 job 조회로 보인다.
"""

from __future__ import annotations

import logging

import redis
from django.utils import timezone

from apps.wardrobe.models import WardrobeUploadJob
from apps.wardrobe.services import jobs as wardrobe_jobs

from . import storage

logger = logging.getLogger(__name__)


def register_outfit_photo(analysis) -> WardrobeUploadJob | None:
    """평가에 쓴 사진으로 옷장 등록 job을 만들고 큐에 넣는다.

    Returns: 생성한 job. 생성 자체가 불가능하면 None (평가는 계속된다).
             큐 적재에 실패한 경우에도 job은 FAILED 상태로 반환한다 —
             클라이언트가 조회했을 때 "왜 안 들어왔는지" 보여야 한다.
    """
    if analysis.user_id is None:
        # 옷장은 사용자 소유 데이터라 익명 요청에는 적용할 수 없다 (뷰에서도 걸러진다)
        return None
    if not analysis.image_s3_key:
        logger.warning("옷장 연계 생략: 사진 키 없음 analysis=%s", analysis.pk)
        return None

    try:
        job = WardrobeUploadJob.objects.create(
            user_id=analysis.user_id,
            source_s3_key=analysis.image_s3_key,
        )
    except Exception:  # noqa: BLE001 — 연계 실패가 평가를 막지 않는다
        logger.exception("옷장 job 생성 실패: analysis=%s", analysis.pk)
        return None

    try:
        # 원본은 코디 평가 버킷에 있다. 옷장 버킷과 같을 수도, 다를 수도 있다.
        wardrobe_jobs.enqueue(job, source_bucket=storage.bucket())
    except redis.RedisError:
        logger.exception("옷장 job 큐 적재 실패: job=%s analysis=%s", job.pk, analysis.pk)
        job.status = WardrobeUploadJob.Status.FAILED
        job.error_message = "처리 큐 적재 실패"
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "finished_at"])
        return job

    logger.info(
        "옷장 등록 연계: analysis=%s job=%s user=%s",
        analysis.pk,
        job.pk,
        analysis.user_id,
    )
    return job
