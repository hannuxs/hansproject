from django.conf import settings


def site(request):
    """Data statis yang aman dipakai di semua template (tanpa akses sesi)."""
    return {
        "SITE_URL": settings.SITE_URL,
        "DEBUG": settings.DEBUG,
        "STORE_BASE_DOMAIN": settings.STORE_BASE_DOMAIN,
    }
