"""Formulir aplikasi kasir: dipakai pemilik toko (di hansproject.app) dan kasir (di subdomain)."""
from __future__ import annotations

import re

from django import forms
from django.core.exceptions import ValidationError

from apps.content.models import Package

from . import services, subdomains
from .cashier_auth import set_pin
from .models import MAX_PRICE, Cashier, Category, Outlet, Product, Store

WEAK_PINS = {"123456", "654321", "012345", "123123", "121212", "112233", "098765", "111222"}


class RupiahField(forms.IntegerField):
    """Menerima '15.000', 'Rp 15.000', atau '15000'."""

    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", 0)
        kwargs.setdefault("max_value", MAX_PRICE)
        super().__init__(**kwargs)
        self.widget = forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off", "placeholder": "Contoh: 15.000"})

    def to_python(self, value):
        if isinstance(value, str):
            value = re.sub(r"(?i)rp|[\s.]", "", value)
            if "," in value:
                head, _, tail = value.partition(",")
                if tail.strip("0"):
                    raise ValidationError("Harga tidak boleh ada sen. Tulis angka bulat, misalnya 15.000.")
                value = head
        return super().to_python(value)


def clean_text(value: str) -> str:
    return " ".join((value or "").split())


class SubdomainField(forms.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("label", "Alamat toko Anda")
        kwargs.setdefault("max_length", 60)
        super().__init__(**kwargs)
        self.widget.attrs.update(
            {"autocapitalize": "none", "autocomplete": "off", "spellcheck": "false", "inputmode": "url", "placeholder": "warungbudi"}
        )

    def clean(self, value):
        value = super().clean(value)
        if not value and not self.required:
            return ""
        return subdomains.validate(value)


# ---------------------------------------------------------------------------
# Pesanan (pelanggan)
# ---------------------------------------------------------------------------
class NewStoreOrderForm(forms.Form):
    subdomain = SubdomainField(help_text="3–30 huruf kecil, angka, atau tanda minus.")

    def clean_subdomain(self):
        name = self.cleaned_data["subdomain"]
        if services.subdomain_taken(name):
            raise ValidationError("Alamat ini sudah dipakai. Coba nama lain, misalnya tambahkan nama kota.")
        return name


class RenewForm(forms.Form):
    package = forms.ModelChoiceField(
        label="Paket", queryset=Package.objects.none(), widget=forms.RadioSelect, empty_label=None
    )
    new_subdomain = SubdomainField(
        label="Ganti alamat toko (opsional)", required=False,
        help_text="Kosongkan bila tidak ingin ganti. Alamat baru perlu kami periksa dulu sebelum dipakai.",
    )

    def __init__(self, *args, store: Store, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.fields["package"].queryset = Package.objects.filter(category=Package.CATEGORY_POS, is_active=True)
        self.fields["package"].label_from_instance = lambda p: f"{p.name} — {p.price_text}"
        if not self.is_bound and store.package_id:
            self.initial["package"] = store.package_id

    def clean_new_subdomain(self):
        name = self.cleaned_data.get("new_subdomain", "")
        if not name or name == self.store.subdomain:
            return ""
        if services.subdomain_taken(name, exclude_store=self.store):
            raise ValidationError("Alamat ini sudah dipakai. Coba nama lain.")
        return name


# ---------------------------------------------------------------------------
# Pengelolaan toko (pemilik)
# ---------------------------------------------------------------------------
class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ["name", "address", "phone", "receipt_footer", "receipt_width"]
        widgets = {"receipt_width": forms.RadioSelect}
        help_texts = {
            "name": "Tampil di layar kasir dan di bagian atas struk.",
            "address": "Dicetak di struk. Bila tiap outlet beda alamat, isi alamat di masing-masing outlet.",
        }

    def clean_name(self):
        return clean_text(self.cleaned_data["name"])

    def clean_address(self):
        return clean_text(self.cleaned_data["address"])

    def clean_phone(self):
        value = clean_text(self.cleaned_data["phone"])
        if value and not re.fullmatch(r"[0-9+()\- ]{6,20}", value):
            raise ValidationError("Nomor telepon hanya boleh angka, spasi, +, -, dan tanda kurung.")
        return value

    def clean_receipt_footer(self):
        return clean_text(self.cleaned_data["receipt_footer"])


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        labels = {"name": "Nama kategori"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Contoh: Minuman"})}

    def __init__(self, *args, store: Store, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store

    def clean_name(self):
        name = clean_text(self.cleaned_data["name"])
        others = self.store.categories.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if others.exists():
            raise ValidationError("Kategori dengan nama ini sudah ada.")
        if not self.instance.pk and self.store.categories.count() >= services.MAX_CATEGORIES_PER_STORE:
            raise ValidationError(f"Maksimal {services.MAX_CATEGORIES_PER_STORE} kategori.")
        return name

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.store = self.store
        if not obj.pk:
            last = self.store.categories.order_by("-order").values_list("order", flat=True).first()
            obj.order = (last or 0) + 10
        if commit:
            obj.save()
        return obj


class ProductForm(forms.ModelForm):
    price = RupiahField(label="Harga jual (Rp)")

    class Meta:
        model = Product
        fields = ["name", "category", "price", "code", "is_active"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Contoh: Kopi Susu", "autocomplete": "off"})}

    def __init__(self, *args, store: Store, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.fields["category"].queryset = store.categories.all()
        self.fields["category"].empty_label = "Tanpa kategori"
        self.fields["code"].widget.attrs.update({"autocomplete": "off", "spellcheck": "false"})

    def clean_name(self):
        return clean_text(self.cleaned_data["name"])

    def clean_code(self):
        code = clean_text(self.cleaned_data["code"])
        if code and self.store.products.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Kode barang ini sudah dipakai barang lain.")
        return code

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and self.store.products.count() >= services.MAX_PRODUCTS_PER_STORE:
            raise ValidationError(f"Jumlah barang sudah mencapai batas ({services.MAX_PRODUCTS_PER_STORE}).")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.store = self.store
        if commit:
            obj.save()
        return obj


class OutletForm(forms.ModelForm):
    class Meta:
        model = Outlet
        fields = ["name", "address", "is_active"]
        labels = {"name": "Nama toko / cabang", "address": "Alamat toko", "is_active": "Toko aktif (kasir boleh masuk)"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Contoh: Cabang Pasar"})}

    def __init__(self, *args, store: Store, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store

    def clean_name(self):
        return clean_text(self.cleaned_data["name"])

    def clean_address(self):
        return clean_text(self.cleaned_data["address"])

    def clean(self):
        cleaned = super().clean()
        becomes_active = cleaned.get("is_active") and not (self.instance.pk and self.instance.is_active)
        if becomes_active:
            active = self.store.outlets.filter(is_active=True).exclude(pk=self.instance.pk).count()
            if active >= self.store.outlet_limit:
                raise ValidationError(
                    f"Kuota Anda {self.store.outlet_limit} toko aktif. Nonaktifkan toko lain dulu, "
                    "atau beli toko tambahan di menu Toko > Tambah toko."
                )
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.store = self.store
        if not obj.pk:
            obj.number = services.next_outlet_number(self.store)
        if commit:
            obj.save()
        return obj


class CashierForm(forms.ModelForm):
    """Akun kasir untuk satu outlet: nama pengguna + PIN 6 angka (dibuat pemilik)."""

    pin = forms.CharField(
        label="PIN (6 angka)", required=False, strip=True,
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "new-password", "maxlength": 6}),
    )
    pin2 = forms.CharField(
        label="Ulangi PIN", required=False, strip=True,
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "new-password", "maxlength": 6}),
    )

    class Meta:
        model = Cashier
        fields = ["username", "is_active"]
        labels = {"is_active": "Akun kasir aktif"}
        help_texts = {"username": "Dipakai kasir untuk masuk. Huruf kecil, angka, titik, minus. Contoh: kasir.pasar"}
        widgets = {"username": forms.TextInput(attrs={"autocapitalize": "none", "autocomplete": "off", "spellcheck": "false"})}

    def __init__(self, *args, store: Store, outlet: Outlet, **kwargs):
        super().__init__(*args, **kwargs)
        self.store, self.outlet = store, outlet
        if self.instance.pk:
            self.fields["pin"].help_text = "Kosongkan bila tidak ingin mengganti PIN. Mengganti PIN membuat kasir harus masuk ulang."
        else:
            self.fields["pin"].required = True
            self.fields["pin2"].required = True

    def clean_username(self):
        name = self.cleaned_data["username"].strip().lower()
        if self.store.cashiers.filter(username=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Nama pengguna ini sudah dipakai kasir lain.")
        return name

    def clean(self):
        cleaned = super().clean()
        pin, pin2 = cleaned.get("pin", ""), cleaned.get("pin2", "")
        if pin or pin2 or not self.instance.pk:
            if not re.fullmatch(r"\d{6}", pin):
                self.add_error("pin", "PIN harus 6 angka.")
            elif len(set(pin)) == 1 or pin in WEAK_PINS:
                self.add_error("pin", "PIN terlalu mudah ditebak. Pakai kombinasi angka lain.")
            elif pin != pin2:
                self.add_error("pin2", "PIN tidak sama.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.store, obj.outlet = self.store, self.outlet
        pin = self.cleaned_data.get("pin")
        if pin:
            set_pin(obj, pin)
        if commit:
            obj.save()
            if not obj.is_active:
                obj.sessions.all().delete()
        return obj


class CashierLoginForm(forms.Form):
    username = forms.CharField(
        label="Nama pengguna", max_length=30,
        widget=forms.TextInput(attrs={"autocapitalize": "none", "autocomplete": "username", "spellcheck": "false", "autofocus": True}),
    )
    pin = forms.CharField(
        label="PIN", max_length=6, min_length=6,
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "current-password", "maxlength": 6}),
    )


class AddOutletOrderForm(forms.Form):
    quantity = forms.IntegerField(
        label="Jumlah toko tambahan", min_value=1, max_value=20, initial=1,
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
        help_text="Setiap toko tambahan punya 1 akun kasir sendiri.",
    )


class VoidForm(forms.Form):
    reason = forms.CharField(
        label="Alasan pembatalan", min_length=3, max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Contoh: salah input jumlah"}),
    )


# ---------------------------------------------------------------------------
# Panel admin
# ---------------------------------------------------------------------------
class StoreAdminForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = [
            "name", "subdomain", "status", "active_until", "package", "package_name", "base_outlets",
            "extra_outlets", "admin_note",
        ]
        widgets = {"active_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "admin_note": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "subdomain": "Mengubah alamat membuat alamat lama langsung tidak bisa dibuka.",
            "active_until": "Setelah tanggal ini: 7 hari masa tenggang, lalu kasir terkunci. 30 hari setelah tanggal ini data dihapus permanen.",
            "base_outlets": "Biasanya sama dengan jumlah outlet di paket (Tunas 2, Tumbuh 10).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = Package.objects.filter(category=Package.CATEGORY_POS)

    def clean_subdomain(self):
        name = subdomains.validate(self.cleaned_data["subdomain"])
        if Store.objects.filter(subdomain=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Alamat ini sudah dipakai toko lain.")
        return name

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            services.enforce_outlet_limit(obj)
        return obj
