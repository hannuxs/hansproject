"""URL publik untuk warga (tanpa login)."""
from django.urls import path

from . import views_public as views

app_name = "warga"

urlpatterns = [
    path("w/<slug:kode>/", views.wilayah, name="wilayah"),
    path("w/<slug:kode>/ajukan/<slug:jenis>/", views.ajukan, name="ajukan"),
    path("surat/lacak/", views.lacak_cari, name="lacak-cari"),
    path("surat/lacak/<str:token>/", views.lacak, name="lacak"),
    path("surat/lacak/<str:token>/cetak/", views.lacak_cetak, name="lacak-cetak"),
    path("surat/lacak/<str:token>/gambar/<str:kind>/", views.lacak_gambar, name="lacak-gambar"),
    path("surat/cek/<str:token>/", views.cek, name="cek"),
]
