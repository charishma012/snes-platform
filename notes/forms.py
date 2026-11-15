import logging
import os
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from pypdf import PdfReader

from .models import Note


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


class NoteUploadForm(forms.ModelForm):
    """
    Form for uploading new academic notes (PDF and PPTX only).
    Validates file format, size <= 25MB, and validates PDF page count via pypdf.
    """

    class Meta:
        model = Note
        fields = (
            "title",
            "subject",
            "topic",
            "category",
            "year",
            "description",
            "file",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update(
                    {
                        "class": (
                            "w-full px-3 py-2 text-sm text-slate-600 border border-slate-300 rounded-xl cursor-pointer "
                            "bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500 file:mr-4 file:py-2 file:px-4 "
                            "file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-sky-600 file:text-white "
                            "hover:file:bg-sky-700 transition shadow-sm"
                        ),
                        "accept": ".pdf,.pptx",
                    }
                )
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update(
                    {
                        "class": (
                            "w-full px-4 py-2.5 rounded-xl border border-slate-300 "
                            "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 "
                            "text-sm text-slate-800 bg-white transition shadow-sm"
                        ),
                    }
                )
            else:
                placeholder_text = f"Enter {field.label.lower() if field.label else name}"
                if name == "title":
                    placeholder_text = "e.g., CS101 Lecture 4: Graph Algorithms"
                elif name == "subject":
                    placeholder_text = "e.g., Computer Science"
                elif name == "topic":
                    placeholder_text = "e.g., Breadth-First & Depth-First Search"
                elif name == "description":
                    placeholder_text = "Optional overview, course module, or notes summary..."

                field.widget.attrs.update(
                    {
                        "class": (
                            "w-full px-4 py-2.5 rounded-xl border border-slate-300 "
                            "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 "
                            "text-sm text-slate-800 placeholder-slate-400 bg-white transition shadow-sm"
                        ),
                        "placeholder": placeholder_text,
                    }
                )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if not uploaded_file:
            raise forms.ValidationError("Please select a file to upload.")

        # Enforce 25 MB max limit
        max_size_mb = 25
        max_size_bytes = max_size_mb * 1024 * 1024
        if uploaded_file.size > max_size_bytes:
            actual_size_mb = uploaded_file.size / (1024 * 1024)
            raise forms.ValidationError(
                f"File size exceeds the {max_size_mb} MB limit (uploaded file is {actual_size_mb:.1f} MB)."
            )

        name = uploaded_file.name or ""
        ext = os.path.splitext(name)[1].lower()
        if ext not in [".pdf", ".pptx"]:
            raise forms.ValidationError(
                "Unsupported file format. Only PDF (.pdf) and PowerPoint (.pptx) files are supported."
            )

        if ext == ".pdf":
            try:
                uploaded_file.seek(0)
                logging.getLogger("pypdf").setLevel(logging.ERROR)
                reader = PdfReader(uploaded_file)
                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        raise forms.ValidationError(
                            "Encrypted or password-protected PDF files are not allowed."
                        )
                page_count = len(reader.pages)
                if page_count < 1:
                    raise forms.ValidationError(
                        "The uploaded PDF file contains no pages or is invalid."
                    )
                self.cleaned_file_type = "PDF"
                self.cleaned_page_count = page_count
            except forms.ValidationError:
                raise
            except Exception:
                raise forms.ValidationError(
                    "The uploaded PDF file is corrupt or could not be read. Please upload a valid PDF document."
                )
            finally:
                uploaded_file.seek(0)
        else:
            self.cleaned_file_type = "PPTX"
            self.cleaned_page_count = None

        return uploaded_file

    def save(self, commit=True):
        instance = super().save(commit=False)
        if hasattr(self, "cleaned_file_type"):
            instance.file_type = self.cleaned_file_type
            instance.page_count = self.cleaned_page_count
        if commit:
            instance.save()
        return instance


class NoteEditForm(forms.ModelForm):
    """
    Form for editing existing note metadata without requiring re-uploading the file.
    """

    class Meta:
        model = Note
        fields = (
            "title",
            "subject",
            "topic",
            "category",
            "year",
            "description",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update(
                    {
                        "class": (
                            "w-full px-4 py-2.5 rounded-xl border border-slate-300 "
                            "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 "
                            "text-sm text-slate-800 bg-white transition shadow-sm"
                        ),
                    }
                )
            else:
                placeholder_text = f"Enter {field.label.lower() if field.label else name}"
                if name == "title":
                    placeholder_text = "e.g., CS101 Lecture 4: Graph Algorithms"
                elif name == "subject":
                    placeholder_text = "e.g., Computer Science"
                elif name == "topic":
                    placeholder_text = "e.g., Breadth-First & Depth-First Search"
                elif name == "description":
                    placeholder_text = "Optional overview, course module, or notes summary..."

                field.widget.attrs.update(
                    {
                        "class": (
                            "w-full px-4 py-2.5 rounded-xl border border-slate-300 "
                            "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 "
                            "text-sm text-slate-800 placeholder-slate-400 bg-white transition shadow-sm"
                        ),
                        "placeholder": placeholder_text,
                    }
                )
