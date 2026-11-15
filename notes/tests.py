from django.test import TestCase, Client
from django.urls import reverse


class HomePageViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_status_code(self):
        """Root URL '/' returns HTTP 200."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_home_page_named_url(self):
        """Named URL 'notes:home' reverses to '/' and returns HTTP 200."""
        url = reverse('notes:home')
        self.assertEqual(url, '/')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_home_page_templates_used(self):
        """Home page renders with base.html and notes/home.html."""
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'notes/home.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_home_page_content(self):
        """Home page contains key branding and navigation elements."""
        response = self.client.get('/')
        self.assertContains(response, 'SNES')
        self.assertContains(response, 'Smart Notes')
        self.assertContains(response, 'Browse Notes')
        self.assertContains(response, 'Upload')
        self.assertContains(response, 'My Study List')
        self.assertContains(response, 'Login')
        self.assertContains(response, 'Register')
        self.assertContains(response, 'htmx.org')
        self.assertContains(response, 'cdn.tailwindcss.com')

    def test_htmx_request_handling(self):
        """HtmxMiddleware detects HX-Request header correctly."""
        response = self.client.get('/', HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.htmx)
