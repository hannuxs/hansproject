"""Mereset 2FA akun admin (misalnya HP hilang). Hanya bisa dari server."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import TwoFactorDevice
from apps.content.models import AuditLog


class Command(BaseCommand):
    help = "Menghapus 2FA akun admin. Saat masuk berikutnya, pemilik diminta mengaktifkan 2FA lagi."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"].strip().lower()).first()
        if not user:
            raise CommandError("Akun tidak ditemukan.")
        if input(f"Reset 2FA akun '{user.username}'? Ketik YA untuk lanjut: ").strip() != "YA":
            self.stdout.write("Dibatalkan.")
            return
        TwoFactorDevice.objects.filter(user=user).delete()
        AuditLog.objects.create(
            username=user.username, action=AuditLog.ACTION_SECURITY, target_type="akun",
            target_repr=user.username, detail="2FA direset dari server",
        )
        self.stdout.write(self.style.SUCCESS("2FA direset. Masuk ke panel untuk mengaktifkannya lagi."))
