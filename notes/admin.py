from django.contrib import admin, messages
from .models import Note


@admin.action(description="Reset report count to 0")
def reset_report_count(modeladmin, request, queryset):
    """Admin action to clear false or resolved abuse reports."""
    updated = queryset.update(report_count=0)
    if request is not None:
        modeladmin.message_user(
            request,
            f"Successfully reset report count to 0 for {updated} note(s).",
            messages.SUCCESS,
        )


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "year",
        "subject",
        "uploader",
        "downloads",
        "report_count",
        "created_at",
    )
    list_filter = (
        "category",
        "year",
        "file_type",
        "created_at",
    )
    search_fields = (
        "title",
        "subject",
        "topic",
        "uploader__username",
    )
    ordering = (
        "-report_count",
        "-created_at",
    )
    actions = [reset_report_count]
    readonly_fields = ("created_at", "updated_at", "downloads")
