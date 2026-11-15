from django.shortcuts import render
from django.http import HttpRequest, HttpResponse


def home(request: HttpRequest) -> HttpResponse:
    """Renders the SNES landing page."""
    return render(request, 'notes/home.html')
