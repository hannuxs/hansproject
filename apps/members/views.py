"""Halaman akun pelanggan: masuk dengan Google, dashboard, pesanan & refund, chat, data diri.

Semua halaman di /akun/ bersifat pribadi: tidak di-cache (no-store) dan
tidak diindeks mesin pencari (lihat SecurityHeadersMiddleware).
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core import signing
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.content import services
from apps.content.models import Announcement, Package
from apps.core import ratelimit
from apps.core.privacy import ip_hash
from apps.pos import services as pos_services
from apps.pos.forms import NewStoreOrderForm
from apps.sim.forms import SimOrderForm

from . import auth, chat, files, google, qr
from .forms import ChatMessageForm, ChatStartForm, PaymentProofForm, ProfileForm, RefundRequestForm
from .models import TOPIC_KEYS, ChatMessage, Conversation, Member, Order, Refund
from .navigation import akun_tabs

log = logging.getLogger("hans.security")

STATE_COOKIE = "hp_oauth"
STATE_SALT = "hans.members.google-state"
STATE_MAX_AGE = 600
STATE_PATH = "/akun/google/"
MAX_OPEN_ORDERS = 5

LOGIN_ERRORS = {
    "batal": "Masuk dengan Google dibatalkan. Silakan coba lagi bila ingin melanjutkan.",
    "kedaluwarsa": "Proses masuk terlalu lama atau tidak valid. Silakan coba lagi.",
    "gagal": "Masuk dengan Google sedang gagal. Silakan coba lagi beberapa saat lagi.",
    "nonaktif": "Akun Anda sedang dinonaktifkan. Hubungi kami lewat DM Instagram.",
    "belum-siap": "Fitur masuk dengan Google sedang disiapkan. Silakan coba lagi nanti.",
    "terlalu-sering": "Terlalu banyak percobaan masuk. Tunggu beberapa menit, lalu coba lagi.",
}
NOTICES = {
    "profil": "Data diri Anda sudah tersimpan.",
    "dibuat": "Pesanan dibuat. Ikuti langkah di bawah untuk melanjutkan.",
    "bukti": "Bukti bayar terkirim. Kami akan mengeceknya, lalu status pesanan diperbarui di sini.",
    "batal": "Pesanan dibatalkan.",
    "batal-refund": "Pesanan dibatalkan. Karena sudah dibayar, Anda bisa mengajukan refund di bawah.",
    "refund": "Pengajuan refund terkirim. Perkembangannya tampil di halaman ini.",
}


def _render(request, template: str, context: dict | None = None, status: int = 200, tab: str = ""):
    snap = services.get_snapshot()
    member = getattr(request, "_member", None)
    ctx = {
        "snap": snap,
        "site": snap.settings,
        "member": member,
        "notice": NOTICES.get(request.GET.get("ok", "")),
        "akun_tabs": akun_tabs(tab, member) if member else [],
    }
    ctx.update(context or {})
    return render(request, template, ctx, status=status)


def _with_query(url: str, **params) -> str:
    return f"{url}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Masuk / keluar
# ---------------------------------------------------------------------------
@require_safe
def masuk(request):
    next_url = auth.safe_next(request, request.GET.get("next"))
    if auth.get_member(request):
        return auth.finish_response(request, redirect(next_url))
    response = _render(
        request,
        "akun/masuk.html",
        {
            "configured": google.is_configured(),
            "error": LOGIN_ERRORS.get(request.GET.get("gagal", "")),
            "start_url": _with_query(reverse("akun:google"), next=next_url),
            "page_title": "Daftar / Masuk",
        },
    )
    return auth.finish_response(request, response)


def _login_failed(reason: str):
    response = redirect(_with_query(reverse("akun:masuk"), gagal=reason))
    response.delete_cookie(STATE_COOKIE, path=STATE_PATH, samesite="Lax")
    return response


@require_safe
def google_start(request):
    if not google.is_configured():
        return _login_failed("belum-siap")
    # Login harus dimulai di alamat yang sama dengan alamat kembali dari Google,
    # supaya cookie pengaman terbaca saat kembali (mis. localhost vs 127.0.0.1).
    expected_host = urlsplit(google.redirect_uri()).netloc
    if request.get_host() != expected_host:
        scheme = urlsplit(google.redirect_uri()).scheme
        return redirect(f"{scheme}://{expected_host}{request.get_full_path()}")
    if not ratelimit.allow(f"google:{ip_hash(request)}", limit=20, window=600):
        return _login_failed("terlalu-sering")

    url, data = google.start()
    data["next"] = auth.safe_next(request, request.GET.get("next"))
    response = redirect(url)
    response.set_cookie(
        STATE_COOKIE,
        signing.dumps(data, salt=STATE_SALT, compress=True),
        max_age=STATE_MAX_AGE,
        path=STATE_PATH,
        secure=settings.MEMBER_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",  # Lax: cookie tetap terkirim saat Google mengembalikan pengunjung
    )
    return response


@require_safe
def google_callback(request):
    if request.GET.get("error"):
        return _login_failed("batal")
    raw = request.COOKIES.get(STATE_COOKIE)
    if not raw:
        return _login_failed("kedaluwarsa")
    try:
        data = signing.loads(raw, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature:
        return _login_failed("kedaluwarsa")
    if not google.state_matches(data.get("state", ""), request.GET.get("state", "")):
        log.warning("Login Google: state tidak cocok (kemungkinan login CSRF). ip=%s", ip_hash(request))
        return _login_failed("kedaluwarsa")
    code = request.GET.get("code", "")
    if not code or len(code) > 2048:
        return _login_failed("gagal")
    if not ratelimit.allow(f"google-cb:{ip_hash(request)}", limit=20, window=600):
        return _login_failed("terlalu-sering")

    try:
        identity = google.validate_claims(google.exchange_code(code, data["verifier"]), data["nonce"])
    except google.GoogleLoginError as exc:
        log.warning("Login Google gagal: %s ip=%s", exc, ip_hash(request))
        return _login_failed("gagal")

    member = _member_from_identity(identity)
    if not member.is_active:
        log.warning("Login Google ditolak: akun pelanggan #%s nonaktif.", member.pk)
        return _login_failed("nonaktif")

    next_url = auth.safe_next(request, data.get("next"))
    if auth.needs_terms(member):
        target = _with_query(reverse("akun:persetujuan"), next=next_url)
    elif not member.profile_complete:
        target = _with_query(reverse("akun:lengkapi"), next=next_url)
    else:
        target = next_url
    response = redirect(target)
    response.delete_cookie(STATE_COOKIE, path=STATE_PATH, samesite="Lax")
    auth.login(request, response, member)
    log.info("Pelanggan #%s masuk dengan Google.", member.pk)
    return response


def _member_from_identity(identity: google.GoogleIdentity) -> Member:
    try:
        member, created = Member.objects.get_or_create(
            google_sub=identity.sub, defaults={"email": identity.email, "name": identity.name}
        )
    except IntegrityError:  # dua login bersamaan untuk akun yang sama
        member, created = Member.objects.get(google_sub=identity.sub), False
    if created:
        log.info("Pelanggan baru terdaftar: #%s", member.pk)
        return member
    changed = []
    if member.email != identity.email:
        member.email = identity.email
        changed.append("email")
    if not member.name and identity.name:
        member.name = identity.name
        changed.append("name")
    if changed:
        member.save(update_fields=changed)
    return member


@require_POST
@auth.member_required(complete_profile=False, require_terms=False)
def keluar(request):
    response = redirect("/")
    auth.logout(request, response, everywhere=request.POST.get("semua") == "1")
    return response


# ---------------------------------------------------------------------------
# Persetujuan Syarat & Ketentuan / Kebijakan Privasi (popup setelah login)
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required(complete_profile=False, require_terms=False)
def persetujuan(request):
    member = request.member
    version = auth.legal_version()
    next_url = auth.safe_next(request, request.GET.get("next"))
    if not member.needs_terms(version):
        return redirect(next_url)
    error = ""
    if request.method == "POST":
        if request.POST.get("setuju") == "1":
            member.terms_version = version
            member.terms_accepted_at = timezone.now()
            member.save(update_fields=["terms_version", "terms_accepted_at"])
            log.info("Pelanggan #%s menyetujui S&K versi %s.", member.pk, version)
            return redirect(next_url)
        error = "Centang kotak persetujuan dulu untuk melanjutkan."
    return _render(
        request,
        "akun/persetujuan.html",
        {
            "error": error,
            "updated": member.terms_version is not None,
            "version": version,
            "page_title": "Persetujuan",
        },
        status=400 if error else 200,
    )


# ---------------------------------------------------------------------------
# Dashboard (halaman pertama setelah masuk)
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def dashboard(request):
    """Halaman pertama setelah masuk: ringkasan SEMUA layanan (kasir, SIM, jasa) + yang perlu perhatian."""
    member = request.member
    services_ = _member_services(member)
    open_orders = list(member.orders.filter(status__in=Order.OPEN_STATUSES)[:5])
    refunds = list(Refund.objects.filter(order__member=member).exclude(status=Refund.STATUS_DONE).select_related("order")[:5])
    return _render(
        request,
        "akun/dashboard.html",
        {
            "announcements": list(Announcement.visible()),
            "svc": services_,
            "open_orders": open_orders,
            "open_refunds": refunds,
            "unread_chats": chat.unread_for_member(member),
            "page_title": "Dashboard",
        },
        tab="dashboard",
    )


class _Services:
    """Ringkasan layanan milik satu pelanggan (dipakai Dashboard & menu Layanan)."""

    def __init__(self, member):
        self.stores = list(member.stores.not_deleted().select_related("subscription__package"))
        self.kasir = pos_services.overview(self.stores) if self.stores else None
        self.wilayah = list(member.wilayah_set.not_deleted().select_related("parent").annotate(
            menunggu=Count("surat_set", filter=Q(surat_set__status="diajukan"), distinct=True),
        ))
        self.surat_menunggu = sum(w.menunggu for w in self.wilayah)
        self.jasa_orders = list(member.orders.filter(package_category=Package.CATEGORY_SERVICE).exclude(
            status__in=(Order.STATUS_CANCELLED, Order.STATUS_DONE)
        ))
        self.pending = list(member.orders.filter(order_type=Order.TYPE_NEW, status__in=Order.OPEN_STATUSES).exclude(
            package_category=Package.CATEGORY_SERVICE
        ))
        self.sim_alerts = []
        for w in self.wilayah:
            state = w.state()
            if state in ("tenggang", "terkunci", "ditangguhkan"):
                self.sim_alerts.append((w, w.state_label, w.state_tone, {
                    "tenggang": f"Masa aktif habis {w.active_until:%d/%m/%Y}. Pengajuan surat online tetap dibuka sampai {w.grace_until:%d/%m/%Y}.",
                    "terkunci": f"Langganan terkunci. Data dihapus permanen setelah {w.delete_on:%d/%m/%Y} bila tidak diperpanjang.",
                    "ditangguhkan": "Langganan ditangguhkan admin. Lihat catatan di halaman instansi.",
                }[state]))
            elif state == "aktif" and w.days_left <= 7:
                self.sim_alerts.append((w, "Segera habis", "wait", f"Masa aktif tinggal {w.days_left} hari."))

    @property
    def count(self) -> int:
        return bool(self.stores) + bool(self.wilayah) + bool(self.jasa_orders)


def _member_services(member) -> _Services:
    return _Services(member)


@require_safe
@auth.member_required
def layanan(request):
    """Menu "Layanan": semua solusi milik pelanggan di satu tempat (kasir, SIM, website & aplikasi)."""
    member = request.member
    return _render(
        request,
        "akun/layanan.html",
        {"svc": _member_services(member), "page_title": "Layanan saya"},
        tab="layanan",
    )


# ---------------------------------------------------------------------------
# Akun: data diri
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required(complete_profile=False)
def lengkapi(request):
    member = request.member
    was_complete = member.profile_complete
    form = ProfileForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        default = _with_query(reverse("akun:profil"), ok="profil")
        return redirect(auth.safe_next(request, request.GET.get("next"), default=default))
    return _render(
        request,
        "akun/lengkapi.html",
        {
            "form": form,
            "first_time": not was_complete,
            "page_title": "Ubah data diri" if was_complete else "Lengkapi data diri",
        },
        status=400 if form.errors else 200,
        tab="akun",
    )


@require_safe
@auth.member_required
def profil(request):
    member = request.member
    return _render(
        request,
        "akun/profil.html",
        {
            "store_count": member.stores.not_deleted().count(),
            "wilayah_count": member.wilayah_set.not_deleted().count(),
            "order_count": member.orders.count(),
            "chat_count": member.chats.count(),
            "page_title": "Akun saya",
        },
        tab="akun",
    )


# ---------------------------------------------------------------------------
# Pesanan & refund
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def pesanan_list(request):
    member = request.member
    orders = list(member.orders.select_related("store", "refund"))
    return _render(
        request,
        "akun/pesanan_list.html",
        {
            "open_orders": [o for o in orders if o.is_open],
            "past_orders": [o for o in orders if not o.is_open],
            "refunds": [o.refund for o in orders if o.refund_or_none],
            "page_title": "Pesanan",
        },
        tab="pesanan",
    )


@require_safe
@auth.member_required
def pesan_pilih(request):
    """Pesan layanan dari dalam akun: 1) pilih solusi, 2) pilih paketnya (``?layanan=kasir|sim|jasa``)."""
    snap = services.get_snapshot()
    choices = {
        "kasir": ("Aplikasi Kasir", "calculator", snap.pos_packages),
        "sim": ("Sistem Informasi Manajemen (SIM)", "database", snap.sim_packages),
        "jasa": ("Website & Aplikasi", "code", snap.service_packages),
    }
    key = request.GET.get("layanan", "")
    chosen = choices.get(key)
    return _render(
        request,
        "akun/pesan_pilih.html",
        {
            "choice": key if chosen else "",
            "choice_label": chosen[0] if chosen else "",
            "packages": chosen[2] if chosen else [],
            "snap": snap,
            "has_store": request.member.stores.not_deleted().exists() if key == "kasir" else False,
            "has_wilayah": request.member.wilayah_set.not_deleted().exists() if key == "sim" else False,
            "page_title": f"Pesan {chosen[0]}" if chosen else "Pesan layanan",
        },
        tab="pesanan",
    )


@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required
def pesan(request, code: str):
    package = get_object_or_404(Package.objects.prefetch_related("notes"), code=code, is_active=True)
    if not package.is_priced:  # harga belum ditentukan pemilik: belum bisa dipesan
        return redirect(_with_query(reverse("akun:pesan-pilih"), layanan=package.category))
    member = request.member
    existing = member.orders.filter(
        package=package, order_type=Order.TYPE_NEW, status__in=Order.OPEN_STATUSES
    ).first()
    # Paket kasir: pelanggan memilih alamat toko (<nama>.hansproject.app).
    store_form = NewStoreOrderForm(request.POST or None) if package.is_pos else None
    # Paket SIM: pelanggan mengisi data wilayahnya (tingkat, nomor RT/RW, kelurahan, ...).
    sim_form = SimOrderForm(request.POST or None) if package.is_sim else None
    extra_form = store_form or sim_form
    error = ""
    if request.method == "POST":
        if existing:
            return redirect("akun:pesanan", code=existing.code)
        if member.orders.filter(status__in=Order.OPEN_STATUSES).count() >= MAX_OPEN_ORDERS:
            error = "Anda masih punya beberapa pesanan yang belum selesai. Selesaikan atau batalkan dulu salah satunya."
        elif extra_form is None or extra_form.is_valid():
            order = Order.objects.create(
                member=member,
                package=package,
                package_name=package.name,
                package_category=package.category,
                price_text=package.price_text,
                amount=package.price,
                subdomain=store_form.cleaned_data["subdomain"] if store_form else "",
                details=sim_form.details() if sim_form else {},
                status=Order.STATUS_PAYMENT if (package.is_pos or package.is_sim) else Order.STATUS_CONSULT,
            )
            log.info("Pesanan baru %s (paket %s) oleh pelanggan #%s.", order.code, package.code, member.pk)
            if order.needs_consultation:
                chat.order_chat(order)  # ruang obrolan konsultasi langsung tersedia (akun & panel)
            return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="dibuat"))
    stores = list(member.stores.not_deleted()) if package.is_pos else []
    return _render(
        request,
        "akun/pesan.html",
        {
            "package": package,
            "existing": existing,
            "error": error,
            "store_form": store_form,
            "sim_form": sim_form,
            "stores": stores,
            "wilayah_list": list(member.wilayah_set.not_deleted()) if package.is_sim else [],
            "page_title": f"Pesan {package.product_short} · Paket {package.name}",
        },
        status=400 if (error or (extra_form is not None and extra_form.errors)) else 200,
        tab="pesanan",
    )


def _own_order(request, code: str) -> Order:
    return get_object_or_404(Order.objects.select_related("package", "store", "wilayah"), code=code, member=request.member)


@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required
def pesanan(request, code: str):
    order = _own_order(request, code)
    form = PaymentProofForm()
    refund_form = RefundRequestForm(initial={"account_holder": request.member.name})
    if request.method == "POST":
        action = request.POST.get("aksi")
        if action == "batal" and order.can_cancel:
            order.status = Order.STATUS_CANCELLED
            order.save(update_fields=["status", "updated_at"])
            log.info("Pesanan %s dibatalkan oleh pelanggan.", order.code)
            notice = "batal-refund" if order.is_paid else "batal"
            return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok=notice) + ("#refund" if order.is_paid else ""))
        if action == "bukti" and order.can_send_proof:
            form = PaymentProofForm(request.POST, request.FILES)
            if form.is_valid():
                files.replace_proof(order, form.cleaned_data["proof"])
                log.info("Bukti bayar dikirim untuk pesanan %s.", order.code)
                return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="bukti"))
        elif action == "chat" and order.needs_consultation:
            return redirect("akun:chat", pk=chat.order_chat(order).pk)
        elif action == "refund" and order.can_request_refund:
            refund_form = RefundRequestForm(request.POST)
            if refund_form.is_valid():
                refund = refund_form.save(commit=False)
                refund.order = order
                refund.amount = order.amount
                refund.save()
                log.info("Refund diajukan untuk pesanan %s.", order.code)
                return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="refund") + "#refund")
        else:
            return HttpResponseBadRequest("Aksi tidak tersedia untuk pesanan ini.")
    snap = services.get_snapshot()
    show_payment = order.can_send_proof and snap.settings.show_payment_info
    return _render(
        request,
        "akun/pesanan.html",
        {
            "order": order,
            "form": form,
            "refund": order.refund_or_none,
            "consultation": order.consultation_chat if order.needs_consultation else None,
            "qr_svg": qr.order_qr_svg(order) if order.has_verified_proof else "",
            "verify_url": qr.verify_url(order) if order.has_verified_proof else "",
            "refund_form": refund_form,
            "show_payment": show_payment,
            "bank_accounts": snap.bank_accounts if show_payment else [],
            "page_title": f"Pesanan {order.code}",
        },
        status=400 if (form.errors or refund_form.errors) else 200,
        tab="pesanan",
    )


@require_safe
@auth.member_required
def bukti(request, code: str):
    order = _own_order(request, code)
    if not order.payment_proof:
        raise Http404
    return files.serve_private(order.payment_proof)


@require_safe
@auth.member_required
def refund_bukti(request, code: str):
    refund = _own_order(request, code).refund_or_none
    if refund is None or not refund.transfer_proof:
        raise Http404
    return files.serve_private(refund.transfer_proof)


# ---------------------------------------------------------------------------
# Chat dengan HANS Project
# ---------------------------------------------------------------------------
def _own_chat(request, pk: int) -> Conversation:
    return get_object_or_404(Conversation, pk=pk, member=request.member)


@require_safe
@auth.member_required
def chat_list(request):
    chats = list(request.member.chats.select_related("order"))
    return _render(
        request,
        "akun/chat_list.html",
        {
            "open_chats": [c for c in chats if c.is_open],
            "closed_chats": [c for c in chats if not c.is_open],
            "can_open": sum(1 for c in chats if c.is_open and not c.order_id) < Conversation.MAX_OPEN,
            "page_title": "Chat",
        },
        tab="chat",
    )


@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required
def chat_baru(request):
    member = request.member
    topic = request.GET.get("topik", "umum")
    form = ChatStartForm(request.POST or None, request.FILES or None, initial={"topic": topic if topic in TOPIC_KEYS else "umum"})
    open_count = member.chats.filter(status=Conversation.STATUS_OPEN, order__isnull=True).count()
    if request.method == "POST" and form.is_valid():
        if open_count >= Conversation.MAX_OPEN:
            form.add_error(None, "Anda masih punya beberapa obrolan yang terbuka. Lanjutkan di obrolan itu, ya.")
        elif not ratelimit.allow(f"chat-baru:{member.pk}", limit=10, window=86400):
            form.add_error(None, "Terlalu banyak obrolan baru hari ini. Coba lagi besok.")
        else:
            conversation = Conversation.objects.create(member=member, topic=form.cleaned_data["topic"])
            chat.post_message(
                conversation, sender=ChatMessage.SENDER_MEMBER,
                text=form.cleaned_data["text"], image=form.cleaned_data["image"],
            )
            log.info("Obrolan baru #%s dari pelanggan #%s.", conversation.pk, member.pk)
            return redirect("akun:chat", pk=conversation.pk)
    return _render(
        request,
        "akun/chat_baru.html",
        {"form": form, "open_count": open_count, "max_open": Conversation.MAX_OPEN, "page_title": "Chat baru"},
        status=400 if form.errors else 200,
        tab="chat",
    )


@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required
def chat_detail(request, pk: int):
    conversation = _own_chat(request, pk)
    wants_json = request.headers.get("Accept", "").startswith("application/json")
    form = ChatMessageForm()
    if request.method == "POST":
        form = ChatMessageForm(request.POST, request.FILES)
        error = ""
        if not conversation.is_open:
            error = "Obrolan ini sudah selesai. Silakan buka obrolan baru."
        elif not ratelimit.allow(f"chat:{request.member.pk}", limit=30, window=60):
            error = "Terlalu cepat. Tunggu sebentar, lalu kirim lagi."
        elif form.is_valid():
            message = chat.post_message(
                conversation, sender=ChatMessage.SENDER_MEMBER, text=form.cleaned_data["text"],
                image=form.cleaned_data["image"], reply_to_id=form.cleaned_data.get("reply_to"),
            )
            if wants_json:
                return JsonResponse({"ok": True, "last_id": message.pk, "html": chat.render_messages([message], viewer="member", request=request)})
            return redirect(reverse("akun:chat", args=[conversation.pk]) + f"#pesan-{message.pk}")
        else:
            error = " ".join(e for errors in form.errors.values() for e in errors)
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
    chat.mark_read(conversation, side=ChatMessage.SENDER_MEMBER)
    messages = list(chat.messages_for(conversation))
    return _render(
        request,
        "akun/chat_detail.html",
        {
            "conversation": conversation,
            "chat_messages": messages,
            "last_id": messages[-1].pk if messages else 0,
            "form": form,
            "page_title": f"Chat — {conversation.get_topic_display()}",
        },
        status=400 if form.errors else 200,
        tab="chat",
    )


@require_safe
@auth.member_required
def chat_poll(request, pk: int):
    """Pesan baru sesudah ``after`` (dipanggil chat.js berkala, hanya saat halaman terbuka)."""
    conversation = _own_chat(request, pk)
    try:
        after = max(0, int(request.GET.get("after", "0")))
    except ValueError:
        after = 0
    messages = list(chat.messages_for(conversation, after))
    if messages:
        chat.mark_read(conversation, side=ChatMessage.SENDER_MEMBER)
    return JsonResponse({
        "open": conversation.is_open,
        "last_id": messages[-1].pk if messages else after,
        "html": chat.render_messages(messages, viewer="member", request=request) if messages else "",
    })


@require_safe
@auth.member_required
def chat_gambar(request, pk: int, msg: int):
    message = get_object_or_404(ChatMessage, pk=msg, conversation=_own_chat(request, pk))
    if not message.image:
        raise Http404
    return files.serve_private(message.image)


@require_safe
def tanya(request):
    """Alamat lama tombol "Tanya Kami": sekarang membuka chat baru."""
    topic = request.GET.get("topik", "umum")
    return redirect(_with_query(reverse("akun:chat-baru"), topik=topic if topic in TOPIC_KEYS else "umum"))
