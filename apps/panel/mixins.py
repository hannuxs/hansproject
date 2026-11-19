"""Akses panel: wajib login, wajib 2FA (bila diaktifkan), dan sesi berbatas waktu."""
from __future__ import annotations

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.messages import get_messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.decorators.cache import never_cache

SESSION_2FA_OK = "hp_2fa_ok"
SESSION_LOGIN_AT = "hp_login_at"


def session_is_valid(request) -> bool:
    user = request.user
    if not (user.is_authenticated and user.is_active and user.is_staff):
        return False
    if settings.ADMIN_REQUIRE_2FA and not request.session.get(SESSION_2FA_OK):
        return False
    login_at = request.session.get(SESSION_LOGIN_AT, 0)
    return time.time() - login_at <= settings.ADMIN_SESSION_MAX_HOURS * 3600


@method_decorator(never_cache, name="dispatch")
class PanelAccessMixin:
    """Dipakai semua halaman panel (kecuali halaman masuk)."""

    page_title = ""
    nav_active = ""

    def dispatch(self, request, *args, **kwargs):
        if not session_is_valid(request):
            expired = request.user.is_authenticated
            logout(request)
            if expired:
                messages.info(request, "Sesi Anda sudah berakhir. Silakan masuk lagi.")
            login_url = reverse("panel:login")
            if request.method == "GET":
                login_url += "?" + urlencode({"next": request.get_full_path()})
            return redirect(login_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from .registry import nav_groups

        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("page_title", self.page_title)
        ctx["nav_groups"] = nav_groups()
        ctx["nav_active"] = self.nav_active
        ctx["messages"] = get_messages(self.request)
        ctx["panel_user"] = self.request.user
        return ctx
