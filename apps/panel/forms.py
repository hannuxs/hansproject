"""Form panel pengelola. Semua input divalidasi di sisi server."""
from __future__ import annotations

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.forms import inlineformset_factory, modelformset_factory
from django.forms.renderers import TemplatesSetting
from django.utils import timezone

from apps.content.models import (
    AddOn,
    Announcement,
    BankAccount,
    ComparisonRow,
    Faq,
    IncludedFeature,
    LegalPage,
    Package,
    PackageFeature,
    PackageNote,
    SiteSettings,
    Testimonial,
)
from apps.core.images import PHOTO, QR_CODE, RECEIPT, ImageRule, process_image
from apps.members.models import Member, Order, OrderItem, Refund


class PanelFormRenderer(TemplatesSetting):
    form_template_name = "panel/forms/form.html"
    field_template_name = "panel/forms/field.html"


# ---------------------------------------------------------------------------
# Mixin yang dipakai ulang
# ---------------------------------------------------------------------------
class ImageUploadMixin:
    """Memproses upload gambar dengan aman (lihat apps/core/images.py).

    Set ``image_fields = {"nama_field": ATURAN}`` di subclass.
    """

    image_fields: dict[str, ImageRule] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_files = {name: getattr(self.instance, name) for name in self.image_fields}
        for name in self.image_fields:
            if name in self.fields:
                self.fields[name].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"

    def _clean_image(self, name: str):
        value = self.cleaned_data.get(name)
        if isinstance(value, UploadedFile):
            return process_image(value, self.image_fields[name])
        return value

    def clean(self):
        cleaned = super().clean()
        for name in self.image_fields:
            if name in cleaned and not self.has_error(name):
                try:
                    cleaned[name] = self._clean_image(name)
                except ValidationError as exc:
                    self.add_error(name, exc)
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            for name, old in self._old_files.items():
                if old and name in self.changed_data and getattr(obj, name) != old:
                    old.storage.delete(old.name)
        return obj


def https_only(value: str) -> str:
    if value and not value.startswith("https://"):
        raise ValidationError("Link harus diawali https://")
    return value


# ---------------------------------------------------------------------------
# Login & akun
# ---------------------------------------------------------------------------
class LoginForm(forms.Form):
    username = forms.CharField(label="Nama pengguna", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}))
    password = forms.CharField(label="Password", max_length=256, strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class OtpForm(forms.Form):
    code = forms.CharField(
        label="Kode 6 angka dari aplikasi Authenticator",
        max_length=12,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric", "pattern": "[0-9 ]*", "autofocus": True}),
    )

    def clean_code(self):
        code = "".join(ch for ch in self.cleaned_data["code"] if ch.isdigit())
        if len(code) != 6:
            raise ValidationError("Kode harus 6 angka.")
        return code


class PanelPasswordChangeForm(PasswordChangeForm):
    pass


# ---------------------------------------------------------------------------
# Konten
# ---------------------------------------------------------------------------
class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = [
            "name", "code", "category", "icon", "tagline", "description",
            "price_prefix", "price", "price_suffix", "monthly_price", "outlet_count",
            "badge", "is_highlighted", "includes_from", "order", "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Package.objects.filter(category=Package.CATEGORY_POS)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["includes_from"].queryset = qs


PackageFeatureFormSet = inlineformset_factory(
    Package, PackageFeature, fields=["simple", "technical", "icon", "show_in_highlights", "order"],
    extra=1, can_delete=True, max_num=40, validate_max=True,
)
PackageNoteFormSet = inlineformset_factory(
    Package, PackageNote, fields=["simple", "technical", "order"], extra=1, can_delete=True, max_num=20, validate_max=True,
)


class IncludedFeatureForm(forms.ModelForm):
    class Meta:
        model = IncludedFeature
        fields = ["simple", "technical", "icon", "order"]


class AddOnForm(forms.ModelForm):
    class Meta:
        model = AddOn
        fields = ["group", "name", "price", "unit", "description", "order", "is_active"]


class ComparisonRowForm(forms.ModelForm):
    """Satu kolom isian untuk setiap paket aktif; disimpan sebagai JSON."""

    class Meta:
        model = ComparisonRow
        fields = ["label", "order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        values = self.instance.values if isinstance(self.instance.values, dict) else {}
        self.packages = list(Package.objects.order_by("order", "id"))
        for pkg in self.packages:
            self.fields[f"val_{pkg.code}"] = forms.CharField(
                label=f"Paket {pkg.name}", max_length=120, required=False, initial=values.get(pkg.code, ""),
            )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.values = {pkg.code: self.cleaned_data.get(f"val_{pkg.code}", "").strip() for pkg in self.packages}
        if commit:
            obj.save()
        return obj


class FaqForm(forms.ModelForm):
    class Meta:
        model = Faq
        fields = ["question", "answer", "order", "is_active"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 7})}


class TestimonialForm(ImageUploadMixin, forms.ModelForm):
    image_fields = {"photo": PHOTO}

    class Meta:
        model = Testimonial
        fields = ["name", "business", "location", "quote", "photo", "order", "is_active"]
        widgets = {"quote": forms.Textarea(attrs={"rows": 4})}


class LegalPageForm(forms.ModelForm):
    class Meta:
        model = LegalPage
        fields = ["title", "body", "is_draft"]
        widgets = {"body": forms.Textarea(attrs={"rows": 24})}


class SiteSettingsForm(ImageUploadMixin, forms.ModelForm):
    image_fields = {"qris_image": QR_CODE}

    class Meta:
        model = SiteSettings
        # instagram_url tidak ditampilkan: link Instagram selalu dibentuk dari username.
        exclude = ["seeded_at", "instagram_url"]
        widgets = {"legal_version": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean(self):
        cleaned = super().clean()
        for name in ("facebook_url", "tiktok_url", "youtube_url"):
            try:
                https_only(cleaned.get(name, ""))
            except ValidationError as exc:
                self.add_error(name, exc)
        if cleaned.get("announcement_active") and not cleaned.get("announcement_text"):
            self.add_error("announcement_text", "Isi teks pengumuman, atau matikan pengumuman.")
        return cleaned

    def __init__(self, *args, **kwargs):
        # Pemilik boleh mengetik "@hansproject.app"; tanda @ dibuang sebelum divalidasi.
        data = kwargs.get("data") if "data" in kwargs else (args[0] if args else None)
        if data is not None and "instagram_username" in data:
            data = data.copy()
            data["instagram_username"] = data["instagram_username"].strip().lstrip("@")
            if "data" in kwargs:
                kwargs["data"] = data
            else:
                args = (data, *args[1:])
        super().__init__(*args, **kwargs)


BankAccountFormSet = modelformset_factory(
    BankAccount, fields=["bank_name", "account_number", "account_holder", "is_active", "order"],
    extra=1, can_delete=True, max_num=10, validate_max=True,
)


# ---------------------------------------------------------------------------
# Pelanggan (akun yang masuk dengan Google)
# ---------------------------------------------------------------------------
class OrderAdminForm(forms.ModelForm):
    """Ubah status pesanan. Pesanan kasir yang diubah menjadi Aktif otomatis membuat /
    memperpanjang toko (lihat apps/pos/services.activate_order)."""

    approve_subdomain = forms.BooleanField(
        label="Setujui ganti alamat toko", required=False,
        help_text="Centang bila alamat baru boleh dipakai. Alamat lama langsung tidak bisa dibuka setelah disimpan.",
    )

    class Meta:
        model = Order
        fields = ["status", "admin_note"]
        widgets = {"admin_note": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.wants_new_subdomain or self.instance.activated_at:
            del self.fields["approve_subdomain"]
        self._activate = False

    def clean(self):
        cleaned = super().clean()
        order = self.instance
        becomes_active = cleaned.get("status") == Order.STATUS_ACTIVE and not order.activated_at
        if becomes_active and order.is_pos:
            from apps.pos import services as pos_services

            problem = pos_services.activation_problem(order, approve_subdomain=cleaned.get("approve_subdomain", False))
            if problem:
                self.add_error("status", problem)
            else:
                self._activate = True
        return cleaned

    def save(self, commit=True):
        order = super().save(commit=False)
        if self._activate:
            from apps.pos import services as pos_services

            pos_services.activate_order(order, approve_subdomain=self.cleaned_data.get("approve_subdomain", False))
        if commit:
            order.save()
        return order


OrderItemFormSet = inlineformset_factory(
    Order, OrderItem, fields=["name", "amount", "period", "note"],
    extra=1, can_delete=True, max_num=40, validate_max=True,
    widgets={
        "period": forms.TextInput(attrs={"placeholder": "mis. 1 tahun, 3 bulan, 14 hari"}),
        "note": forms.TextInput(attrs={"placeholder": "opsional"}),
    },
)


class RefundAdminForm(ImageUploadMixin, forms.ModelForm):
    """Proses refund: ubah status, nominal, catatan, dan unggah bukti transfer."""

    image_fields = {"transfer_proof": RECEIPT}

    class Meta:
        model = Refund
        fields = ["status", "amount", "admin_note", "transfer_proof"]
        widgets = {"admin_note": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == Refund.STATUS_DONE:
            if not cleaned.get("amount"):
                self.add_error("amount", "Isi nominal yang ditransfer.")
            if not cleaned.get("transfer_proof") and not self.instance.transfer_proof:
                self.add_error("transfer_proof", "Unggah bukti transfer refund.")
        if cleaned.get("status") == Refund.STATUS_REJECTED and not cleaned.get("admin_note"):
            self.add_error("admin_note", "Tulis alasan penolakan untuk pelanggan.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if obj.status in (Refund.STATUS_DONE, Refund.STATUS_REJECTED) and not obj.processed_at:
            obj.processed_at = timezone.now()
        if commit:
            obj.save()
            for name, old in self._old_files.items():
                if old and name in self.changed_data and getattr(obj, name) != old:
                    old.storage.delete(old.name)
        return obj


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "body", "tone", "starts_at", "ends_at", "is_active"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("starts_at", "ends_at"):
            self.fields[name].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("starts_at"), cleaned.get("ends_at")
        if start and end and end <= start:
            self.add_error("ends_at", "Waktu berhenti harus setelah waktu mulai.")
        return cleaned


class MemberAdminForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["is_active"]
