import io
from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from pypdf import PdfWriter

from .admin import NoteAdmin, reset_report_count
from .forms import NoteEditForm, NoteUploadForm
from .models import Note

# Minimal valid 1-page PDF
VALID_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n"
    b"0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
)


class NoteModelTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="student1", password="securepassword123"
        )
        self.user2 = User.objects.create_user(
            username="student2", password="securepassword123"
        )
        self.user3 = User.objects.create_user(
            username="student3", password="securepassword123"
        )

    def test_note_creation_and_defaults(self):
        """Note model creates successfully with default values and auto PDF detection."""
        fake_pdf = SimpleUploadedFile(
            "sample_lecture.pdf",
            VALID_PDF_BYTES,
            content_type="application/pdf",
        )
        note = Note.objects.create(
            title="Data Structures Lecture 1",
            description="Introduction to Arrays and Linked Lists",
            file=fake_pdf,
            subject="Computer Science",
            topic="Data Structures",
            uploader=self.user1,
        )
        self.assertEqual(note.title, "Data Structures Lecture 1")
        self.assertEqual(note.category, Note.Category.NOTES)
        self.assertEqual(note.year, 2026)
        self.assertEqual(note.file_type, "PDF")
        self.assertEqual(note.file_extension, "PDF")
        self.assertEqual(note.page_count, 1)
        self.assertEqual(note.downloads, 0)
        self.assertEqual(note.report_count, 0)
        self.assertEqual(note.vote_score, 0)
        self.assertIn("Data Structures Lecture 1 (Computer Science)", str(note))

    def test_pptx_file_type_auto_population(self):
        """PPTX files auto-populate file_type and file_extension as PPTX."""
        fake_pptx = SimpleUploadedFile(
            "discrete_math_slides.pptx",
            b"fake pptx content",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        note = Note.objects.create(
            title="Graph Theory Slides",
            file=fake_pptx,
            category=Note.Category.CHEAT_SHEET,
            year=2024,
            subject="Mathematics",
            topic="Graph Theory",
            uploader=self.user2,
        )
        self.assertEqual(note.file_type, "PPTX")
        self.assertEqual(note.file_extension, "PPTX")

    def test_vote_score_calculation(self):
        """Vote score calculates upvotes minus downvotes correctly."""
        fake_pdf = SimpleUploadedFile(
            "pyq_exam.pdf", VALID_PDF_BYTES, content_type="application/pdf"
        )
        note = Note.objects.create(
            title="Final Exam 2023",
            file=fake_pdf,
            category=Note.Category.PYQ,
            year=2023,
            subject="Algorithms",
            topic="Dynamic Programming",
            uploader=self.user1,
        )
        self.assertEqual(note.vote_score, 0)

        # 2 upvotes
        note.upvoted_by.add(self.user1, self.user2)
        self.assertEqual(note.vote_score, 2)

        # 1 downvote
        note.downvoted_by.add(self.user3)
        self.assertEqual(note.vote_score, 1)

    def test_bookmarked_by_relation(self):
        """Bookmarked by ManyToMany relationship functions properly."""
        fake_pdf = SimpleUploadedFile(
            "assignment1.pdf", VALID_PDF_BYTES, content_type="application/pdf"
        )
        note = Note.objects.create(
            title="Homework 1",
            file=fake_pdf,
            category=Note.Category.ASSIGNMENT,
            year=2025,
            subject="Operating Systems",
            topic="Processes",
            uploader=self.user1,
        )
        note.bookmarked_by.add(self.user2)
        self.assertIn(self.user2, note.bookmarked_by.all())
        self.assertIn(note, self.user2.bookmarked_notes.all())


class AuthenticationViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alexsmith",
            email="alex@university.edu",
            password="StrongPassword123!",
        )

    def test_register_get(self):
        """GET /register/ displays registration form."""
        response = self.client.get(reverse("notes:register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/register.html")
        self.assertContains(response, "Create your SNES account")

    def test_register_post_success(self):
        """POST /register/ with valid data creates user and redirects to home."""
        response = self.client.post(
            reverse("notes:register"),
            {
                "username": "newscholar",
                "email": "newscholar@university.edu",
                "password1": "SecurePass987!",
                "password2": "SecurePass987!",
            },
        )
        self.assertRedirects(response, reverse("notes:home"))
        self.assertTrue(User.objects.filter(username="newscholar").exists())

    def test_register_post_mismatched_password(self):
        """POST /register/ with mismatched passwords returns errors."""
        response = self.client.post(
            reverse("notes:register"),
            {
                "username": "mismatchuser",
                "email": "mismatch@university.edu",
                "password1": "SecurePass987!",
                "password2": "DifferentPass987!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatchuser").exists())
        self.assertContains(response, "password fields")

    def test_login_get(self):
        """GET /login/ displays login form."""
        response = self.client.get(reverse("notes:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/login.html")
        self.assertContains(response, "Sign in to your account")

    def test_login_post_success(self):
        """POST /login/ logs the user in and redirects to home."""
        response = self.client.post(
            reverse("notes:login"),
            {
                "username": "alexsmith",
                "password": "StrongPassword123!",
            },
        )
        self.assertRedirects(response, reverse("notes:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_post_invalid_credentials(self):
        """POST /login/ with wrong password fails and displays error."""
        response = self.client.post(
            reverse("notes:login"),
            {
                "username": "alexsmith",
                "password": "WrongPassword!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_logout_post(self):
        """POST /logout/ logs user out and redirects to home (Django 5.2 compliant)."""
        self.client.login(username="alexsmith", password="StrongPassword123!")
        response = self.client.post(reverse("notes:logout"))
        self.assertRedirects(response, reverse("notes:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_get_method_not_allowed(self):
        """GET /logout/ returns HTTP 405 Method Not Allowed in Django 5.2."""
        self.client.login(username="alexsmith", password="StrongPassword123!")
        response = self.client.get(reverse("notes:logout"))
        self.assertEqual(response.status_code, 405)


class NavbarTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="studious_user",
            password="StrongPassword123!",
        )

    def test_anonymous_navbar_view(self):
        """Anonymous visitors see Login, Register, Browse Notes."""
        response = self.client.get(reverse("notes:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Browse Notes")
        self.assertContains(response, "Login")
        self.assertContains(response, "Register")
        self.assertNotContains(response, "Logout")
        self.assertNotContains(response, "Upload Note")
        self.assertNotContains(response, "My Study List")

    def test_authenticated_navbar_view(self):
        """Authenticated users see username, Upload Note, My Study List, and Logout."""
        self.client.login(username="studious_user", password="StrongPassword123!")
        response = self.client.get(reverse("notes:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "studious_user")
        self.assertContains(response, "Upload Note")
        self.assertContains(response, "My Study List")
        self.assertContains(response, "Logout")


class AdminModerationTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="adminuser",
            email="admin@snes.edu",
            password="SuperPassword123!",
        )
        self.user = User.objects.create_user(
            username="noteuploader",
            password="UserPassword123!",
        )
        fake_pdf = SimpleUploadedFile(
            "flagged_doc.pdf", VALID_PDF_BYTES, content_type="application/pdf"
        )
        self.note1 = Note.objects.create(
            title="Reported Note 1",
            file=fake_pdf,
            subject="Physics",
            topic="Thermodynamics",
            uploader=self.user,
            report_count=5,
        )
        self.note2 = Note.objects.create(
            title="Clean Note 2",
            file=fake_pdf,
            subject="Chemistry",
            topic="Organic",
            uploader=self.user,
            report_count=0,
        )

    def test_admin_registration(self):
        """Note model is registered in admin with correct configuration."""
        self.assertIn(Note, site._registry)
        model_admin = site._registry[Note]
        self.assertIsInstance(model_admin, NoteAdmin)

        self.assertEqual(
            model_admin.list_display,
            (
                "title",
                "category",
                "year",
                "subject",
                "uploader",
                "downloads",
                "report_count",
                "created_at",
            ),
        )
        self.assertEqual(
            model_admin.list_filter,
            ("category", "year", "file_type", "created_at"),
        )
        self.assertEqual(
            model_admin.search_fields,
            ("title", "subject", "topic", "uploader__username"),
        )
        self.assertEqual(
            model_admin.ordering,
            ("-report_count", "-created_at"),
        )

    def test_reset_report_count_action(self):
        """Admin action reset_report_count resets report_count to 0."""
        model_admin = site._registry[Note]
        queryset = Note.objects.filter(pk=self.note1.pk)

        # Create dummy request with messages support
        factory = RequestFactory()
        request = factory.get("/admin/notes/note/")
        setattr(request, "session", {})
        setattr(request, "_messages", FallbackStorage(request))

        reset_report_count(model_admin, request, queryset)

        self.note1.refresh_from_db()
        self.assertEqual(self.note1.report_count, 0)


def create_test_pdf(num_pages=1) -> bytes:
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class NoteFormValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author1", password="SecurePassword123!"
        )

    def test_upload_valid_pdf_form(self):
        """Valid PDF form cleaning extracts page count and sets file_type = 'PDF'."""
        pdf_bytes = create_test_pdf(num_pages=3)
        file_obj = SimpleUploadedFile(
            "calculus_notes.pdf", pdf_bytes, content_type="application/pdf"
        )
        form = NoteUploadForm(
            data={
                "title": "Calculus III Multivariable",
                "subject": "Mathematics",
                "topic": "Vector Fields",
                "category": Note.Category.NOTES,
                "year": 2024,
                "description": "Comprehensive notes covering Green's theorem.",
            },
            files={"file": file_obj},
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_file_type, "PDF")
        self.assertEqual(form.cleaned_page_count, 3)

    def test_upload_valid_pptx_form(self):
        """Valid PPTX form cleaning sets file_type = 'PPTX' and page_count = None."""
        pptx_file = SimpleUploadedFile(
            "algorithm_slides.pptx",
            b"PK\x03\x04fake pptx binary",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        form = NoteUploadForm(
            data={
                "title": "Sorting Algorithms Slides",
                "subject": "Computer Science",
                "topic": "QuickSort & MergeSort",
                "category": Note.Category.NOTES,
                "year": 2025,
            },
            files={"file": pptx_file},
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_file_type, "PPTX")
        self.assertIsNone(form.cleaned_page_count)

    def test_upload_corrupt_pdf_rejected(self):
        """Corrupt or unreadable PDF is rejected with user-friendly error message."""
        bad_file = SimpleUploadedFile(
            "broken_doc.pdf",
            b"This is not a real PDF file contents",
            content_type="application/pdf",
        )
        form = NoteUploadForm(
            data={
                "title": "Broken PDF Note",
                "subject": "Physics",
                "topic": "Mechanics",
                "category": Note.Category.NOTES,
                "year": 2024,
            },
            files={"file": bad_file},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("corrupt or could not be read", form.errors["file"][0])

    def test_upload_unsupported_extension_rejected(self):
        """Uploading files with unsupported extensions (e.g. .docx, .txt) is rejected."""
        doc_file = SimpleUploadedFile(
            "essay.docx",
            b"Word document content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        form = NoteUploadForm(
            data={
                "title": "Essay Draft",
                "subject": "Literature",
                "topic": "Modernism",
                "category": Note.Category.NOTES,
                "year": 2024,
            },
            files={"file": doc_file},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("Only PDF (.pdf) and PowerPoint (.pptx)", form.errors["file"][0])

    def test_upload_exe_rejected(self):
        """Uploading executable (.exe) files is strictly rejected."""
        exe_file = SimpleUploadedFile(
            "malicious.exe",
            b"MZ\x90\x00binary",
            content_type="application/octet-stream",
        )
        form = NoteUploadForm(
            data={
                "title": "Malicious Executable",
                "subject": "Security",
                "topic": "Exploits",
                "category": Note.Category.NOTES,
                "year": 2024,
            },
            files={"file": exe_file},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("Only PDF (.pdf) and PowerPoint (.pptx)", form.errors["file"][0])

    def test_upload_txt_rejected(self):
        """Uploading plain text (.txt) files is strictly rejected."""
        txt_file = SimpleUploadedFile(
            "notes.txt",
            b"plain text content",
            content_type="text/plain",
        )
        form = NoteUploadForm(
            data={
                "title": "Plain Text Notes",
                "subject": "Literature",
                "topic": "Poetry",
                "category": Note.Category.NOTES,
                "year": 2024,
            },
            files={"file": txt_file},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("Only PDF (.pdf) and PowerPoint (.pptx)", form.errors["file"][0])

    def test_upload_file_size_exceeded_rejected(self):
        """Files exceeding 25 MB are rejected by validation."""
        fake_large_file = SimpleUploadedFile(
            "huge_file.pdf",
            b"x" * 10,  # small dummy content
            content_type="application/pdf",
        )
        # artificially set size attribute above 25 MB (26 MB)
        fake_large_file.size = 26 * 1024 * 1024
        form = NoteUploadForm(
            data={
                "title": "Huge Notes",
                "subject": "Biology",
                "topic": "Genetics",
                "category": Note.Category.NOTES,
                "year": 2024,
            },
            files={"file": fake_large_file},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("exceeds the 25 MB limit", form.errors["file"][0])

    def test_note_edit_form_valid(self):
        """NoteEditForm updates metadata without requiring a file."""
        note = Note.objects.create(
            title="Original Title",
            subject="History",
            topic="WWII",
            category=Note.Category.NOTES,
            year=2023,
            uploader=self.user,
        )
        edit_form = NoteEditForm(
            instance=note,
            data={
                "title": "Updated Title",
                "subject": "World History",
                "topic": "Pacific Theater",
                "category": Note.Category.CHEAT_SHEET,
                "year": 2024,
                "description": "Updated detailed notes.",
            },
        )
        self.assertTrue(edit_form.is_valid(), edit_form.errors)
        saved = edit_form.save()
        self.assertEqual(saved.title, "Updated Title")
        self.assertEqual(saved.subject, "World History")
        self.assertEqual(saved.category, Note.Category.CHEAT_SHEET)


class NoteViewsAndPermissionsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.uploader = User.objects.create_user(
            username="prof_uploader", password="SecurePassword123!"
        )
        self.other_user = User.objects.create_user(
            username="other_student", password="SecurePassword123!"
        )

        pdf_bytes = create_test_pdf(num_pages=4)
        pdf_file = SimpleUploadedFile(
            "sample_calculus.pdf", pdf_bytes, content_type="application/pdf"
        )
        self.pdf_note = Note.objects.create(
            title="Multivariable Calculus Guide",
            description="Complete semester formulas and exam prep.",
            file=pdf_file,
            subject="Mathematics",
            topic="Calculus III",
            category=Note.Category.CHEAT_SHEET,
            year=2024,
            uploader=self.uploader,
            page_count=4,
            file_type="PDF",
        )

        pptx_file = SimpleUploadedFile(
            "intro_os_slides.pptx",
            b"fake pptx presentation bytes",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        self.pptx_note = Note.objects.create(
            title="OS Scheduling Slides",
            description="Lecture slides covering round-robin and priority scheduling.",
            file=pptx_file,
            subject="Computer Science",
            topic="Operating Systems",
            category=Note.Category.NOTES,
            year=2025,
            uploader=self.uploader,
            file_type="PPTX",
        )

    def test_upload_view_requires_login(self):
        """Anonymous user is redirected to login when accessing upload."""
        response = self.client.get(reverse("notes:upload_note"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("notes:login"), response.url)

    def test_upload_view_get(self):
        """Authenticated user can view upload form."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        response = self.client.get(reverse("notes:upload_note"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/upload_note.html")
        self.assertContains(response, "Upload Study Material")

    def test_upload_view_post_pdf_success(self):
        """Authenticated user uploads valid PDF, page count is saved, redirected to detail."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        pdf_bytes = create_test_pdf(num_pages=5)
        pdf_file = SimpleUploadedFile(
            "chemistry_notes.pdf", pdf_bytes, content_type="application/pdf"
        )
        response = self.client.post(
            reverse("notes:upload_note"),
            {
                "title": "Organic Reactions Summary",
                "subject": "Chemistry",
                "topic": "Stereochemistry",
                "category": Note.Category.NOTES,
                "year": 2026,
                "description": "Comprehensive reactions cheatsheet.",
                "file": pdf_file,
            },
        )
        new_note = Note.objects.get(title="Organic Reactions Summary")
        self.assertRedirects(response, reverse("notes:note_detail", kwargs={"pk": new_note.pk}))
        self.assertEqual(new_note.uploader, self.uploader)
        self.assertEqual(new_note.file_type, "PDF")
        self.assertEqual(new_note.page_count, 5)

    def test_upload_view_post_pptx_success(self):
        """Authenticated user uploads PPTX, file_type='PPTX', page_count=None."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        pptx_file = SimpleUploadedFile(
            "db_slides.pptx",
            b"fake pptx content",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        response = self.client.post(
            reverse("notes:upload_note"),
            {
                "title": "Database Normalization Slides",
                "subject": "Computer Science",
                "topic": "SQL & Normalization",
                "category": Note.Category.NOTES,
                "year": 2026,
                "file": pptx_file,
            },
        )
        new_note = Note.objects.get(title="Database Normalization Slides")
        self.assertRedirects(response, reverse("notes:note_detail", kwargs={"pk": new_note.pk}))
        self.assertEqual(new_note.file_type, "PPTX")
        self.assertIsNone(new_note.page_count)

    def test_note_detail_view_anonymous_access(self):
        """Detail view is publicly accessible and displays full metadata."""
        response = self.client.get(
            reverse("notes:note_detail", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/note_detail.html")
        self.assertContains(response, self.pdf_note.title)
        self.assertContains(response, self.pdf_note.subject)
        self.assertContains(response, self.pdf_note.topic)
        self.assertContains(response, "Cheat Sheet / Summary")
        self.assertContains(response, "4 pages")
        self.assertContains(response, "<iframe", html=False)

    def test_note_detail_pptx_preview_and_local_notice(self):
        """PPTX note detail renders Office Online iframe and local dev notice."""
        response = self.client.get(
            reverse("notes:note_detail", kwargs={"pk": self.pptx_note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "view.officeapps.live.com")
        self.assertContains(response, "Local Development Notice")
        self.assertContains(response, "Render")

    def test_note_detail_owner_actions_visibility(self):
        """Edit and Delete buttons appear ONLY for note uploader."""
        # Anonymous visitor sees neither
        anon_resp = self.client.get(
            reverse("notes:note_detail", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertNotContains(anon_resp, reverse("notes:edit_note", kwargs={"pk": self.pdf_note.pk}))
        self.assertNotContains(anon_resp, reverse("notes:delete_note", kwargs={"pk": self.pdf_note.pk}))

        # Other logged-in student sees neither
        self.client.login(username="other_student", password="SecurePassword123!")
        other_resp = self.client.get(
            reverse("notes:note_detail", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertNotContains(other_resp, reverse("notes:edit_note", kwargs={"pk": self.pdf_note.pk}))
        self.assertNotContains(other_resp, reverse("notes:delete_note", kwargs={"pk": self.pdf_note.pk}))

        # Uploader sees both Edit and Delete
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        owner_resp = self.client.get(
            reverse("notes:note_detail", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertContains(owner_resp, reverse("notes:edit_note", kwargs={"pk": self.pdf_note.pk}))
        self.assertContains(owner_resp, reverse("notes:delete_note", kwargs={"pk": self.pdf_note.pk}))

    def test_edit_note_view_permission_enforcement(self):
        """Non-uploader receives 403 Forbidden when attempting to edit note."""
        self.client.login(username="other_student", password="SecurePassword123!")
        # GET attempt
        resp_get = self.client.get(
            reverse("notes:edit_note", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertEqual(resp_get.status_code, 403)
        # POST attempt
        resp_post = self.client.post(
            reverse("notes:edit_note", kwargs={"pk": self.pdf_note.pk}),
            {"title": "Hacked Title", "subject": "Math", "topic": "Diff", "category": "NOTES", "year": 2024},
        )
        self.assertEqual(resp_post.status_code, 403)

    def test_edit_note_view_owner_success(self):
        """Note owner can successfully update note metadata."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        response = self.client.post(
            reverse("notes:edit_note", kwargs={"pk": self.pdf_note.pk}),
            {
                "title": "Calculus III Advanced Cheatsheet",
                "subject": "Mathematics",
                "topic": "Stokes & Gauss Theorems",
                "category": Note.Category.CHEAT_SHEET,
                "year": 2025,
                "description": "Updated exam review.",
            },
        )
        self.assertRedirects(response, reverse("notes:note_detail", kwargs={"pk": self.pdf_note.pk}))
        self.pdf_note.refresh_from_db()
        self.assertEqual(self.pdf_note.title, "Calculus III Advanced Cheatsheet")
        self.assertEqual(self.pdf_note.topic, "Stokes & Gauss Theorems")

    def test_delete_note_view_permission_enforcement(self):
        """Non-uploader receives 403 Forbidden when attempting to delete note."""
        self.client.login(username="other_student", password="SecurePassword123!")
        response = self.client.post(
            reverse("notes:delete_note", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Note.objects.filter(pk=self.pdf_note.pk).exists())

    def test_delete_note_view_requires_post(self):
        """GET request to delete_note endpoint returns 405 Method Not Allowed."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        response = self.client.get(
            reverse("notes:delete_note", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_note_view_owner_success(self):
        """Note owner can delete note and its file via POST, redirects to dashboard."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        pk = self.pdf_note.pk
        response = self.client.post(
            reverse("notes:delete_note", kwargs={"pk": pk})
        )
        self.assertRedirects(response, reverse("notes:my_dashboard"))
        self.assertFalse(Note.objects.filter(pk=pk).exists())

    def test_dashboard_view_displays_uploads_and_study_list(self):
        """Dashboard displays My Uploads and My Study List for authenticated user."""
        self.client.login(username="prof_uploader", password="SecurePassword123!")
        self.pdf_note.bookmarked_by.add(self.uploader)

        response = self.client.get(reverse("notes:my_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/dashboard.html")
        self.assertContains(response, "My Uploads")
        self.assertContains(response, "My Study List")
        self.assertContains(response, self.pdf_note.title)
        self.assertContains(response, self.pptx_note.title)

    def test_controlled_download_increments_count_and_serves_file(self):
        """Download endpoint increments download count atomically and returns attachment."""
        initial_downloads = self.pdf_note.downloads
        response = self.client.get(
            reverse("notes:download_note", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.pdf_note.refresh_from_db()
        self.assertEqual(self.pdf_note.downloads, initial_downloads + 1)
        self.assertIn("attachment;", response.headers.get("Content-Disposition", ""))

    def test_report_note_endpoint(self):
        """Authenticated user can report note via POST, increments report_count atomically."""
        self.client.login(username="other_student", password="SecurePassword123!")
        initial_reports = self.pdf_note.report_count

        response = self.client.post(
            reverse("notes:report_note", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertRedirects(
            response, reverse("notes:note_detail", kwargs={"pk": self.pdf_note.pk})
        )
        self.pdf_note.refresh_from_db()
        self.assertEqual(self.pdf_note.report_count, initial_reports + 1)

    def test_report_note_get_method_not_allowed(self):
        """GET request to report_note returns 405 Method Not Allowed."""
        self.client.login(username="other_student", password="SecurePassword123!")
        response = self.client.get(
            reverse("notes:report_note", kwargs={"pk": self.pdf_note.pk})
        )
        self.assertEqual(response.status_code, 405)


class HTMXInteractivityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username="student_voter", password="SecurePassword123!"
        )
        self.user2 = User.objects.create_user(
            username="student_peer", password="SecurePassword123!"
        )
        self.author = User.objects.create_user(
            username="prof_author", password="SecurePassword123!"
        )
        pdf_bytes = create_test_pdf(num_pages=2)
        pdf_file = SimpleUploadedFile(
            "study_notes.pdf", pdf_bytes, content_type="application/pdf"
        )
        self.note = Note.objects.create(
            title="Algorithm Complexity Cheat Sheet",
            subject="Computer Science",
            topic="Big-O Analysis",
            category=Note.Category.CHEAT_SHEET,
            year=2025,
            uploader=self.author,
            file=pdf_file,
            file_type="PDF",
            page_count=2,
        )

    def test_upvote_anonymous_redirect(self):
        """Anonymous POST to toggle_upvote returns 204 with HX-Redirect header to login."""
        response = self.client.post(
            reverse("notes:toggle_upvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response.headers.get("HX-Redirect"),
            f"/login/?next=/note/{self.note.pk}/",
        )
        self.assertEqual(self.note.vote_score, 0)

    def test_downvote_anonymous_redirect(self):
        """Anonymous POST to toggle_downvote returns 204 with HX-Redirect header to login."""
        response = self.client.post(
            reverse("notes:toggle_downvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response.headers.get("HX-Redirect"),
            f"/login/?next=/note/{self.note.pk}/",
        )
        self.assertEqual(self.note.vote_score, 0)

    def test_bookmark_anonymous_redirect(self):
        """Anonymous POST to toggle_bookmark returns 204 with HX-Redirect header to login."""
        response = self.client.post(
            reverse("notes:toggle_bookmark", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response.headers.get("HX-Redirect"),
            f"/login/?next=/note/{self.note.pk}/",
        )
        self.assertNotIn(self.note, self.user1.bookmarked_notes.all())

    def test_toggle_upvote_lifecycle(self):
        """Authenticated user can upvote (score +1) and clicking again cancels upvote (score 0)."""
        self.client.login(username="student_voter", password="SecurePassword123!")

        # 1. First upvote -> score increments to 1
        response = self.client.post(
            reverse("notes:toggle_upvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/partials/vote_controls.html")
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, 1)
        self.assertTrue(self.note.upvoted_by.filter(pk=self.user1.pk).exists())
        self.assertContains(response, f'id="vote-controls-{self.note.pk}"')
        self.assertContains(response, "bg-emerald-500")

        # 2. Second upvote -> cancels upvote, score reverts to 0
        response2 = self.client.post(
            reverse("notes:toggle_upvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response2.status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, 0)
        self.assertFalse(self.note.upvoted_by.filter(pk=self.user1.pk).exists())
        self.assertNotContains(response2, "bg-emerald-500")

    def test_toggle_downvote_lifecycle(self):
        """Authenticated user can downvote (score -1) and clicking again cancels downvote (score 0)."""
        self.client.login(username="student_voter", password="SecurePassword123!")

        # 1. First downvote -> score decrements to -1
        response = self.client.post(
            reverse("notes:toggle_downvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/partials/vote_controls.html")
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, -1)
        self.assertTrue(self.note.downvoted_by.filter(pk=self.user1.pk).exists())
        self.assertContains(response, f'id="vote-controls-{self.note.pk}"')
        self.assertContains(response, "bg-rose-500")

        # 2. Second downvote -> cancels downvote, score reverts to 0
        response2 = self.client.post(
            reverse("notes:toggle_downvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response2.status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, 0)
        self.assertFalse(self.note.downvoted_by.filter(pk=self.user1.pk).exists())
        self.assertNotContains(response2, "bg-rose-500")

    def test_mutual_exclusion_upvote_then_downvote(self):
        """Upvoting (+1) and then clicking downvote immediately flips vote score to -1."""
        self.client.login(username="student_voter", password="SecurePassword123!")

        # Upvote -> +1
        self.client.post(
            reverse("notes:toggle_upvote", kwargs={"pk": self.note.pk})
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, 1)
        self.assertTrue(self.note.upvoted_by.filter(pk=self.user1.pk).exists())
        self.assertFalse(self.note.downvoted_by.filter(pk=self.user1.pk).exists())

        # Downvote -> flips to -1 (removes upvote AND adds downvote)
        response = self.client.post(
            reverse("notes:toggle_downvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, -1)
        self.assertFalse(self.note.upvoted_by.filter(pk=self.user1.pk).exists())
        self.assertTrue(self.note.downvoted_by.filter(pk=self.user1.pk).exists())
        self.assertContains(response, "bg-rose-500")
        self.assertNotContains(response, "bg-emerald-500")

    def test_mutual_exclusion_downvote_then_upvote(self):
        """Downvoting (-1) and then clicking upvote immediately flips vote score to +1."""
        self.client.login(username="student_voter", password="SecurePassword123!")

        # Downvote -> -1
        self.client.post(
            reverse("notes:toggle_downvote", kwargs={"pk": self.note.pk})
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, -1)

        # Upvote -> flips to +1 (removes downvote AND adds upvote)
        response = self.client.post(
            reverse("notes:toggle_upvote", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.vote_score, 1)
        self.assertTrue(self.note.upvoted_by.filter(pk=self.user1.pk).exists())
        self.assertFalse(self.note.downvoted_by.filter(pk=self.user1.pk).exists())
        self.assertContains(response, "bg-emerald-500")
        self.assertNotContains(response, "bg-rose-500")

    def test_toggle_bookmark_lifecycle(self):
        """Authenticated user bookmarks note, adds to user.bookmarked_notes; clicking again removes it."""
        self.client.login(username="student_voter", password="SecurePassword123!")

        # 1. Bookmark note
        response = self.client.post(
            reverse("notes:toggle_bookmark", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/partials/bookmark_button.html")
        self.assertTrue(self.note.bookmarked_by.filter(pk=self.user1.pk).exists())
        self.assertIn(self.note, self.user1.bookmarked_notes.all())
        self.assertContains(response, f'id="bookmark-btn-{self.note.pk}"')
        self.assertContains(response, "Saved")

        # 2. Toggle off bookmark
        response2 = self.client.post(
            reverse("notes:toggle_bookmark", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response2.status_code, 200)
        self.assertFalse(self.note.bookmarked_by.filter(pk=self.user1.pk).exists())
        self.assertNotIn(self.note, self.user1.bookmarked_notes.all())
        self.assertContains(response2, "Save to Study List")

    def test_detail_view_includes_partials(self):
        """Note detail page embeds vote_controls and bookmark_button partials."""
        self.client.login(username="student_voter", password="SecurePassword123!")
        response = self.client.get(
            reverse("notes:note_detail", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="vote-controls-{self.note.pk}"')
        self.assertContains(response, f'id="bookmark-btn-{self.note.pk}"')
        self.assertContains(response, 'hx-post="')
        self.assertContains(response, 'hx-swap="outerHTML"')

    def test_dashboard_study_list_includes_bookmark_controls(self):
        """Dashboard Study List tab allows users to toggle/remove saved notes via bookmark control."""
        self.client.login(username="student_voter", password="SecurePassword123!")
        self.note.bookmarked_by.add(self.user1)

        response = self.client.get(reverse("notes:my_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="bookmark-btn-{self.note.pk}"')
        self.assertContains(response, "Saved")

    def test_get_methods_not_allowed_for_toggles(self):
        """GET requests to toggle endpoints return 405 Method Not Allowed."""
        self.client.login(username="student_voter", password="SecurePassword123!")
        for url_name in ("notes:toggle_upvote", "notes:toggle_downvote", "notes:toggle_bookmark"):
            with self.subTest(url=url_name):
                resp = self.client.get(reverse(url_name, kwargs={"pk": self.note.pk}))
                self.assertEqual(resp.status_code, 405)


class DiscoveryHomepageAndBrowseTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username="prof_turing", password="SecurePassword123!"
        )
        self.student_a = User.objects.create_user(
            username="student_ada", password="SecurePassword123!"
        )
        self.student_b = User.objects.create_user(
            username="student_boole", password="SecurePassword123!"
        )
        self.student_c = User.objects.create_user(
            username="student_curie", password="SecurePassword123!"
        )

        pdf_bytes = create_test_pdf(num_pages=14)
        pdf_file = SimpleUploadedFile(
            "discrete_math.pdf", pdf_bytes, content_type="application/pdf"
        )
        self.note1 = Note.objects.create(
            title="Discrete Mathematics Master Guide",
            description="Complete coverage of graph theory and propositional logic.",
            file=pdf_file,
            subject="Mathematics",
            topic="Graph Theory",
            category=Note.Category.NOTES,
            year=2026,
            uploader=self.author,
            page_count=14,
            file_type="PDF",
            downloads=20,
        )

        pptx_file = SimpleUploadedFile(
            "deep_learning_slides.pptx",
            b"PK\x03\x04fake pptx slides",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        self.note2 = Note.objects.create(
            title="Deep Learning Convolutional Networks",
            description="CNN architectures and backpropagation slides.",
            file=pptx_file,
            subject="Computer Science",
            topic="Neural Networks",
            category=Note.Category.CHEAT_SHEET,
            year=2025,
            uploader=self.author,
            file_type="PPTX",
            downloads=5,
        )

        pdf_file_pyq = SimpleUploadedFile(
            "algorithms_pyq_2024.pdf", pdf_bytes, content_type="application/pdf"
        )
        self.note3 = Note.objects.create(
            title="Algorithms Final Exam 2024 Past Paper",
            description="Official past questions with dynamic programming solutions.",
            file=pdf_file_pyq,
            subject="Computer Science",
            topic="Dynamic Programming",
            category=Note.Category.PYQ,
            year=2024,
            uploader=self.author,
            page_count=8,
            file_type="PDF",
            downloads=50,
        )

        pdf_file_assign = SimpleUploadedFile(
            "physics_assignment.pdf", pdf_bytes, content_type="application/pdf"
        )
        self.note4 = Note.objects.create(
            title="Quantum Mechanics Assignment 2",
            description="Schrodinger equation problem set with verified proofs.",
            file=pdf_file_assign,
            subject="Physics",
            topic="Quantum Mechanics",
            category=Note.Category.ASSIGNMENT,
            year=2023,
            uploader=self.author,
            page_count=5,
            file_type="PDF",
            downloads=1,
        )

        # Set up votes for quality_score verification:
        # formula: quality_score = (upvotes - downvotes) + (downloads * 0.2)
        # Note 3: 3 upvotes, 0 downvotes, 50 downloads -> (3 - 0) + 50*0.2 = 13.0
        self.note3.upvoted_by.add(self.student_a, self.student_b, self.student_c)

        # Note 1: 2 upvotes, 0 downvotes, 20 downloads -> (2 - 0) + 20*0.2 = 6.0
        self.note1.upvoted_by.add(self.student_a, self.student_b)

        # Note 2: 1 upvote, 0 downvotes, 5 downloads -> (1 - 0) + 5*0.2 = 2.0
        self.note2.upvoted_by.add(self.student_a)

        # Note 4: 0 upvotes, 2 downvotes, 1 download -> (0 - 2) + 1*0.2 = -1.8
        self.note4.downvoted_by.add(self.student_a, self.student_b)

    def test_anonymous_access_homepage(self):
        """Anonymous visitor can access homepage (200), seeing hero search and ranked sections."""
        response = self.client.get(reverse("notes:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/home.html")
        self.assertTemplateUsed(response, "notes/partials/note_card.html")

        # Check Hero Search elements
        self.assertContains(response, 'action="/browse/"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, "Lecture Notes")
        self.assertContains(response, "Cheat Sheets")
        self.assertContains(response, "PYQs")
        self.assertContains(response, "Assignments")
        self.assertContains(response, "2026")
        self.assertContains(response, "2025")
        self.assertContains(response, "2024")
        self.assertContains(response, "2023")

        # Check section headings and links
        self.assertContains(response, "Top Rated & Most Helpful")
        self.assertContains(response, "Recently Uploaded")
        self.assertContains(response, "View All Notes")

        # Check that top_notes context contains our notes ordered by quality_score
        top_notes = list(response.context["top_notes"])
        self.assertEqual(top_notes[0], self.note3)
        self.assertEqual(top_notes[1], self.note1)

    def test_anonymous_access_browse(self):
        """Anonymous visitor can access /browse/ (200) and view note cards."""
        response = self.client.get(reverse("notes:browse"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notes/browse.html")
        self.assertTemplateUsed(response, "notes/partials/note_card.html")
        self.assertContains(response, "Browse Study Materials")
        self.assertContains(response, self.note1.title)
        self.assertContains(response, self.note2.title)
        self.assertContains(response, self.note3.title)
        self.assertContains(response, self.note4.title)

    def test_note_card_rendering_details(self):
        """Note card partial renders title link, badges, format, page count, and metrics."""
        response = self.client.get(reverse("notes:browse"))
        self.assertEqual(response.status_code, 200)

        # Title link
        self.assertContains(response, reverse("notes:note_detail", kwargs={"pk": self.note1.pk}))
        # Category badges
        self.assertContains(response, "Lecture Notes")
        self.assertContains(response, "Cheat Sheet / Summary")
        self.assertContains(response, "Past Exam Paper (PYQ)")
        # Year badges
        self.assertContains(response, "2026")
        self.assertContains(response, "2025")
        # File format & page count
        self.assertContains(response, "14 pages &bull; PDF")
        self.assertContains(response, "PPTX")
        # Metrics: Net votes, downloads, and uploader
        self.assertContains(response, "prof_turing")
        self.assertContains(response, "▲")
        self.assertContains(response, "⬇")

    def test_search_q_keyword_matching(self):
        """Keyword search ?q= matches title, subject, topic, and description case-insensitively."""
        # 1. Matches title
        resp1 = self.client.get(reverse("notes:browse"), {"q": "Master Guide"})
        self.assertContains(resp1, self.note1.title)
        self.assertNotContains(resp1, self.note2.title)

        # 2. Matches subject
        resp2 = self.client.get(reverse("notes:browse"), {"q": "PHYSICS"})
        self.assertContains(resp2, self.note4.title)
        self.assertNotContains(resp2, self.note1.title)

        # 3. Matches topic
        resp3 = self.client.get(reverse("notes:browse"), {"q": "Neural Networks"})
        self.assertContains(resp3, self.note2.title)
        self.assertNotContains(resp3, self.note3.title)

        # 4. Matches description
        resp4 = self.client.get(reverse("notes:browse"), {"q": "Schrodinger equation"})
        self.assertContains(resp4, self.note4.title)
        self.assertNotContains(resp4, self.note1.title)

    def test_category_filter(self):
        """Filter by ?category= isolates only notes in that category."""
        resp = self.client.get(reverse("notes:browse"), {"category": "PYQ"})
        self.assertContains(resp, self.note3.title)
        self.assertNotContains(resp, self.note1.title)
        self.assertNotContains(resp, self.note2.title)
        self.assertNotContains(resp, self.note4.title)

    def test_year_filter(self):
        """Filter by ?year= isolates notes from the selected academic year."""
        resp = self.client.get(reverse("notes:browse"), {"year": "2024"})
        self.assertContains(resp, self.note3.title)
        self.assertNotContains(resp, self.note1.title)
        self.assertNotContains(resp, self.note2.title)

        # Invalid year does not crash
        resp_invalid = self.client.get(reverse("notes:browse"), {"year": "invalid_year"})
        self.assertEqual(resp_invalid.status_code, 200)

    def test_subject_filter(self):
        """Filter by ?subject= performs case-insensitive subject substring matching."""
        resp = self.client.get(reverse("notes:browse"), {"subject": "computer"})
        self.assertContains(resp, self.note2.title)
        self.assertContains(resp, self.note3.title)
        self.assertNotContains(resp, self.note1.title)
        self.assertNotContains(resp, self.note4.title)

    def test_combined_filters(self):
        """Seamlessly combines q, category, year, and subject parameters."""
        resp = self.client.get(
            reverse("notes:browse"),
            {
                "q": "Past Paper",
                "category": "PYQ",
                "year": "2024",
                "subject": "Computer Science",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.note3.title)
        self.assertNotContains(resp, self.note1.title)
        self.assertNotContains(resp, self.note2.title)
        self.assertNotContains(resp, self.note4.title)

    def test_quality_score_composite_ordering(self):
        """
        Verify composite quality_score ordering:
        formula: (upvotes - downvotes) + (downloads * 0.2)
        Note 3: (3 - 0) + 50*0.2 = 13.0
        Note 1: (2 - 0) + 20*0.2 = 6.0
        Note 2: (1 - 0) + 5*0.2  = 2.0
        Note 4: (0 - 2) + 1*0.2  = -1.8
        """
        resp = self.client.get(reverse("notes:browse"), {"sort": "top"})
        self.assertEqual(resp.status_code, 200)
        notes = list(resp.context["page_obj"])
        self.assertEqual([n.pk for n in notes], [self.note3.pk, self.note1.pk, self.note2.pk, self.note4.pk])

    def test_sort_recent_and_downloads(self):
        """Sort by recent (-created_at) and downloads (-downloads) options."""
        # 1. Most downloaded
        resp_dl = self.client.get(reverse("notes:browse"), {"sort": "downloads"})
        notes_dl = list(resp_dl.context["page_obj"])
        self.assertEqual(notes_dl[0].pk, self.note3.pk)  # 50 downloads
        self.assertEqual(notes_dl[1].pk, self.note1.pk)  # 20 downloads

        # 2. Most recent
        resp_rec = self.client.get(reverse("notes:browse"), {"sort": "recent"})
        notes_rec = list(resp_rec.context["page_obj"])
        self.assertEqual(notes_rec[0].pk, self.note4.pk)  # Created last

    def test_pagination_and_query_param_preservation(self):
        """Paginator limits to 12 items per page and preserves query parameters across page links."""
        pdf_bytes = create_test_pdf(num_pages=1)
        # Create 10 more notes so total = 14
        for i in range(10):
            Note.objects.create(
                title=f"Bulk Paged Note {i}",
                file=SimpleUploadedFile(f"bulk_{i}.pdf", pdf_bytes, content_type="application/pdf"),
                subject="Mathematics",
                topic=f"Topic {i}",
                category=Note.Category.NOTES,
                year=2026,
                uploader=self.author,
            )

        resp_all_p1 = self.client.get(reverse("notes:browse"), {"sort": "recent", "page": "1"})
        self.assertEqual(len(resp_all_p1.context["page_obj"]), 12)
        self.assertTrue(resp_all_p1.context["page_obj"].has_next())
        self.assertContains(resp_all_p1, "page=2")
        self.assertContains(resp_all_p1, "sort=recent")

        resp_all_p2 = self.client.get(reverse("notes:browse"), {"sort": "recent", "page": "2"})
        self.assertEqual(len(resp_all_p2.context["page_obj"]), 2)

    def test_empty_state_and_reset_filters(self):
        """Displays empty state with Reset Filters button when no notes match search."""
        resp = self.client.get(reverse("notes:browse"), {"q": "NonExistentQueryZXY999"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No matching notes found")
        self.assertContains(resp, "Reset Filters")
        self.assertContains(resp, reverse("notes:browse"))

    def test_base_navbar_browse_link(self):
        """Navbar 'Browse Notes' link routes to reverse('notes:browse')."""
        resp = self.client.get(reverse("notes:home"))
        self.assertContains(resp, reverse("notes:browse"))



