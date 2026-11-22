"""Formulir aplikasi kasir: dipakai pemilik toko (di hansproject.app) dan kasir (di subdomain)."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import models

from apps.content.models import Package
from apps.core.images import ImageRule, process_image

from . import palette, services, subdomains
from .cashier_auth import set_pin
from .models import MAX_PRICE, Cashier, Category, Product, Store, StoreHighlight, StorePage, Subscription

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
        self.fields["package"].queryset = Package.objects.filter(category=Package.CATEGORY_POS, is_active=True, price__gt=0)
        self.fields["package"].label_from_instance = lambda p: f"{p.name} — {p.price_text}"
        if not self.is_bound and store.subscription.package_id:
            self.initial["package"] = store.subscription.package_id

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
            "address": "Dicetak di struk.",
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


class NewStoreForm(forms.Form):
    """Toko baru dari sisa kuota langganan: nama + alamat (subdomain) sendiri."""

    name = forms.CharField(
        label="Nama toko", max_length=60,
        widget=forms.TextInput(attrs={"placeholder": "Contoh: Cabang Pasar", "autocomplete": "off"}),
        help_text="Tampil di layar kasir dan di struk. Bisa diubah nanti.",
    )
    subdomain = SubdomainField(help_text="3–30 huruf kecil, angka, atau tanda minus. Langsung aktif setelah disimpan.")

    def clean_name(self):
        return clean_text(self.cleaned_data["name"])

    def clean_subdomain(self):
        name = self.cleaned_data["subdomain"]
        if services.subdomain_taken(name):
            raise ValidationError("Alamat ini sudah dipakai. Coba nama lain, misalnya tambahkan nama kota.")
        return name


class CashierForm(forms.ModelForm):
    """Akun kasir toko (satu per toko): nama pengguna + PIN 6 angka, dibuat pemilik.

    Akun yang sama bisa dipakai masuk di banyak perangkat sekaligus.
    """

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
        help_texts = {"username": "Dipakai kasir untuk masuk. Huruf kecil, angka, titik, minus. Contoh: kasir"}
        widgets = {"username": forms.TextInput(attrs={"autocapitalize": "none", "autocomplete": "off", "spellcheck": "false"})}

    def __init__(self, *args, store: Store, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        if self.instance.pk:
            self.fields["pin"].help_text = "Kosongkan bila tidak ingin mengganti PIN. Mengganti PIN membuat semua perangkat kasir harus masuk ulang."
        else:
            self.fields["pin"].required = True
            self.fields["pin2"].required = True
            # Akun baru selalu aktif (kotak "aktif" baru tampil saat mengubah akun).
            del self.fields["is_active"]

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

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
        obj.store = self.store
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


class AddStoreOrderForm(forms.Form):
    quantity = forms.IntegerField(
        label="Jumlah toko tambahan", min_value=1, max_value=20, initial=1,
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
        help_text="Setiap toko tambahan punya alamat (subdomain), barang, laporan, dan akun kasir sendiri.",
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
    """Panel: data toko + langganannya (paket, kuota, masa aktif berlaku untuk semua toko di langganan)."""

    SUB_FIELDS = ["status", "active_until", "package", "package_name", "base_stores", "extra_stores", "admin_note"]

    class Meta:
        model = Store
        fields = ["name", "subdomain", "is_active"]
        help_texts = {"subdomain": "Mengubah alamat membuat alamat lama langsung tidak bisa dibuka."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sub_form = forms.models.modelform_factory(
            Subscription, fields=self.SUB_FIELDS,
            widgets={"active_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                     "admin_note": forms.Textarea(attrs={"rows": 3})},
            help_texts={
                "status": "Berlaku untuk SEMUA toko di langganan ini.",
                "active_until": "Berlaku untuk semua toko di langganan ini. Setelah tanggal ini: 7 hari masa tenggang, "
                                "lalu kasir terkunci. 30 hari setelah tanggal ini data dihapus permanen.",
                "base_stores": "Biasanya sama dengan jumlah toko di paket (Tunas 2, Tumbuh 10).",
            },
        )
        self.sub_form = sub_form(self.data or None, instance=self.instance.subscription, prefix="langganan")
        self.sub_form.fields["package"].queryset = Package.objects.filter(category=Package.CATEGORY_POS)
        for name in self.SUB_FIELDS:
            self.fields[f"langganan-{name}"] = self.sub_form.fields[name]
            self.initial[f"langganan-{name}"] = self.sub_form.initial.get(name)

    def clean_subdomain(self):
        name = subdomains.validate(self.cleaned_data["subdomain"])
        if Store.objects.filter(subdomain=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Alamat ini sudah dipakai toko lain.")
        return name

    def clean(self):
        cleaned = super().clean()
        if not self.sub_form.is_valid():
            for name, errors in self.sub_form.errors.items():
                for error in errors:
                    self.add_error(f"langganan-{name}" if name != "__all__" else None, error)
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            sub = self.sub_form.save()
            services.enforce_store_limit(sub)
        return obj


# ---------------------------------------------------------------------------
# Halaman toko
# ---------------------------------------------------------------------------
LOGO_RULE = ImageRule(max_side=512, output="WEBP", quality=88)
COVER_RULE = ImageRule(max_side=1600, output="WEBP", quality=80)
HIGHLIGHT_RULE = ImageRule(max_side=1000, output="WEBP", quality=80)
IMAGE_ACCEPT = "image/jpeg,image/png,image/webp"
MAPS_SHORT_HOSTS = {"maps.app.goo.gl", "maps.google.com"}
MAPS_PATH_HOSTS = {"goo.gl", "www.google.com", "google.com", "www.google.co.id", "google.co.id"}


def _process(form, name: str, rule: ImageRule):
    value = form.cleaned_data.get(name)
    if isinstance(value, UploadedFile):
        try:
            return process_image(value, rule)
        except ValidationError as exc:
            form.add_error(name, exc)
            return None
    return value


class StorePageForm(forms.ModelForm):
    """Template, warna, dan isi halaman toko (disimpan sebagai draf)."""

    remove_logo = forms.BooleanField(label="Hapus logo", required=False)
    # Lebih longgar dari kolomnya: pemilik boleh menempel link profil, nanti diringkas jadi nama pengguna.
    instagram = forms.CharField(
        label="Instagram", max_length=200, required=False,
        help_text="Nama pengguna atau link profil Instagram toko.",
        widget=forms.TextInput(attrs={"autocapitalize": "none", "spellcheck": "false", "placeholder": "warungbusari"}),
    )
    remove_cover = forms.BooleanField(label="Hapus foto sampul", required=False)

    class Meta:
        model = StorePage
        fields = ["template", "color", "tagline", "about", "hours", "phone", "instagram", "maps_url", "show_prices", "logo", "cover"]
        widgets = {
            "template": forms.RadioSelect,
            "color": forms.TextInput(attrs={"type": "color", "class": "color-input"}),
            "about": forms.Textarea(attrs={"rows": 4, "placeholder": "Cerita singkat toko Anda: apa yang dijual, sejak kapan, apa keunggulannya."}),
            "tagline": forms.TextInput(attrs={"placeholder": "Sembako lengkap, harga bersahabat"}),
            "hours": forms.TextInput(attrs={"placeholder": "Setiap hari 07.00–21.00"}),
            "phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "off"}),
            "instagram": forms.TextInput(attrs={"autocapitalize": "none", "spellcheck": "false", "placeholder": "warungbusari"}),
            "maps_url": forms.URLInput(attrs={"placeholder": "https://maps.app.goo.gl/..."}),
            "logo": forms.FileInput(attrs={"accept": IMAGE_ACCEPT}),
            "cover": forms.FileInput(attrs={"accept": IMAGE_ACCEPT}),
        }
        help_texts = {
            "logo": "Opsional. JPG, PNG, atau WebP, maksimal 3 MB. Bentuk persegi paling bagus.",
            "cover": "Opsional. Foto toko atau barang andalan, posisi mendatar. Maksimal 3 MB.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old = {"logo": self.instance.logo.name or "", "cover": self.instance.cover.name or ""}

    def clean_color(self):
        value = palette.normalize(self.cleaned_data.get("color", ""))
        if not value:
            raise ValidationError("Pilih warna.")
        return value

    def clean_tagline(self):
        return clean_text(self.cleaned_data["tagline"])

    def clean_about(self):
        lines = [" ".join(line.split()) for line in (self.cleaned_data["about"] or "").splitlines()]
        return "\n".join(lines).strip()[:500]

    def clean_hours(self):
        return clean_text(self.cleaned_data["hours"])

    def clean_phone(self):
        value = clean_text(self.cleaned_data["phone"])
        if value and not re.fullmatch(r"[0-9+()\- ]{6,20}", value):
            raise ValidationError("Nomor telepon hanya boleh angka, spasi, +, -, dan tanda kurung.")
        return value

    def clean_instagram(self):
        value = (self.cleaned_data.get("instagram") or "").strip()
        value = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", value, flags=re.I).strip("/@ ")
        value = value.split("?")[0].split("/")[0]
        if value and not re.fullmatch(r"[A-Za-z0-9._]{1,30}", value):
            raise ValidationError("Isi nama pengguna Instagram saja, misalnya warungbusari.")
        return value

    def clean_maps_url(self):
        value = (self.cleaned_data.get("maps_url") or "").strip()
        if not value:
            return ""
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        ok = parts.scheme == "https" and (
            host in MAPS_SHORT_HOSTS or (host in MAPS_PATH_HOSTS and parts.path.startswith("/maps"))
        )
        if not ok:
            raise ValidationError("Tempel link dari Google Maps (tombol Bagikan), misalnya https://maps.app.goo.gl/...")
        return value

    def clean(self):
        cleaned = super().clean()
        cleaned["logo"] = _process(self, "logo", LOGO_RULE)
        cleaned["cover"] = _process(self, "cover", COVER_RULE)
        return cleaned

    def save(self, commit=True):
        page = super().save(commit=False)
        if self.cleaned_data.get("remove_logo") and "logo" not in self.files:
            page.logo = ""
        if self.cleaned_data.get("remove_cover") and "cover" not in self.files:
            page.cover = ""
        if commit:
            page.save()
            from . import pages

            pages.cleanup(page, self._old.values())
        return page


class HighlightForm(forms.ModelForm):
    """Satu barang unggulan: dari data barang (boleh diberi foto) atau gambar lain."""

    class Meta:
        model = StoreHighlight
        fields = ["product", "image", "title", "caption"]
        widgets = {
            "image": forms.FileInput(attrs={"accept": IMAGE_ACCEPT}),
            "title": forms.TextInput(attrs={"placeholder": "Contoh: Promo Jumat Berkah"}),
            "caption": forms.TextInput(attrs={"placeholder": "Contoh: Paling laris, dibuat tiap pagi"}),
        }
        labels = {"product": "Pilih dari data barang", "image": "Foto"}
        help_texts = {
            "product": "Kosongkan bila ingin menampilkan gambar lain, misalnya promo atau suasana toko.",
            "image": "Wajib bila tidak memilih barang. Opsional untuk barang. Maksimal 3 MB.",
            "title": "Kosongkan untuk memakai nama barang.",
        }

    def __init__(self, *args, page: StorePage, **kwargs):
        super().__init__(*args, **kwargs)
        self.page = page
        used = list(page.highlights.exclude(product=None).values_list("product_id", flat=True))
        self.fields["product"].queryset = page.store.products.filter(is_active=True).exclude(pk__in=used).order_by("name")
        self.fields["product"].empty_label = "— Bukan dari data barang (gambar lain) —"

    def clean_title(self):
        return clean_text(self.cleaned_data["title"])

    def clean_caption(self):
        return clean_text(self.cleaned_data["caption"])

    def clean(self):
        cleaned = super().clean()
        if self.page.highlights.count() >= StorePage.MAX_HIGHLIGHTS:
            raise ValidationError(f"Barang unggulan paling banyak {StorePage.MAX_HIGHLIGHTS}. Hapus salah satu dulu.")
        cleaned["image"] = _process(self, "image", HIGHLIGHT_RULE)
        if not cleaned.get("product") and not self.has_error("image"):
            if not cleaned.get("image"):
                self.add_error("image", "Pilih barang dari daftar, atau unggah gambar.")
            elif not cleaned.get("title"):
                self.add_error("title", "Beri judul untuk gambar ini.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        item.page = self.page
        item.order = (self.page.highlights.aggregate(m=models.Max("order"))["m"] or 0) + 1
        if commit:
            item.save()
        return item
