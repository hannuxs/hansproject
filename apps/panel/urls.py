from django.urls import path

from .registry import SECTIONS
from .views import auth, chat, pages

app_name = "panel"

urlpatterns = [
    path("", pages.DashboardView.as_view(), name="dashboard"),
    path("masuk/", auth.LoginView.as_view(), name="login"),
    path("verifikasi/", auth.OtpVerifyView.as_view(), name="otp-verify"),
    path("aktifkan-2fa/", auth.OtpSetupView.as_view(), name="otp-setup"),
    path("keluar/", auth.LogoutView.as_view(), name="logout"),
    path("akun/", pages.AccountView.as_view(), name="account"),
    path("riwayat/", pages.AuditListView.as_view(), name="audit"),
    path("pesanan/<int:pk>/bukti/", pages.PaymentProofView.as_view(), name="pesanan-bukti"),
    path("refund/<int:pk>/bukti/", chat.RefundProofView.as_view(), name="refund-bukti"),
    path("chat/", chat.ChatListView.as_view(), name="chat-list"),
    path("chat/<int:pk>/", chat.ChatDetailView.as_view(), name="chat"),
    path("chat/<int:pk>/baru/", chat.ChatPollView.as_view(), name="chat-poll"),
    path("chat/gambar/<int:msg>/", chat.ChatImageView.as_view(), name="chat-gambar"),
]

for section in SECTIONS:
    urlpatterns += section.urls()
