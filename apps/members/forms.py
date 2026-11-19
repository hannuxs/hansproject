from __future__ import annotations

import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from apps.core.images import RECEIPT, process_image

from .models import TOPICS, Member, Refund


def normalize_phone(raw: str) -> str:
    """'0812-3456 7890' / '+62 812…' / '62812…' / '812…' -> '62812…'."""
    digits = re.sub(r"[\s().-]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit():
        raise ValidationError("Nomor HP hanya boleh berisi angka.")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    if not re.fullmatch(r"628\d{7,12}", digits):
        raise ValidationError("Nomor HP tidak valid. Contoh: 0812 3456 7890.")
    return digits


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["name", "phone", "business_name"]
        labels = {"name": "Nama Anda", "phone": "Nomor HP", "business_name": "Nama usaha / toko"}
        help_texts = {
            "phone": "Dipakai untuk aktivasi dan layanan pelanggan. Tidak ditampilkan ke orang lain.",
            "business_name": "Misalnya: Warung Bu Sari. Belum punya nama usaha? Tulis nama Anda.",
        }
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name", "maxlength": 120}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "0812 3456 7890"}),
            "business_name": forms.TextInput(attrs={"autocomplete": "organization", "maxlength": 120}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = True
        if self.instance.phone and not self.is_bound:
            self.initial["phone"] = self.instance.phone_display

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean_business_name(self):
        return " ".join(self.cleaned_data["business_name"].split())

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class PaymentProofForm(forms.Form):
    proof = forms.ImageField(
        label="Foto bukti bayar",
        help_text="Foto atau screenshot bukti transfer / QRIS. Format JPG, PNG, atau WebP, maksimal 3 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def clean_proof(self):
        value = self.cleaned_data["proof"]
        if isinstance(value, UploadedFile):
            return process_image(value, RECEIPT)
        raise ValidationError("Pilih foto bukti bayar.")


IMAGE_ACCEPT = "image/jpeg,image/png,image/webp"


class ChatMessageForm(forms.Form):
    """Satu pesan chat: teks, gambar, atau keduanya. Bisa membalas pesan lain."""

    text = forms.CharField(
        label="Pesan", required=False, max_length=2000, strip=True,
        widget=forms.Textarea(attrs={"rows": 1, "maxlength": 2000, "placeholder": "Tulis pesan…", "autocomplete": "off"}),
    )
    image = forms.ImageField(
        label="Gambar", required=False,
        widget=forms.ClearableFileInput(attrs={"accept": IMAGE_ACCEPT}),
    )
    reply_to = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def clean_image(self):
        value = self.cleaned_data.get("image")
        if isinstance(value, UploadedFile):
            return process_image(value, RECEIPT)
        return None

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("text") and not cleaned.get("image") and not self.errors:
            raise ValidationError("Tulis pesan atau pilih gambar.")
        return cleaned


class ChatStartForm(ChatMessageForm):
    topic = forms.ChoiceField(label="Topik", choices=TOPICS, initial="umum")
    field_order = ["topic", "text", "image"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text"].widget.attrs.update({"rows": 4, "placeholder": "Tulis pertanyaan atau keperluan Anda…"})


class RefundRequestForm(forms.ModelForm):
    class Meta:
        model = Refund
        fields = ["bank_name", "account_number", "account_holder", "note"]
        labels = {
            "bank_name": "Bank / dompet digital tujuan",
            "account_number": "Nomor rekening / nomor akun",
            "account_holder": "Nama pemilik rekening",
            "note": "Catatan (opsional)",
        }
        help_texts = {
            "bank_name": "Contoh: BRI, BCA, Mandiri, DANA, GoPay.",
            "account_holder": "Sesuai Syarat & Ketentuan, refund dikirim ke rekening atas nama Anda sendiri.",
        }
        widgets = {
            "bank_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "account_number": forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
            "account_holder": forms.TextInput(attrs={"autocomplete": "name"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("bank_name", "account_number", "account_holder"):
            self.fields[name].required = True

    def clean_bank_name(self):
        return " ".join(self.cleaned_data["bank_name"].split())

    def clean_account_holder(self):
        return " ".join(self.cleaned_data["account_holder"].split())

    def clean_account_number(self):
        digits = re.sub(r"[\s.-]", "", self.cleaned_data["account_number"])
        if not re.fullmatch(r"\d{5,25}", digits):
            raise ValidationError("Nomor rekening hanya angka, 5 sampai 25 digit.")
        return digits
