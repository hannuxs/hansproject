from django.urls import path

from . import views

app_name = "akun"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("masuk/", views.masuk, name="masuk"),
    path("keluar/", views.keluar, name="keluar"),
    path("google/", views.google_start, name="google"),
    path("google/callback/", views.google_callback, name="google-callback"),
    path("persetujuan/", views.persetujuan, name="persetujuan"),
    path("profil/", views.profil, name="profil"),
    path("data-diri/", views.lengkapi, name="lengkapi"),
    path("pesan/", views.pesan_pilih, name="pesan-pilih"),
    path("pesan/<slug:code>/", views.pesan, name="pesan"),
    path("pesanan/", views.pesanan_list, name="pesanan-list"),
    path("pesanan/<str:code>/", views.pesanan, name="pesanan"),
    path("pesanan/<str:code>/bukti/", views.bukti, name="bukti"),
    path("pesanan/<str:code>/refund/bukti/", views.refund_bukti, name="refund-bukti"),
    path("chat/", views.chat_list, name="chat-list"),
    path("chat/baru/", views.chat_baru, name="chat-baru"),
    path("chat/<int:pk>/", views.chat_detail, name="chat"),
    path("chat/<int:pk>/baru/", views.chat_poll, name="chat-poll"),
    path("chat/<int:pk>/gambar/<int:msg>/", views.chat_gambar, name="chat-gambar"),
    # Alamat lama tombol "Tanya Kami".
    path("tanya/", views.tanya, name="tanya"),
]
