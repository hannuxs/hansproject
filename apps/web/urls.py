from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("aplikasi-kasir/", views.solution_page, {"key": "kasir"}, name="kasir"),
    path("sistem-informasi-manajemen/", views.solution_page, {"key": "sim"}, name="sim"),
    path("website-aplikasi/", views.solution_page, {"key": "jasa"}, name="jasa"),
    path("syarat-ketentuan/", views.legal_page, {"slug": "syarat-ketentuan"}, name="terms"),
    path("kebijakan-privasi/", views.legal_page, {"slug": "kebijakan-privasi"}, name="privacy"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path(".well-known/security.txt", views.security_txt, name="security-txt"),
    path("favicon.ico", views.favicon),
    path("api/klik/", views.contact_click, name="contact-click"),
    path("sehat/", views.health, name="health"),
    path("cek/<str:token>/", views.cek_pesanan, name="cek-pesanan"),
]
