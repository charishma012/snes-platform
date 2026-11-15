import os
from django.conf import settings
from django.db import models


class Note(models.Model):
    """
    Core model representing academic study materials (PDF and PPTX only).
    """

    class Category(models.TextChoices):
        NOTES = "NOTES", "Lecture Notes"
        CHEAT_SHEET = "CHEAT_SHEET", "Cheat Sheet / Summary"
        PYQ = "PYQ", "Past Exam Paper (PYQ)"
        ASSIGNMENT = "ASSIGNMENT", "Assignment"

    YEAR_CHOICES = [(y, str(y)) for y in range(2026, 2017, -1)] + [
        (0, "Other / General")
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="notes/%Y/%m/")
    file_type = models.CharField(max_length=10, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.NOTES,
    )
    year = models.IntegerField(
        choices=YEAR_CHOICES,
        default=2026,
    )
    subject = models.CharField(max_length=120, db_index=True)
    topic = models.CharField(max_length=150, db_index=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_notes",
    )
    downloads = models.PositiveIntegerField(default=0)
    report_count = models.PositiveIntegerField(default=0)

    # Social and bookmarking interactions
    upvoted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="upvoted_notes",
        blank=True,
    )
    downvoted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="downvoted_notes",
        blank=True,
    )
    bookmarked_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="bookmarked_notes",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["year"]),
            models.Index(fields=["subject"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.subject})"

    @property
    def vote_score(self) -> int:
        """Returns net community vote score: upvotes minus downvotes."""
        if hasattr(self, "upvotes_count") and hasattr(self, "downvotes_count"):
            return self.upvotes_count - self.downvotes_count
        return self.upvoted_by.count() - self.downvoted_by.count()

    @property
    def file_extension(self) -> str:
        """Returns uppercase file extension (PDF or PPTX)."""
        if self.file and self.file.name:
            ext = os.path.splitext(self.file.name)[1].lstrip(".").upper()
            if ext:
                return ext
        return (self.file_type or "").upper()

    def save(self, *args, **kwargs) -> None:
        """Auto-populate file_type and attempt page_count detection for PDFs."""
        if self.file and self.file.name:
            ext = os.path.splitext(self.file.name)[1].lower()
            if ext == ".pdf":
                self.file_type = "PDF"
                if not self.page_count:
                    try:
                        import logging
                        from pypdf import PdfReader
                        logging.getLogger("pypdf").setLevel(logging.ERROR)
                        reader = PdfReader(self.file)
                        self.page_count = len(reader.pages)
                    except Exception:
                        pass
            elif ext in (".pptx", ".ppt"):
                self.file_type = "PPTX"
        super().save(*args, **kwargs)
