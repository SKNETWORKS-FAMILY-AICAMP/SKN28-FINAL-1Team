"""옷장 아이템 등록 API.

플로우 (설계 문서 2-1):
  ① 업로드(multipart) → ② S3 선업로드 → ③ job 생성(PENDING)
  → ④ 큐 enqueue → ⑤ 202(job_id) ... ⑨ 콜백(멱등) → ⑩ 저장+벡터 upsert
  → ⑫ 사용자 확인·수정 후 확정
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import redis as redis_lib
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lookbook.services import lookbook_service
from apps.style_calendar.services import calendar_service

from .models import WardrobeItem, WardrobeItemBatch, WardrobeUploadJob
from .permissions import HasInternalToken
from .serializers import (
    CallbackSerializer,
    MAX_BATCH_TOTAL_MB,
    MAX_UPLOAD_MB,
    WardrobeBatchCreateSerializer,
    WardrobeItemSerializer,
    WardrobeItemUpdateSerializer,
    WardrobeJobSerializer,
    WardrobeUploadSerializer,
)
from .services import jobs, storage, vectors
from . import taxonomy as T

logger = logging.getLogger(__name__)

IMPORT_TAG_FIELDS = (
    "item_name", "category_large", "category_small", "season", "style", "color",
    "pattern", "fit", "material", "sleeve", "length", "usage", "layer_role",
    "layer_order", "confirmed",
)


def _provided_metadata(item: dict) -> dict:
    return {
        key: item[key]
        for key in IMPORT_TAG_FIELDS
        if key in item and (item[key] not in ("", None, [], {}) or key == "confirmed")
    }


def _merge_metadata(generated: dict, provided: dict) -> dict:
    merged = dict(generated)
    merged.update({key: value for key, value in provided.items() if key in IMPORT_TAG_FIELDS})
    if merged.get("category_small") and not T.is_valid_pair(
        merged.get("category_large", ""), merged["category_small"]
    ):
        merged["category_small"] = ""
    return merged


def _expire_stale_jobs(queryset) -> int:
    cutoff = timezone.now() - timedelta(
        minutes=int(os.getenv("WARDROBE_BATCH_STALE_AFTER_MINUTES", "20"))
    )
    stale_jobs = list(queryset.filter(
        status=WardrobeUploadJob.Status.PENDING,
        created_at__lte=cutoff,
    ).only("pk", "pipeline"))
    for job in stale_jobs:
        try:
            jobs.cancel_pending(job)
        except redis_lib.RedisError:
            logger.exception("만료 job Redis 제거 실패: %s", job.pk)
    return WardrobeUploadJob.objects.filter(pk__in=[job.pk for job in stale_jobs]).update(
        status=WardrobeUploadJob.Status.FAILED,
        error_message="processing_timeout",
        finished_at=timezone.now(),
    )


def _batch_data(batch: WardrobeItemBatch) -> dict:
    pending = max(batch.total_count - batch.done_count - batch.failed_count, 0)
    terminal = batch.status in {batch.Status.DONE, batch.Status.PARTIAL, batch.Status.FAILED}
    return {
        "batch_id": str(batch.pk), "status": batch.status, "source": batch.source,
        "counts": {"total": batch.total_count, "pending": pending,
                   "done": batch.done_count, "failed": batch.failed_count},
        "progress": round((batch.done_count + batch.failed_count) / batch.total_count, 2),
        "poll_after_ms": None if terminal else int(os.getenv("WARDROBE_BATCH_POLL_AFTER_MS", "3000")),
        "created_at": batch.created_at, "finished_at": batch.finished_at,
        "jobs": WardrobeJobSerializer(batch.jobs.all(), many=True).data,
    }


class WardrobeBatchView(APIView):
    parser_classes = [JSONParser]

    def get(self, request):
        queryset = WardrobeItemBatch.objects.filter(user=request.user).prefetch_related("jobs__items")
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"].upper())
        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except ValueError:
            return Response({"detail": "limit과 offset은 정수여야 합니다."}, status=400)
        return Response([_batch_data(batch) for batch in queryset[offset:offset + limit]])

    def post(self, request):
        serializer = WardrobeBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not storage.BUCKET:
            return Response({"detail": "이미지 저장소가 설정되지 않았습니다."}, status=503)

        items = serializer.validated_data["items"]
        batch = WardrobeItemBatch.objects.create(
            user=request.user, source=serializer.validated_data["source"], total_count=len(items),
        )
        accepted, rejected, uploaded = [], [], []
        total_bytes = 0
        for index, item in enumerate(items):
            image_link = item["image_link"]
            original_name = unquote(PurePosixPath(urlparse(image_link).path).name)[:255]
            job = WardrobeUploadJob(
                user=request.user,
                batch=batch,
                pipeline="qwen-tag",
                original_file_name=original_name or f"import-{index + 1}",
                input_metadata=_provided_metadata(item),
            )
            key = ""
            try:
                image, content_type, extension, size = storage.fetch_remote_image(
                    image_link, MAX_UPLOAD_MB * 1024 * 1024,
                )
                if total_bytes + size > MAX_BATCH_TOTAL_MB * 1024 * 1024:
                    raise storage.RemoteImageError("배치 이미지 합계 용량을 초과했습니다.")
                key = storage.original_key(request.user.pk, job.pk, f"image{extension}")
                storage.upload_fileobj(image, key, content_type)
                total_bytes += size
                uploaded.append(key)
            except storage.RemoteImageError as exc:
                job.status, job.error_message, job.finished_at = "FAILED", str(exc), timezone.now()
                job.source_s3_key = key
                job.save()
                rejected.append({"image_link": image_link, "reason": "image_fetch_failed"})
                continue
            except Exception:  # noqa: BLE001
                logger.exception("외부 이미지 S3 저장 실패: %s", image_link)
                job.status, job.error_message, job.finished_at = "FAILED", "upload_failed", timezone.now()
                job.source_s3_key = key
                job.save()
                rejected.append({"image_link": image_link, "reason": "upload_failed"})
                continue
            job.source_s3_key = key
            job.save()
            try:
                jobs.enqueue_item(job)
                accepted.append({"job_id": str(job.pk), "image_link": image_link})
            except redis_lib.RedisError:
                job.status, job.error_message, job.finished_at = "FAILED", "enqueue_failed", timezone.now()
                job.save(update_fields=["status", "error_message", "finished_at"])
                rejected.append({"image_link": image_link, "reason": "enqueue_failed"})

        if not accepted:
            batch.delete()
            for key in uploaded:
                try:
                    storage.delete_object(key)
                except Exception:  # noqa: BLE001
                    logger.exception("배치 롤백 S3 정리 실패: %s", key)
            return Response({"detail": "일괄 등록을 시작하지 못했습니다."}, status=503)

        batch.refresh_status()
        poll_ms = int(os.getenv("WARDROBE_BATCH_POLL_AFTER_MS", "3000"))
        return Response({
            "batch_id": str(batch.pk), "status": batch.status, "total_count": batch.total_count,
            "accepted": accepted, "rejected": rejected,
            "poll_url": f"/api/v1/wardrobe/batches/{batch.pk}/", "poll_after_ms": poll_ms,
            "estimated_seconds": batch.total_count * int(os.getenv("WARDROBE_BATCH_SECONDS_PER_ITEM", "8")),
        }, status=202)


class WardrobeBatchDetailView(APIView):
    def get(self, request, batch_id):
        batch = get_object_or_404(
            WardrobeItemBatch.objects.prefetch_related("jobs__items"), pk=batch_id, user=request.user,
        )
        # ponytail: 폴링 중에만 만료시킨다. 무조회 자동 정리가 필요해지면 ECS 스케줄로 분리.
        changed = _expire_stale_jobs(batch.jobs)
        if changed:
            batch.refresh_status()
            batch = WardrobeItemBatch.objects.prefetch_related("jobs__items").get(pk=batch.pk)
        return Response(_batch_data(batch))


class WardrobeUploadView(APIView):
    """POST /api/v1/wardrobe/uploads/ — 사진 접수 → 비동기 처리 시작.

    이미지 바이너리는 여기서 S3에 선업로드하고, 큐에는 참조(S3 키)만 넣는다.
    202와 job_id를 반환하며 프론트는 GET /wardrobe/uploads/{job_id}/ 로 폴링한다.
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = WardrobeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]

        job = WardrobeUploadJob(user=request.user)
        key = storage.original_key(request.user.pk, job.pk, image.name)
        try:
            storage.upload_fileobj(image, key, image.content_type)
        except Exception:  # noqa: BLE001
            logger.exception("원본 S3 업로드 실패: user=%s", request.user.pk)
            return Response(
                {"detail": "이미지 저장소 업로드에 실패했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        job.source_s3_key = key
        job.save()

        try:
            jobs.enqueue(job)
        except redis_lib.RedisError:
            # 큐 장애 — 원본은 S3에 남아 있으므로 job을 FAILED로 마킹하고 안내
            logger.exception("job enqueue 실패: job=%s", job.pk)
            job.status = WardrobeUploadJob.Status.FAILED
            job.error_message = "처리 큐 적재 실패"
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error_message", "finished_at"])
            return Response(
                {"detail": "처리 대기열 등록에 실패했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"job_id": str(job.pk), "status": job.status},
            status=status.HTTP_202_ACCEPTED,
        )


class WardrobeUploadJobView(APIView):
    """GET /api/v1/wardrobe/uploads/{job_id}/ — job 상태·결과 조회 (프론트 폴링)."""

    def get(self, request, job_id):
        job = get_object_or_404(
            WardrobeUploadJob.objects.prefetch_related("items"),
            pk=job_id, user=request.user,
        )
        if _expire_stale_jobs(WardrobeUploadJob.objects.filter(pk=job.pk)):
            job = WardrobeUploadJob.objects.prefetch_related("items").get(pk=job.pk)
        return Response(WardrobeJobSerializer(job).data)


class WardrobeCallbackView(APIView):
    """POST /api/v1/internal/wardrobe/callback/ — 이미지 프로세서 처리 결과 수신.

    - 인증: X-Internal-Token (사용자 JWT 아님)
    - 멱등: 이미 DONE/FAILED인 job은 재처리 없이 200 (프로세서 재시도 안전)
    - 벡터는 DB 커밋 후 Qdrant에 best-effort upsert (실패해도 콜백은 성공)
    """

    authentication_classes: list = []
    permission_classes = [HasInternalToken]

    def post(self, request):
        serializer = CallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        batch_id = WardrobeUploadJob.objects.filter(pk=data["job_id"]).values_list("batch_id", flat=True).first()
        with transaction.atomic():
            batch = (WardrobeItemBatch.objects.select_for_update().get(pk=batch_id)
                     if batch_id else None)
            job = (
                WardrobeUploadJob.objects.select_for_update()
                .filter(pk=data["job_id"])
                .first()
            )
            if job is None:
                return Response(
                    {"detail": "job을 찾을 수 없습니다."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if job.status in (
                WardrobeUploadJob.Status.DONE,
                WardrobeUploadJob.Status.FAILED,
            ):
                # 멱등: 중복 콜백은 무시
                return Response({"detail": "이미 처리된 job입니다.", "job_id": str(job.pk)})

            if data["status"] == "processing":
                if job.status == WardrobeUploadJob.Status.PENDING:
                    job.status = WardrobeUploadJob.Status.PROCESSING
                    job.save(update_fields=["status"])
                if batch and batch.status == WardrobeItemBatch.Status.PENDING:
                    batch.status = WardrobeItemBatch.Status.PROCESSING
                    batch.save(update_fields=["status"])
                return Response({"job_id": str(job.pk), "status": job.status})

            if data["status"] == "failed":
                job.status = WardrobeUploadJob.Status.FAILED
                job.error_message = data.get("error", "")
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "error_message", "finished_at"])
                if batch:
                    batch.refresh_status()
                # 한 job이 캘린더와 룩북 양쪽에 걸려 있을 수 있다 (룩북에서
                # '캘린더에도 기록'을 켠 경우 같은 사진을 두 번 처리하지 않으려고
                # job을 공유한다). 걸린 쪽이 없으면 각 함수가 조용히 반환한다.
                calendar_service.apply_wardrobe_job_failure(job=job)
                lookbook_service.apply_wardrobe_job_failure(job=job)
                return Response({"job_id": str(job.pk), "status": job.status})

            created: list[tuple[WardrobeItem, list, list]] = []
            for it in data["items"]:
                item_data = dict(it)
                image_vec = item_data.pop("image_vector", [])
                text_vec = item_data.pop("text_vector", [])
                item_data = _merge_metadata(item_data, job.input_metadata)
                item = WardrobeItem.objects.create(
                    user_id=job.user_id,
                    job=job,
                    embedding_version=vectors.EMBEDDING_VERSION if image_vec else "",
                    **item_data,
                )
                created.append((item, image_vec, text_vec))

            job.status = WardrobeUploadJob.Status.DONE
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "finished_at"])
            if batch:
                batch.refresh_status()
            created_wardrobe_items = [item for item, _, _ in created]
            calendar_service.apply_wardrobe_job_success(
                job=job,
                created_items=created_wardrobe_items,
            )
            lookbook_service.apply_wardrobe_job_success(
                job=job,
                created_items=created_wardrobe_items,
            )

        # DB 커밋 후 파생 저장소 반영 (실패해도 embedding_version으로 재색인 가능)
        for item, image_vec, text_vec in created:
            ok = vectors.upsert_item(item, image_vec, text_vec)
            if not ok and item.embedding_version:
                item.embedding_version = ""
                item.save(update_fields=["embedding_version"])

        return Response(
            {"job_id": str(job.pk), "status": job.status, "num_items": len(created)},
            status=status.HTTP_201_CREATED,
        )


class WardrobeItemListView(APIView):
    """GET /api/v1/wardrobe/items/ — 내 옷장 아이템 목록.

    쿼리 파라미터: category_large, confirmed(true|false)
    """

    def get(self, request):
        qs = WardrobeItem.objects.filter(user=request.user)
        category = request.query_params.get("category_large")
        if category:
            qs = qs.filter(category_large=category)
        confirmed = request.query_params.get("confirmed")
        if confirmed is not None:
            qs = qs.filter(confirmed=confirmed.lower() == "true")
        return Response(WardrobeItemSerializer(qs, many=True).data)


class WardrobeItemDetailView(APIView):
    """PATCH /api/v1/wardrobe/items/{id}/ — 태깅 수정 + 확정 (플로우 ⑫).
    DELETE — 아이템 삭제 (벡터도 함께 제거).
    """

    def patch(self, request, item_id):
        item = get_object_or_404(WardrobeItem, pk=item_id, user=request.user)
        serializer = WardrobeItemUpdateSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        vectors.update_payload(item)  # Qdrant payload 동기화 (best-effort)
        return Response(WardrobeItemSerializer(item).data)

    def delete(self, request, item_id):
        item = get_object_or_404(WardrobeItem, pk=item_id, user=request.user)
        item_pk = item.pk
        item.delete()
        vectors.delete_item(item_pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
