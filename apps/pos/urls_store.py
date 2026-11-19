"""URL untuk subdomain toko (dipilih otomatis oleh StoreHostMiddleware)."""
from django.urls import include, path

from apps.web import views as web_views

from . import views_kasir as views

kasir_patterns = [
    path("", views.toko_home, name="home"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("favicon.ico", web_views.favicon, name="favicon"),
    path("kasir/", views.pos, name="pos"),
    path("kasir/masuk/", views.masuk, name="masuk"),
    path("kasir/keluar/", views.keluar, name="keluar"),
    path("kasir/bayar/", views.bayar, name="bayar"),
    path("kasir/riwayat/", views.riwayat, name="riwayat"),
    path("kasir/struk/<int:pk>/", views.struk, name="struk"),
]

urlpatterns = [path("", include((kasir_patterns, "kasir")))]

handler400 = "apps.web.views.error_400"
handler403 = "apps.web.views.error_403"
handler404 = "apps.web.views.error_404"
handler500 = "apps.web.views.error_500"
