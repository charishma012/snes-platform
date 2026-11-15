from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from .admin import NoteAdmin, reset_report_count
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
