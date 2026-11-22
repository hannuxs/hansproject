"""Langkah 2/3: memindahkan data ke susunan baru (1 toko = 1 subdomain = 1 kasir).

- Setiap toko lama mendapat satu langganan (paket, kuota, masa aktif dipindah ke sana).
- Outlet pertama menyatu dengan tokonya (nomor struk, status aktif, alamat).
- Outlet ke-2 dst. menjadi TOKO BARU dalam langganan yang sama: dapat subdomain baru
  (``<alamat-lama>-<nomor>``), salinan kategori & barang, serta akun kasir dan
  transaksi milik outlet itu. Struk lama tetap benar (nama & harga tersalin di transaksi).
"""
from django.core.exceptions import ValidationError
from django.db import migrations

from apps.pos import subdomains


def _free_subdomain(Store, Order, base: str, start: int) -> str:
    for i in range(start, start + 500):
        tail = f"-{i}"
        candidate = f"{base[: 30 - len(tail)].rstrip('-')}{tail}"
        try:
            candidate = subdomains.validate(candidate)
        except ValidationError:
            continue
        if not Store.objects.filter(subdomain=candidate).exists() and not Order.objects.filter(subdomain=candidate).exists():
            return candidate
    raise RuntimeError(f"Tidak menemukan alamat kosong untuk {base}")


def forwards(apps, schema_editor):
    Store = apps.get_model("pos", "Store")
    Subscription = apps.get_model("pos", "Subscription")
    Outlet = apps.get_model("pos", "Outlet")
    Cashier = apps.get_model("pos", "Cashier")
    Category = apps.get_model("pos", "Category")
    Product = apps.get_model("pos", "Product")
    Sale = apps.get_model("pos", "Sale")
    SaleItem = apps.get_model("pos", "SaleItem")
    Order = apps.get_model("members", "Order")

    for store in list(Store.objects.filter(subscription__isnull=True).order_by("pk")):
        sub = Subscription.objects.create(
            owner_id=store.owner_id,
            package_id=store.package_id,
            package_name=store.package_name,
            base_stores=store.base_outlets,
            extra_stores=store.extra_outlets,
            status=store.status,
            active_until=store.active_until,
            admin_note=store.admin_note,
        )
        Subscription.objects.filter(pk=sub.pk).update(created_at=store.created_at)

        outlets = list(Outlet.objects.filter(store=store).order_by("number"))
        store.subscription = sub
        if outlets:
            first = outlets[0]
            store.sale_seq = first.sale_seq
            store.is_active = first.is_active
            if first.address and not store.address:
                store.address = first.address
        store.save()

        for outlet in outlets[1:]:
            new = Store.objects.create(
                subscription=sub,
                owner_id=store.owner_id,
                subdomain=_free_subdomain(Store, Order, store.subdomain, outlet.number),
                name=(outlet.name or store.name)[:60],
                address=outlet.address or store.address,
                phone=store.phone,
                receipt_footer=store.receipt_footer,
                receipt_width=store.receipt_width,
                is_active=outlet.is_active,
                sale_seq=outlet.sale_seq,
                # Kolom lama masih ada sampai langkah 3/3 (dan sebagian wajib diisi).
                package_id=store.package_id,
                package_name=store.package_name,
                base_outlets=0,
                extra_outlets=0,
                status=store.status,
                active_until=store.active_until,
                admin_note="",
            )
            category_map = {
                c.pk: Category.objects.create(store=new, name=c.name, order=c.order).pk
                for c in Category.objects.filter(store=store)
            }
            product_map = {
                p.pk: Product.objects.create(
                    store=new, category_id=category_map.get(p.category_id), name=p.name, code=p.code,
                    price=p.price, is_active=p.is_active,
                ).pk
                for p in Product.objects.filter(store=store)
            }
            Cashier.objects.filter(outlet=outlet).update(store=new)
            sale_ids = list(Sale.objects.filter(outlet=outlet).values_list("pk", flat=True))
            Sale.objects.filter(pk__in=sale_ids).update(store=new)
            for old_id, new_id in product_map.items():
                SaleItem.objects.filter(sale_id__in=sale_ids, product_id=old_id).update(product_id=new_id)


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0002_langganan"),
        ("members", "0009_periode_bebas"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
