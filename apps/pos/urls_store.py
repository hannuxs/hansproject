"""URL untuk subdomain toko (dipilih otomatis oleh StoreHostMiddleware)."""
from django.urls import include, path, re_path

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
    re_path(r"^_tema/v(?P<version>[0-9]{1,3})/(?P<color>[0-9a-f]{6})\.css$", views.tema_css, name="tema"),
    # Gambar halaman toko (logo, sampul, barang unggulan) dari alamat toko sendiri (CSP img-src 'self').
    re_path(r"^media/(?P<path>uploads/toko/[A-Za-z0-9/_-]+\.(?:webp|png|jpg))$", web_views.media_file, name="media"),
]

urlpatterns = [path("", include((kasir_patterns, "kasir")))]

handler400 = "apps.web.views.error_400"
handler403 = "apps.web.views.error_403"
handler404 = "apps.web.views.error_404"
handler500 = "apps.web.views.error_500"
