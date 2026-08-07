from django.contrib import admin

from .models import (
    GoldenAnalysis,
    GoldenDataset,
    GoldenImage,
    GoldenPairwiseReview,
    GoldenPrinciple,
    GoldenPrincipleEvidence,
    GoldenReview,
)


@admin.register(GoldenDataset)
class GoldenDatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "status", "run_id", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "version", "run_id")


@admin.register(GoldenImage)
class GoldenImageAdmin(admin.ModelAdmin):
    list_display = (
        "golden_id",
        "dataset",
        "split",
        "presentation_group",
        "cluster_id",
        "score_band",
        "human_score",
    )
    list_filter = ("dataset", "split", "presentation_group", "score_band")
    search_fields = ("golden_id", "source_uri", "image_sha256")


@admin.register(GoldenAnalysis)
class GoldenAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "image",
        "model_version",
        "prompt_version",
        "status",
        "latency_seconds",
        "created_at",
    )
    list_filter = ("status", "model_version", "prompt_version")
    search_fields = ("image__golden_id", "error_message")


class GoldenPrincipleEvidenceInline(admin.TabularInline):
    model = GoldenPrincipleEvidence
    extra = 0


@admin.register(GoldenPrinciple)
class GoldenPrincipleAdmin(admin.ModelAdmin):
    list_display = (
        "principle_key",
        "dimension",
        "status",
        "confidence",
        "version",
    )
    list_filter = ("dataset", "dimension", "status", "version")
    search_fields = ("principle_key", "statement")
    inlines = (GoldenPrincipleEvidenceInline,)


@admin.register(GoldenReview)
class GoldenReviewAdmin(admin.ModelAdmin):
    list_display = (
        "dataset",
        "review_key",
        "reviewer_label",
        "verdict",
        "image",
        "principle",
        "created_at",
    )
    list_filter = ("dataset", "verdict", "reviewer_label")
    search_fields = ("image__golden_id", "principle__principle_key", "rationale")


@admin.register(GoldenPairwiseReview)
class GoldenPairwiseReviewAdmin(admin.ModelAdmin):
    list_display = (
        "dataset",
        "pair_key",
        "reviewer_label",
        "comparison_axis",
        "outcome",
        "confidence",
        "created_at",
    )
    list_filter = ("dataset", "comparison_axis", "outcome", "reviewer_label")
    search_fields = (
        "pair_key",
        "left_image__golden_id",
        "right_image__golden_id",
        "rationale",
    )
