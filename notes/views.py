import re
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db.models import Count, ExpressionWrapper, F, FloatField, Q
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import NoteEditForm, NoteUploadForm, UserLoginForm, UserRegisterForm
from .models import Note


def get_annotated_notes():
    """Returns Note queryset annotated with upvotes, downvotes, and composite quality_score."""
    return Note.objects.select_related("uploader").annotate(
        upvotes_count=Count("upvoted_by", distinct=True),
        downvotes_count=Count("downvoted_by", distinct=True),
        quality_score=ExpressionWrapper(
            (Count("upvoted_by", distinct=True) - Count("downvoted_by", distinct=True))
            + (F("downloads") * 0.2),
            output_field=FloatField(),
        ),
    )


def home(request: HttpRequest) -> HttpResponse:
    """
    Renders the SNES discovery landing page featuring:
    - Hero search & quick-filter category/year pills
    - Top 6 notes ordered by composite quality_score
    - Latest 6 recently uploaded notes
    """
    base_qs = get_annotated_notes()
    top_notes = base_qs.order_by("-quality_score", "-created_at")[:6]
    recent_notes = base_qs.order_by("-created_at")[:6]

    return render(
        request,
        "notes/home.html",
        {
            "top_notes": top_notes,
            "recent_notes": recent_notes,
        },
    )


def browse_notes(request: HttpRequest) -> HttpResponse:
    """
    Public discovery & multi-filter search directory for academic notes.
    Supports filtering by keyword (q), category, year, and subject, with
    composite quality_score, recent, or downloads sorting, plus pagination.
    """
    queryset = get_annotated_notes()

    # Query parameters
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    year = request.GET.get("year", "").strip()
    subject = request.GET.get("subject", "").strip()
    sort = request.GET.get("sort", "top").strip()

    # Search keyword
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(subject__icontains=q)
            | Q(topic__icontains=q)
            | Q(description__icontains=q)
        )

    # Category filter
    valid_categories = dict(Note.Category.choices)
    if category and category in valid_categories:
        queryset = queryset.filter(category=category)

    # Year filter
    if year:
        try:
            year_val = int(year)
            queryset = queryset.filter(year=year_val)
        except (ValueError, TypeError):
            pass

    # Subject filter
    if subject:
        queryset = queryset.filter(subject__icontains=subject)

    # Sorting
    if sort == "recent":
        queryset = queryset.order_by("-created_at")
    elif sort == "downloads":
        queryset = queryset.order_by("-downloads", "-created_at")
    else:
        # Default: "top" (quality_score descending, then -created_at)
        sort = "top"
        queryset = queryset.order_by("-quality_score", "-created_at")

    # Pagination: 12 notes per page
    paginator = Paginator(queryset, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Preserve active query parameters across pagination links
    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")
    querystring = query_params.urlencode()

    # Determine if any filter is active
    has_active_filters = bool(q or category or year or subject or (sort and sort != "top"))

    return render(
        request,
        "notes/browse.html",
        {
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "total_count": paginator.count,
            "q": q,
            "selected_category": category,
            "selected_year": year,
            "selected_subject": subject,
            "selected_sort": sort,
            "categories": Note.Category.choices,
            "year_choices": Note.YEAR_CHOICES,
            "querystring": querystring,
            "has_active_filters": has_active_filters,
        },
    )


def register_view(request: HttpRequest) -> HttpResponse:
    """User registration view using Tailwind-styled UserCreationForm."""
    if request.user.is_authenticated:
        return redirect("notes:home")

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f"Welcome to SNES, {user.username}! Your account has been created successfully.",
            )
            return redirect("notes:home")
        else:
            messages.error(
                request,
                "Please correct the errors below to complete your registration.",
            )
    else:
        form = UserRegisterForm()

    return render(request, "notes/register.html", {"form": form})


class UserLoginView(LoginView):
    """Custom LoginView with Tailwind-styled form and authenticated redirect."""

    template_name = "notes/login.html"
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Invalid username or password. Please try again.",
        )
        return super().form_invalid(form)


class UserLogoutView(LogoutView):
    """POST-based logout view for Django 5.2 compliance."""

    next_page = reverse_lazy("notes:home")


@login_required
def upload_note(request: HttpRequest) -> HttpResponse:
    """
    Handles note uploading, validates file format/size, extracts PDF page count,
    assigns uploader, and redirects to note detail.
    """
    if request.method == "POST":
        form = NoteUploadForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.uploader = request.user
            note.file_type = getattr(
                form,
                "cleaned_file_type",
                "PDF" if note.file.name.lower().endswith(".pdf") else "PPTX",
            )
            note.page_count = getattr(form, "cleaned_page_count", None)
            note.save()
            messages.success(
                request,
                f'Note "{note.title}" uploaded successfully!',
            )
            return redirect("notes:note_detail", pk=note.pk)
        else:
            messages.error(
                request,
                "Please correct the errors below to upload your note.",
            )
    else:
        form = NoteUploadForm()

    return render(request, "notes/upload_note.html", {"form": form})


def note_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Displays full note metadata, in-browser document preview, and download/report actions.
    Accessible to both anonymous and authenticated visitors.
    """
    note = get_object_or_404(Note, pk=pk)
    preview_url = ""
    if note.file and note.file.name:
        preview_url = request.build_absolute_uri(note.file.url)

    return render(
        request,
        "notes/note_detail.html",
        {
            "note": note,
            "preview_url": preview_url,
        },
    )


@login_required
def edit_note(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Allows only the note's original uploader to update note metadata.
    Returns 403 Forbidden for unauthorized users.
    """
    note = get_object_or_404(Note, pk=pk)
    if note.uploader != request.user:
        return HttpResponseForbidden(
            "You do not have permission to edit this note."
        )

    if request.method == "POST":
        form = NoteEditForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Note "{note.title}" updated successfully!',
            )
            return redirect("notes:note_detail", pk=note.pk)
        else:
            messages.error(
                request,
                "Please correct the errors below.",
            )
    else:
        form = NoteEditForm(instance=note)

    return render(
        request,
        "notes/edit_note.html",
        {
            "form": form,
            "note": note,
        },
    )


@login_required
@require_POST
def delete_note(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Allows only the note's uploader to delete the note and its underlying file.
    Returns 403 Forbidden for unauthorized users.
    """
    note = get_object_or_404(Note, pk=pk)
    if note.uploader != request.user:
        return HttpResponseForbidden(
            "You do not have permission to delete this note."
        )

    title = note.title
    if note.file:
        note.file.delete(save=False)
    note.delete()
    messages.success(
        request,
        f'Note "{title}" and its underlying file were deleted successfully.',
    )
    return redirect("notes:my_dashboard")


@login_required
def my_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Displays the authenticated user's uploaded notes and bookmarked study list.
    """
    user_uploads = request.user.uploaded_notes.all().order_by("-created_at")
    bookmarked_notes = request.user.bookmarked_notes.all().order_by("-created_at")
    return render(
        request,
        "notes/dashboard.html",
        {
            "user_uploads": user_uploads,
            "bookmarked_notes": bookmarked_notes,
        },
    )


def download_note(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Controlled download endpoint: atomically increments download count
    and serves the file with a clean sanitized attachment filename.
    """
    note = get_object_or_404(Note, pk=pk)
    if not note.file:
        raise Http404("File does not exist for this note.")

    # Atomically increment download count
    Note.objects.filter(pk=pk).update(downloads=F("downloads") + 1)

    # Sanitize title for filename
    raw_name = re.sub(r"[^\w\s\-.]", "", note.title).strip()
    raw_name = re.sub(r"\s+", "_", raw_name)
    if not raw_name:
        raw_name = f"note_{note.pk}"
    ext = note.file_extension.lower() or "pdf"
    if not raw_name.lower().endswith(f".{ext}"):
        download_filename = f"{raw_name}.{ext}"
    else:
        download_filename = raw_name

    try:
        file_handle = note.file.open("rb")
    except Exception:
        raise Http404("Unable to read the requested file from storage.")

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_filename,
    )


@login_required
@require_POST
def report_note(request: HttpRequest, pk: int) -> HttpResponse:
    """
    1-click report endpoint: atomically increments report count,
    flashes admin review confirmation, and redirects back to note detail.
    """
    note = get_object_or_404(Note, pk=pk)
    Note.objects.filter(pk=pk).update(report_count=F("report_count") + 1)
    messages.success(
        request,
        "Thank you. This note has been flagged for admin review.",
    )
    return redirect("notes:note_detail", pk=note.pk)


@require_POST
def toggle_upvote(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Toggles the upvote status of a note for the authenticated user.
    Enforces mutual exclusion with downvotes.
    Returns the vote_controls partial for HTMX swap.
    """
    if not request.user.is_authenticated:
        return HttpResponse(
            status=204,
            headers={"HX-Redirect": f"/login/?next=/note/{pk}/"},
        )

    note = get_object_or_404(Note, pk=pk)
    if note.upvoted_by.filter(pk=request.user.pk).exists():
        note.upvoted_by.remove(request.user)
    else:
        note.upvoted_by.add(request.user)
        note.downvoted_by.remove(request.user)

    return render(
        request,
        "notes/partials/vote_controls.html",
        {"note": note},
    )


@require_POST
def toggle_downvote(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Toggles the downvote status of a note for the authenticated user.
    Enforces mutual exclusion with upvotes.
    Returns the vote_controls partial for HTMX swap.
    """
    if not request.user.is_authenticated:
        return HttpResponse(
            status=204,
            headers={"HX-Redirect": f"/login/?next=/note/{pk}/"},
        )

    note = get_object_or_404(Note, pk=pk)
    if note.downvoted_by.filter(pk=request.user.pk).exists():
        note.downvoted_by.remove(request.user)
    else:
        note.downvoted_by.add(request.user)
        note.upvoted_by.remove(request.user)

    return render(
        request,
        "notes/partials/vote_controls.html",
        {"note": note},
    )


@require_POST
def toggle_bookmark(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Toggles the bookmark status of a note for the authenticated user.
    Returns the bookmark_button partial for HTMX swap.
    """
    if not request.user.is_authenticated:
        return HttpResponse(
            status=204,
            headers={"HX-Redirect": f"/login/?next=/note/{pk}/"},
        )

    note = get_object_or_404(Note, pk=pk)
    if note.bookmarked_by.filter(pk=request.user.pk).exists():
        note.bookmarked_by.remove(request.user)
    else:
        note.bookmarked_by.add(request.user)

    return render(
        request,
        "notes/partials/bookmark_button.html",
        {"note": note},
    )

