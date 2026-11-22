"""Halaman panel: beranda, keamanan akun, riwayat perubahan."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import TemplateView, View

from apps.accounts.models import LoginAttempt
from apps.content import audit
from apps.content.checks import placeholder_reminders
from apps.content.models import AuditLog, ContactClick, Package
from apps.members import chat, files
from apps.members.models import Member, Order, Refund
from apps.pos.models import Store
from apps.sim.models import Wilayah

from ..forms import PanelPasswordChangeForm
from ..mixins import PanelAccessMixin

TARGET_LABELS = {
    "instagram": "DM Instagram",
}


class DashboardView(PanelAccessMixin, TemplateView):
    template_name = "panel/dashboard.html"
    page_title = "Beranda Panel"
    nav_active = "dashboard"

    def click_stats(self):
        today = timezone.localdate()
        labels = dict(TARGET_LABELS)
        labels.update({p.code: f"Paket {p.name}" for p in Package.objects.all()})

        def totals(days: int) -> dict[str, int]:
            since = today - timedelta(days=days - 1)
            rows = ContactClick.objects.filter(date__gte=since).values("target").annotate(total=Sum("count"))
            return {r["target"]: r["total"] for r in rows}

        week, month = totals(7), totals(30)
        targets = sorted(set(week) | set(month), key=lambda t: -month.get(t, 0))
        return [
            {"label": labels.get(t, t), "week": week.get(t, 0), "month": month.get(t, 0)} for t in targets
        ], sum(week.values()), sum(month.values())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stats, week_total, month_total = self.click_stats()
        since = timezone.now() - timedelta(hours=24)
        ctx.update(
            reminders=placeholder_reminders(),
            click_rows=stats,
            click_week=week_total,
            click_month=month_total,
            recent_changes=AuditLog.objects.select_related("user")[:8],
            failed_logins_24h=LoginAttempt.objects.filter(success=False, created_at__gte=since).count(),
            last_logins=LoginAttempt.objects.filter(success=True)[:5],
            orders_to_check=Order.objects.filter(status=Order.STATUS_CHECKING).count(),
            orders_to_consult=Order.objects.filter(status=Order.STATUS_CONSULT).count(),
            orders_waiting_payment=Order.objects.filter(status=Order.STATUS_PAYMENT).count(),
            chats_need_reply=chat.needs_reply_count(),
            refunds_open=Refund.objects.filter(status__in=(Refund.STATUS_REQUESTED, Refund.STATUS_PROCESSING)).count(),
            member_count=Member.objects.count(),
            services=_service_stats(),
        )
        return ctx


def _service_stats() -> list[dict]:
    """Ringkasan per solusi untuk beranda panel (angka saja, tanpa data pribadi)."""
    today = timezone.localdate()
    soon = today + timedelta(days=7)
    open_orders = dict(
        Order.objects.filter(status__in=Order.OPEN_STATUSES).values_list("package_category").annotate(n=models.Count("pk"))
    )
    stores = Store.objects.not_deleted()
    wilayah = Wilayah.objects.not_deleted()
    return [
        {
            "label": "Aplikasi Kasir", "icon": "calculator", "url_name": "panel:toko-list",
            "active": stores.filter(is_active=True, subscription__active_until__gte=today).count(),
            "unit": "toko aktif",
            "expiring": stores.filter(subscription__active_until__gte=today, subscription__active_until__lte=soon).count(),
            "orders": open_orders.get(Package.CATEGORY_POS, 0),
        },
        {
            "label": "Sistem Informasi Manajemen (SIM)", "icon": "database", "url_name": "panel:wilayah-list",
            "active": wilayah.filter(active_until__gte=today).count(),
            "unit": "instansi aktif",
            "expiring": wilayah.filter(active_until__gte=today, active_until__lte=soon).count(),
            "orders": open_orders.get(Package.CATEGORY_SIM, 0),
        },
        {
            "label": "Website & Aplikasi", "icon": "code", "url_name": "panel:pesanan-list",
            "active": Order.objects.filter(package_category=Package.CATEGORY_SERVICE, status=Order.STATUS_PROCESS).count(),
            "unit": "proyek dikerjakan",
            "expiring": None,
            "orders": open_orders.get(Package.CATEGORY_SERVICE, 0),
        },
    ]


@method_decorator(sensitive_post_parameters("old_password", "new_password1", "new_password2"), name="dispatch")
class AccountView(PanelAccessMixin, TemplateView):
    template_name = "panel/account.html"
    page_title = "Keamanan Akun"
    nav_active = "akun"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", PanelPasswordChangeForm(self.request.user))
        return ctx

    def post(self, request, *args, **kwargs):
        form = PanelPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            audit.record(request, AuditLog.ACTION_SECURITY, user, target_type="akun", detail="Password diganti")
            messages.success(request, "Password berhasil diganti.")
            return redirect("panel:account")
        return self.render_to_response(self.get_context_data(form=form), status=400)


class AuditListView(PanelAccessMixin, TemplateView):
    template_name = "panel/audit.html"
    page_title = "Riwayat Perubahan"
    nav_active = "riwayat"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        paginator = Paginator(AuditLog.objects.select_related("user"), 30)
        ctx["page_obj"] = paginator.get_page(self.request.GET.get("halaman"))
        return ctx


class PaymentProofView(PanelAccessMixin, View):
    """Menampilkan bukti bayar (file pribadi) hanya untuk pengelola yang sudah login."""

    def get(self, request, pk: int):
        order = get_object_or_404(Order, pk=pk)
        if not order.payment_proof:
            raise Http404
        return files.serve_private(order.payment_proof)
