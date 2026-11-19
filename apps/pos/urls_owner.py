"""URL dashboard pemilik toko: hansproject.app/akun/toko/..."""
from django.urls import path

from . import views_owner as views

app_name = "toko"

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("tambah/", views.tambah, name="tambah"),
    path("<slug:sub>/", views.ringkasan, name="ringkasan"),
    path("<slug:sub>/barang/", views.barang, name="barang"),
    path("<slug:sub>/barang/baru/", views.barang_form, name="barang-baru"),
    path("<slug:sub>/barang/<int:pk>/", views.barang_form, name="barang-ubah"),
    path("<slug:sub>/barang/<int:pk>/hapus/", views.barang_hapus, name="barang-hapus"),
    path("<slug:sub>/kategori/", views.kategori, name="kategori"),
    path("<slug:sub>/kategori/<int:pk>/", views.kategori, name="kategori-ubah"),
    path("<slug:sub>/kategori/<int:pk>/hapus/", views.kategori_hapus, name="kategori-hapus"),
    path("<slug:sub>/outlet/", views.outlet, name="outlet"),
    path("<slug:sub>/outlet/baru/", views.outlet_form, name="outlet-baru"),
    path("<slug:sub>/outlet/<int:pk>/", views.outlet_form, name="outlet-ubah"),
    path("<slug:sub>/outlet/<int:pk>/hapus/", views.outlet_hapus, name="outlet-hapus"),
    path("<slug:sub>/beli-toko/", views.beli_toko, name="beli-toko"),
    path("<slug:sub>/transaksi/", views.transaksi, name="transaksi"),
    path("<slug:sub>/transaksi/<int:pk>/", views.transaksi_detail, name="transaksi-detail"),
    path("<slug:sub>/transaksi/<int:pk>/struk/", views.transaksi_struk, name="transaksi-struk"),
    path("<slug:sub>/laporan/", views.laporan, name="laporan"),
    path("<slug:sub>/laporan/unduh/", views.laporan_unduh, name="laporan-unduh"),
    path("<slug:sub>/pengaturan/", views.pengaturan, name="pengaturan"),
    path("<slug:sub>/perpanjang/", views.perpanjang, name="perpanjang"),
]
