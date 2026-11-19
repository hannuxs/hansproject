"""Membuat akun admin (password diketik pemilik, tidak ada password bawaan)."""
from __future__ import annotations

import getpass
import re

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Membuat akun admin panel, atau mengganti password akun yang sudah ada."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Nama pengguna.")
        parser.add_argument("--jika-belum-ada", action="store_true", dest="if_none",
                            help="Lewati bila sudah ada akun admin (dipakai install.bat).")

    def handle(self, *args, **options):
        User = get_user_model()
        if options["if_none"] and User.objects.filter(is_staff=True, is_active=True).exists():
            self.stdout.write("Akun admin sudah ada. Lewati.")
            return

        self.stdout.write("\n=== Buat akun admin panel ===")
        username = options["username"] or input("Nama pengguna (huruf kecil/angka, contoh: pemilik): ").strip().lower()
        if not re.fullmatch(r"[a-z0-9._-]{3,30}", username or ""):
            raise CommandError("Nama pengguna 3-30 karakter: huruf kecil, angka, titik, minus, atau garis bawah.")

        user = User.objects.filter(username=username).first()
        if user:
            answer = input(f"Akun '{username}' sudah ada. Ganti password-nya? (y/n): ").strip().lower()
            if answer not in ("y", "ya"):
                self.stdout.write("Dibatalkan.")
                return
        else:
            user = User(username=username, is_staff=True, is_superuser=True, is_active=True)

        self.stdout.write("Password minimal 12 karakter. Saat diketik, password tidak terlihat di layar.")
        for _ in range(3):
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Ulangi password: "):
                self.stderr.write("Password tidak sama. Coba lagi.")
                continue
            try:
                password_validation.validate_password(password, user)
            except ValidationError as exc:
                self.stderr.write("Password belum memenuhi syarat:\n  - " + "\n  - ".join(exc.messages))
                continue
            user.set_password(password)
            user.is_staff = user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Akun admin '{username}' siap dipakai."))
            self.stdout.write("Saat pertama masuk, Anda akan diminta mengaktifkan verifikasi dua langkah (2FA).")
            return
        raise CommandError("Gagal 3 kali. Jalankan ulang perintah ini.")
