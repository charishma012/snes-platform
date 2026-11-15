"""
URL configuration for SNES (Smart Notes Exchange System).
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('notes.urls')),
]

# Serve uploaded media files from local MEDIA_ROOT when USE_S3_STORAGE is False,
# even in production (DEBUG=False) for zero-cost Render deployments.
if not getattr(settings, 'USE_S3_STORAGE', False):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
