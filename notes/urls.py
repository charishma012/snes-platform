from django.urls import path
from . import views

app_name = "notes"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register_view, name="register"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    # Phase 3 URLs
    path("upload/", views.upload_note, name="upload_note"),
    path("upload/", views.upload_note, name="upload"),
    path("dashboard/", views.my_dashboard, name="my_dashboard"),
    path("dashboard/", views.my_dashboard, name="dashboard"),
    path("note/<int:pk>/", views.note_detail, name="note_detail"),
    path("note/<int:pk>/edit/", views.edit_note, name="edit_note"),
    path("note/<int:pk>/delete/", views.delete_note, name="delete_note"),
    path("note/<int:pk>/download/", views.download_note, name="download_note"),
    path("note/<int:pk>/report/", views.report_note, name="report_note"),
    # Phase 4 HTMX Interactivity (Voting & Bookmarks)
    path("note/<int:pk>/upvote/", views.toggle_upvote, name="toggle_upvote"),
    path("note/<int:pk>/upvote/", views.toggle_upvote, name="upvote_note"),
    path("note/<int:pk>/downvote/", views.toggle_downvote, name="toggle_downvote"),
    path("note/<int:pk>/downvote/", views.toggle_downvote, name="downvote_note"),
    path("note/<int:pk>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path("note/<int:pk>/bookmark/", views.toggle_bookmark, name="bookmark_note"),
]
