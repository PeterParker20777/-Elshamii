from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


class ClientScopedThrottle(ScopedRateThrottle):
    """Scoped rate limit keyed by the real client IP.

    Behind Cloudflare Tunnel every request arrives from 127.0.0.1, so we read
    CF-Connecting-IP, but only when TRUST_CLOUDFLARE_HEADERS is enabled (i.e. the
    site is reachable only through the tunnel and the header cannot be forged).
    """

    def get_ident(self, request):
        if settings.TRUST_CLOUDFLARE_HEADERS:
            ip = request.META.get("HTTP_CF_CONNECTING_IP", "").strip()
            if ip:
                return ip
        return super().get_ident(request)
