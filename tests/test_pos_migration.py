"""Migrasi pos 0002–0004: data lama (1 toko + beberapa outlet) -> 1 toko = 1 subdomain = 1 kasir.

Penting karena server produksi sudah berisi toko dengan lebih dari satu outlet.
"""
from __future__ import annotations

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

OLD = [("pos", "0001_aplikasi_kasir"), ("members", "0009_periode_bebas"), ("content", "0009_toko_per_subdomain")]


class OutletToStoreMigrationTests(TransactionTestCase):
    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_second_outlet_becomes_its_own_store(self):
        old = self._migrate(OLD)
        Member = old.get_model("members", "Member")
        Store = old.get_model("pos", "Store")
        Outlet = old.get_model("pos", "Outlet")
        Cashier = old.get_model("pos", "Cashier")
        Category = old.get_model("pos", "Category")
        Product = old.get_model("pos", "Product")
        Sale = old.get_model("pos", "Sale")
        SaleItem = old.get_model("pos", "SaleItem")

        owner = Member.objects.create(google_sub="mig-1", email="mig@gmail.com", name="Farhan")
        store = Store.objects.create(
            owner=owner, subdomain="farhan", name="tes", package_name="Tunas", base_outlets=2, extra_outlets=1,
            status="aktif", active_until=date(2026, 12, 19), admin_note="catatan",
        )
        utama = Outlet.objects.create(store=store, number=1, name="Toko utama", sale_seq=3)
        cabang = Outlet.objects.create(store=store, number=2, name="Cabang Pasar", address="Jl. Pasar 1", sale_seq=1)
        Cashier.objects.create(store=store, outlet=utama, username="kol", pin_hash="x")
        Cashier.objects.create(store=store, outlet=cabang, username="kol2", pin_hash="y")
        minuman = Category.objects.create(store=store, name="Minuman", order=10)
        kopi = Product.objects.create(store=store, category=minuman, name="Kopi", price=5000)
        sale_utama = Sale.objects.create(store=store, outlet=utama, cashier_name="kol", number="1-00003", client_key="k-utama-1",
                                         subtotal=5000, total=5000, paid=5000)
        sale_cabang = Sale.objects.create(store=store, outlet=cabang, cashier_name="kol2", number="2-00001", client_key="k-cabang-1",
                                          subtotal=5000, total=5000, paid=5000)
        SaleItem.objects.create(sale=sale_utama, product=kopi, name="Kopi", price=5000, qty=1, line_total=5000)
        SaleItem.objects.create(sale=sale_cabang, product=kopi, name="Kopi", price=5000, qty=1, line_total=5000)

        self._migrate([("pos", "0004_rapikan_toko")])
        from apps.pos.models import Cashier as NewCashier
        from apps.pos.models import Sale as NewSale
        from apps.pos.models import Store as NewStore
        from apps.pos.models import Subscription

        sub = Subscription.objects.get()
        self.assertEqual((sub.owner.email, sub.package_name, sub.base_stores, sub.extra_stores, sub.active_until, sub.admin_note),
                         ("mig@gmail.com", "Tunas", 2, 1, date(2026, 12, 19), "catatan"))
        first = NewStore.objects.get(subdomain="farhan")
        second = NewStore.objects.get(subdomain="farhan-2")
        self.assertEqual((first.subscription, second.subscription), (sub, sub))
        self.assertEqual((first.name, first.sale_seq, second.name, second.address, second.sale_seq),
                         ("tes", 3, "Cabang Pasar", "Jl. Pasar 1", 1))
        # Satu akun kasir per toko, tetap dengan PIN lamanya.
        self.assertEqual((NewCashier.objects.get(store=first).username, NewCashier.objects.get(store=second).username), ("kol", "kol2"))
        # Transaksi ikut toko masing-masing; barang tersalin & tertaut ke salinan.
        self.assertEqual(NewSale.objects.get(client_key="k-cabang-1").store, second)
        self.assertEqual(NewSale.objects.get(client_key="k-utama-1").store, first)
        self.assertEqual(list(second.products.values_list("name", "category__name")), [("Kopi", "Minuman")])
        item = NewSale.objects.get(client_key="k-cabang-1").items.get()
        self.assertEqual(item.product.store, second)
        self.assertEqual(NewSale.objects.get(client_key="k-utama-1").items.get().product.store, first)
        self.assertEqual(sub.stores_used, 2)
