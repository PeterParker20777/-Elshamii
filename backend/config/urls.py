from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve


def home(request):
    return HttpResponse("Elshamii backend is running.", content_type="text/plain")


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),
    path("api/", include("store.api_urls")),
    # Product images. Small single-store catalogue, so Django serves them directly.
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
