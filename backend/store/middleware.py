from django.conf import settings
from django.http import HttpResponseNotFound

PROTECTED_PREFIXES = ("/admin/", "/api/admin/", "/api/auth/")


class LocalOnlyAdminMiddleware:
    """Hide management endpoints from the public internet.

    Requests that arrive through Cloudflare carry Cloudflare headers. When
    ADMIN_LOCAL_ONLY is on, those requests get a 404 for the Django admin, the
    management API and the login endpoint. Staff use the desktop app on the store
    computer / local network, where these headers are absent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.ADMIN_LOCAL_ONLY and request.path.startswith(PROTECTED_PREFIXES):
            if "HTTP_CF_CONNECTING_IP" in request.META or "HTTP_CF_RAY" in request.META:
                return HttpResponseNotFound()
        return self.get_response(request)
