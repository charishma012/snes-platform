from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import UserLoginForm, UserRegisterForm


def home(request: HttpRequest) -> HttpResponse:
    """Renders the SNES landing page."""
    return render(request, "notes/home.html")


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
