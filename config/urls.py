from django.conf import settings
from django.urls import include, path, re_path

from apps.web import views as web_views

urlpatterns = [
    path("", include("apps.web.urls")),
    path("akun/toko/", include("apps.pos.urls_owner")),
    path("akun/", include("apps.members.urls")),
    # Alamat panel diatur dari .env (ADMIN_URL_PATH), bukan /admin.
    path(f"{settings.ADMIN_URL_PATH}/", include("apps.panel.urls")),
    re_path(r"^media/(?P<path>uploads/[A-Za-z0-9/_-]+\.(?:webp|png|jpg))$", web_views.media_file, name="media"),
]

handler400 = "apps.web.views.error_400"
handler403 = "apps.web.views.error_403"
handler404 = "apps.web.views.error_404"
handler500 = "apps.web.views.error_500"
