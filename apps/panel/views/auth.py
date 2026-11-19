"""Masuk, verifikasi dua langkah (2FA), dan keluar dari panel."""
from __future__ import annotations

import logging
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.messages import get_messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from apps.accounts import security
from apps.accounts.models import LoginAttempt, TwoFactorDevice
from apps.content import audit
from apps.content.models import AuditLog
from apps.core.privacy import ip_hash

from ..forms import LoginForm, OtpForm
from ..mixins import SESSION_2FA_OK, SESSION_LOGIN_AT, session_is_valid

log = logging.getLogger("hans.security")

PENDING_UID = "hp_pending_uid"
PENDING_AT = "hp_pending_at"
PENDING_NEXT = "hp_pending_next"
PENDING_TTL = 5 * 60  # detik untuk memasukkan kode 2FA setelah password benar

auth_decorators = [never_cache, csrf_protect, sensitive_post_parameters("password", "code")]


def _safe_next(request, url: str | None) -> str | None:
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        if url.startswith(f"/{settings.ADMIN_URL_PATH}/"):
            return url
    return None


def _lock_message(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    return f"Terlalu banyak percobaan gagal. Demi keamanan, coba lagi dalam {minutes} menit."


def _pending_user(request):
    uid, started = request.session.get(PENDING_UID), request.session.get(PENDING_AT, 0)
    if not uid or time.time() - started > PENDING_TTL:
        return None
    return get_user_model().objects.filter(pk=uid, is_active=True, is_staff=True).first()


def _complete_login(request, user):
    next_url = request.session.get(PENDING_NEXT)
    for key in (PENDING_UID, PENDING_AT, PENDING_NEXT):
        request.session.pop(key, None)
    login(request, user)  # membuat ID sesi baru (mencegah session fixation)
    request.session[SESSION_2FA_OK] = user.has_2fa or not settings.ADMIN_REQUIRE_2FA
    request.session[SESSION_LOGIN_AT] = time.time()
    return redirect(next_url or "panel:dashboard")


def _render(request, template, context, status=200):
    context = {**context, "messages": get_messages(request)}
    return render(request, template, context, status=status)


@method_decorator(auth_decorators, name="dispatch")
class LoginView(View):
    template_name = "panel/auth/login.html"

    def get(self, request):
        if session_is_valid(request):
            return redirect("panel:dashboard")
        return _render(request, self.template_name, {"form": LoginForm(), "next": request.GET.get("next", "")})

    def post(self, request):
        form = LoginForm(request.POST)
        ip = ip_hash(request)
        username = (request.POST.get("username") or "").strip()
        next_url = _safe_next(request, request.POST.get("next"))
        ctx = {"form": form, "next": next_url or ""}

        locked = security.lock_remaining_seconds(username, ip)
        if locked:
            log.warning("Login admin DIBLOKIR sementara (user=%s, ip_hash=%s)", username.lower() or "-", ip)
            form.add_error(None, _lock_message(locked))
            return _render(request, self.template_name, ctx, status=429)
        if not form.is_valid():
            return _render(request, self.template_name, ctx, status=400)

        user = authenticate(request, username=form.cleaned_data["username"], password=form.cleaned_data["password"])
        if user is None or not user.is_staff:
            security.record_attempt(username, ip, success=False)
            form.add_error(None, "Nama pengguna atau password salah.")
            return _render(request, self.template_name, ctx, status=400)

        security.record_attempt(username, ip, success=True)
        # 2FA tidak diwajibkan (hanya komputer pengembangan): cukup password, walau akun punya Authenticator.
        if not settings.ADMIN_REQUIRE_2FA:
            request.session[PENDING_NEXT] = next_url
            return _complete_login(request, user)

        request.session.cycle_key()
        request.session[PENDING_UID] = user.pk
        request.session[PENDING_AT] = time.time()
        request.session[PENDING_NEXT] = next_url
        return redirect("panel:otp-verify" if user.has_2fa else "panel:otp-setup")


@method_decorator(auth_decorators, name="dispatch")
class OtpVerifyView(View):
    template_name = "panel/auth/otp_verify.html"

    def get(self, request):
        user = _pending_user(request)
        if user is None or not user.has_2fa:
            return redirect("panel:login")
        return _render(request, self.template_name, {"form": OtpForm()})

    def post(self, request):
        user = _pending_user(request)
        if user is None or not user.has_2fa:
            messages.info(request, "Waktu memasukkan kode habis. Silakan masuk lagi.")
            return redirect("panel:login")
        ip = ip_hash(request)
        form = OtpForm(request.POST)
        locked = security.lock_remaining_seconds(user.username, ip)
        if locked:
            request.session.flush()
            messages.error(request, _lock_message(locked))
            return redirect("panel:login")
        if form.is_valid() and security.verify_code(user.totp_device, form.cleaned_data["code"]):
            security.record_attempt(user.username, ip, success=True, stage=LoginAttempt.STAGE_OTP)
            return _complete_login(request, user)
        security.record_attempt(user.username, ip, success=False, stage=LoginAttempt.STAGE_OTP)
        if form.is_valid():
            form.add_error("code", "Kode salah atau sudah kedaluwarsa. Coba kode yang baru.")
        return _render(request, self.template_name, {"form": form}, status=400)


@method_decorator(auth_decorators, name="dispatch")
class OtpSetupView(View):
    """Mengaktifkan 2FA pertama kali (wajib sebelum bisa memakai panel)."""

    template_name = "panel/auth/otp_setup.html"

    def _device(self, user) -> TwoFactorDevice:
        device, _ = TwoFactorDevice.objects.get_or_create(user=user, defaults={"secret": security.new_secret()})
        return device

    def _context(self, user, device, form):
        uri = security.provisioning_uri(user.username, device.secret)
        secret = " ".join(device.secret[i : i + 4] for i in range(0, len(device.secret), 4))
        return {"form": form, "qr_svg": security.qr_svg(uri), "secret": secret}

    def get(self, request):
        user = _pending_user(request)
        if user is None:
            return redirect("panel:login")
        if user.has_2fa:
            return redirect("panel:otp-verify")
        device = self._device(user)
        return _render(request, self.template_name, self._context(user, device, OtpForm()))

    def post(self, request):
        user = _pending_user(request)
        if user is None or user.has_2fa:
            return redirect("panel:login")
        device = self._device(user)
        form = OtpForm(request.POST)
        if form.is_valid() and security.verify_code(device, form.cleaned_data["code"]):
            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed_at"])
            user.refresh_from_db()
            response = _complete_login(request, user)
            audit.record(request, AuditLog.ACTION_SECURITY, user, target_type="akun", detail="2FA diaktifkan")
            messages.success(request, "Verifikasi dua langkah aktif. Akun Anda sekarang jauh lebih aman.")
            return response
        security.record_attempt(user.username, ip_hash(request), success=False, stage=LoginAttempt.STAGE_OTP)
        if form.is_valid():
            form.add_error("code", "Kode belum cocok. Pastikan jam di HP sudah benar, lalu coba kode yang baru.")
        return _render(request, self.template_name, self._context(user, device, form), status=400)


@method_decorator([never_cache, csrf_protect], name="dispatch")
class LogoutView(View):
    def post(self, request):
        if request.user.is_authenticated:
            log.info("Logout admin (user=%s)", request.user.get_username())
        logout(request)  # menghapus sesi dari database
        response = redirect("panel:login")
        response.delete_cookie(settings.SESSION_COOKIE_NAME, path=settings.SESSION_COOKIE_PATH)
        return response

    def get(self, request):
        return redirect("panel:dashboard")
