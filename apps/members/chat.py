"""Logika chat pelanggan <-> HANS Project (dipakai halaman akun dan panel pengelola).

- Satu ruang obrolan (Conversation) berisi banyak pesan (ChatMessage).
- Admin bisa menutup obrolan (status Selesai). Setelah itu tidak bisa diisi lagi;
  pelanggan membuka obrolan baru, dan obrolan lama tetap ada di riwayat.
- Gambar disimpan di penyimpanan pribadi (tanpa alamat publik), diproses ulang
  sehingga metadata (lokasi, kamera) terbuang.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import F, Q
from django.template.loader import render_to_string
from django.utils import timezone

from .models import ChatMessage, Conversation


class ChatClosed(Exception):
    pass


@transaction.atomic
def post_message(conversation: Conversation, *, sender: str, text: str = "", image=None, reply_to_id=None, admin_user=None) -> ChatMessage:
    conv = Conversation.objects.select_for_update().get(pk=conversation.pk)
    if not conv.is_open:
        raise ChatClosed("Obrolan ini sudah selesai.")
    reply = None
    if reply_to_id:
        reply = ChatMessage.objects.filter(conversation=conv, pk=reply_to_id).first()
    message = ChatMessage(conversation=conv, sender=sender, text=text or "", reply_to=reply, admin_user=admin_user)
    if image is not None:
        message.image.save(image.name, image, save=False)
    message.save()
    fields = {"last_message_at": message.created_at, "last_sender": sender}
    # Pengirim otomatis dianggap sudah membaca obrolannya sendiri.
    fields["admin_read_at" if sender == ChatMessage.SENDER_ADMIN else "member_read_at"] = message.created_at
    Conversation.objects.filter(pk=conv.pk).update(**fields)
    for key, value in fields.items():
        setattr(conversation, key, value)
    return message


def close(conversation: Conversation) -> None:
    Conversation.objects.filter(pk=conversation.pk, status=Conversation.STATUS_OPEN).update(
        status=Conversation.STATUS_CLOSED, closed_at=timezone.now()
    )


def mark_read(conversation: Conversation, *, side: str) -> None:
    field = "admin_read_at" if side == ChatMessage.SENDER_ADMIN else "member_read_at"
    now = timezone.now()
    Conversation.objects.filter(pk=conversation.pk).update(**{field: now})
    setattr(conversation, field, now)


def unread_for_member(member) -> int:
    return (
        Conversation.objects.filter(member=member, last_sender=ChatMessage.SENDER_ADMIN)
        .filter(Q(member_read_at__isnull=True) | Q(member_read_at__lt=F("last_message_at")))
        .count()
    )


def needs_reply_count() -> int:
    """Obrolan terbuka yang pesan terakhirnya dari pelanggan (untuk panel)."""
    return Conversation.objects.filter(status=Conversation.STATUS_OPEN, last_sender=ChatMessage.SENDER_MEMBER).count()


def messages_for(conversation: Conversation, after: int = 0):
    qs = conversation.messages.select_related("reply_to", "conversation__member")
    return qs.filter(pk__gt=after) if after else qs


def render_messages(messages, *, viewer: str, request=None) -> str:
    """Potongan HTML gelembung pesan (untuk JSON). Tanpa pemisah tanggal supaya tidak dobel."""
    messages = list(messages)
    conversation = messages[0].conversation if messages else None
    return render_to_string(
        "components/chat_messages.html",
        {"messages": messages, "viewer": viewer, "conversation": conversation, "show_days": False},
        request=request,
    )


INTRO = (
    "Terima kasih sudah memesan {title} ({code}). Ceritakan kebutuhan Anda di sini: tujuan website/aplikasi, "
    "fitur yang diinginkan, contoh yang Anda suka, dan target selesai. Boleh kirim gambar atau sketsa. "
    "Kami balas di obrolan ini."
)


def order_chat(order) -> Conversation:
    """Obrolan konsultasi untuk satu pesanan: dipakai bila masih terbuka, dibuat baru bila belum ada/sudah selesai.

    Obrolan yang sama tampil di menu Chat pelanggan dan di Chat Pelanggan (panel).
    """
    existing = order.chats.filter(status=Conversation.STATUS_OPEN).order_by("-pk").first()
    if existing:
        return existing
    conversation = Conversation.objects.create(member=order.member, topic="konsultasi", order=order)
    post_message(conversation, sender=ChatMessage.SENDER_ADMIN, text=INTRO.format(title=order.title, code=order.code))
    return conversation
