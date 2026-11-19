from django.core.management.base import BaseCommand

from apps.content.seeding import seed


class Command(BaseCommand):
    help = "Mengisi data awal (paket, harga, FAQ, dll.). Aman dijalankan berulang kali."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lengkapi",
            action="store_true",
            help="Tambahkan data awal yang belum ada tanpa menimpa data yang sudah diubah.",
        )

    def handle(self, *args, **options):
        created = seed(only_missing=options["lengkapi"])
        if not created:
            self.stdout.write(self.style.SUCCESS("Data awal sudah ada. Tidak ada yang diubah."))
            return
        summary = ", ".join(f"{k}: {v}" for k, v in created.items())
        self.stdout.write(self.style.SUCCESS(f"Data awal berhasil diisi ({summary})."))
