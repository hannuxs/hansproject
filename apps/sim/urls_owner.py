"""URL dashboard pengurus wilayah: hansproject.app/akun/sim/..."""
from django.urls import path

from . import views_owner as views

app_name = "sim"

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("<slug:kode>/", views.ringkasan, name="ringkasan"),
    path("<slug:kode>/warga/", views.warga, name="warga"),
    path("<slug:kode>/warga/unduh/", views.warga_unduh, name="warga-unduh"),
    path("<slug:kode>/warga/kk/baru/", views.kk_form, name="kk-baru"),
    path("<slug:kode>/warga/kk/<int:pk>/", views.kk_detail, name="kk"),
    path("<slug:kode>/warga/kk/<int:pk>/ubah/", views.kk_form, name="kk-ubah"),
    path("<slug:kode>/warga/kk/<int:pk>/hapus/", views.kk_hapus, name="kk-hapus"),
    path("<slug:kode>/warga/kk/<int:kk>/anggota/baru/", views.penduduk_form, name="anggota-baru"),
    path("<slug:kode>/warga/anggota/<int:pk>/", views.penduduk_form, name="anggota-ubah"),
    path("<slug:kode>/warga/anggota/<int:pk>/hapus/", views.penduduk_hapus, name="anggota-hapus"),
    path("<slug:kode>/scan/", views.scan, name="scan"),
    path("<slug:kode>/scan/<int:pk>/", views.scan_detail, name="scan-detail"),
    path("<slug:kode>/scan/<int:pk>/gambar/", views.scan_gambar, name="scan-gambar"),
    path("<slug:kode>/surat/", views.surat, name="surat"),
    path("<slug:kode>/surat/buat/", views.surat_pilih, name="surat-pilih"),
    path("<slug:kode>/surat/buat/<slug:jenis>/", views.surat_baru, name="surat-baru"),
    path("<slug:kode>/surat/<int:pk>/", views.surat_detail, name="surat-detail"),
    path("<slug:kode>/surat/<int:pk>/cetak/", views.surat_cetak, name="surat-cetak"),
    path("<slug:kode>/format/", views.format_list, name="format"),
    path("<slug:kode>/format/baru/", views.format_form, name="format-baru"),
    path("<slug:kode>/format/<int:pk>/", views.format_form, name="format-ubah"),
    path("<slug:kode>/format/<int:pk>/contoh/", views.format_contoh, name="format-contoh"),
    path("<slug:kode>/format/<int:pk>/hapus/", views.format_hapus, name="format-hapus"),
    path("<slug:kode>/format/<int:pk>/bawaan/", views.format_reset, name="format-reset"),
    path("<slug:kode>/pengumuman/", views.pengumuman, name="pengumuman"),
    path("<slug:kode>/pengumuman/<int:pk>/", views.pengumuman, name="pengumuman-ubah"),
    path("<slug:kode>/pengumuman/<int:pk>/hapus/", views.pengumuman_hapus, name="pengumuman-hapus"),
    path("<slug:kode>/jaringan/", views.jaringan, name="jaringan"),
    path("<slug:kode>/jaringan/surat/<int:pk>/", views.ketahui, name="ketahui"),
    path("<slug:kode>/pengaturan/", views.pengaturan, name="pengaturan"),
    path("<slug:kode>/pengaturan/gambar/<str:kind>/", views.gambar, name="gambar"),
    path("<slug:kode>/perpanjang/", views.perpanjang, name="perpanjang"),
]
