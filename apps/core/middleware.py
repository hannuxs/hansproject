"""Header keamanan tambahan yang belum disediakan Django 5.2."""
from __future__ import annotations

from django.conf import settings


def build_csp(policy: dict[str, list[str]]) -> str:
    parts = []
    for directive, sources in policy.items():
        parts.append(f"{directive} {' '.join(sources)}".strip())
    return "; ".join(parts)


class SecurityHeadersMiddleware:
    """Memasang Content-Security-Policy, Permissions-Policy, dan header lain.

    Panel pengelola dan halaman akun pelanggan juga diberi ``X-Robots-Tag: noindex`` dan ``no-store``
    supaya tidak diindeks mesin pencari dan tidak tersimpan di cache.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = build_csp(settings.CONTENT_SECURITY_POLICY)
        self.permissions = settings.PERMISSIONS_POLICY
        # Panel pengelola & halaman akun pelanggan berisi data pribadi.
        self.private_prefixes = (f"/{settings.ADMIN_URL_PATH}/", "/akun/")

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.csp)
        response.setdefault("Permissions-Policy", self.permissions)
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        if request.path.startswith(self.private_prefixes):
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            response["Cache-Control"] = "no-store, max-age=0"
        return response
