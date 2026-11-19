"""Aturan penyimpanan data saat akun pelanggan, pesanan, refund, atau pesan chat dihapus.

- Akun dihapus: pesanan yang TIDAK pernah dibayar ikut dihapus. Pesanan yang sudah
  dibayar (termasuk yang dibatalkan lalu di-refund) beserta bukti bayar dan data
  refund-nya disimpan sampai 10 tahun untuk kewajiban pencatatan pajak; identitas
  pemesan disalin ke pesanan karena akunnya sudah tidak ada. Obrolan ikut terhapus.
- File pribadi (bukti bayar, bukti transfer refund, gambar chat) ikut dihapus
  bersama datanya.
"""
from django.db.models import Q
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from .models import ChatMessage, Member, Order, Refund


def _paid(qs):
    return qs.filter(Q(status__in=Order.PAID_STATUSES) | ~Q(payment_proof=""))


@receiver(pre_delete, sender=Member)
def keep_paid_orders(sender, instance: Member, **kwargs):
    orders = Order.objects.filter(member=instance)
    keep = set(_paid(orders).values_list("pk", flat=True))
    for order in orders.exclude(pk__in=keep):
        order.delete()
    Order.objects.filter(pk__in=keep).update(
        buyer_name=instance.name or instance.display_name,
        buyer_email=instance.email,
        buyer_phone=instance.phone,
        buyer_business=instance.business_name,
    )


def _delete_file(field) -> None:
    if field:
        field.storage.delete(field.name)


@receiver(post_delete, sender=Order)
def delete_proof_file(sender, instance: Order, **kwargs):
    _delete_file(instance.payment_proof)


@receiver(post_delete, sender=Refund)
def delete_refund_proof(sender, instance: Refund, **kwargs):
    _delete_file(instance.transfer_proof)


@receiver(post_delete, sender=ChatMessage)
def delete_chat_image(sender, instance: ChatMessage, **kwargs):
    _delete_file(instance.image)
