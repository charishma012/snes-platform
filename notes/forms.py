from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class UserRegisterForm(UserCreationForm):
    """Registration form based on UserCreationForm with Tailwind classes."""

    email = forms.EmailField(
        required=True,
        help_text="Required for account recovery and verified academic updates.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": (
                        "w-full px-4 py-2.5 rounded-xl border border-slate-300 "
                        "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 "
                        "text-sm text-slate-800 placeholder-slate-400 bg-white transition shadow-sm"
                    ),
                    "placeholder": f"Enter your {field.label.lower() if field.label else name}",
                }
            )


class UserLoginForm(AuthenticationForm):
    """Login form based on AuthenticationForm with Tailwind classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": (
                        "w-full px-4 py-2.5 rounded-xl border border-slate-300 "
                        "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 "
                        "text-sm text-slate-800 placeholder-slate-400 bg-white transition shadow-sm"
                    ),
                    "placeholder": f"Enter your {field.label.lower() if field.label else name}",
                }
            )
