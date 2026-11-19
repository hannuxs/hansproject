"""Chat pelanggan di panel: daftar obrolan, membalas (teks/gambar/balas pesan), dan menutup obrolan."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.content import audit
from apps.content.models import AuditLog
from apps.members import chat, files
from apps.members.forms import ChatMessageForm
from apps.members.models import ChatMessage, Conversation, Refund

from ..mixins import PanelAccessMixin

log = logging.getLogger("hans.security")

FILTERS = [("perlu-dibalas", "Perlu dibalas"), ("terbuka", "Terbuka"), ("selesai", "Selesai"), ("semua", "Semua")]


class ChatListView(PanelAccessMixin, TemplateView):
    template_name = "panel/chat/list.html"
    page_title = "Chat Pelanggan"
    nav_active = "chat"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current = self.request.GET.get("filter", "perlu-dibalas")
        current = current if current in dict(FILTERS) else "perlu-dibalas"
        qs = Conversation.objects.select_related("member", "order")
        if current == "perlu-dibalas":
            qs = qs.filter(status=Conversation.STATUS_OPEN, last_sender=ChatMessage.SENDER_MEMBER)
        elif current in (Conversation.STATUS_OPEN, Conversation.STATUS_CLOSED):
            qs = qs.filter(status=current)
        ctx.update(
            filters=FILTERS,
            current=current,
            page=Paginator(qs, 40).get_page(self.request.GET.get("hal")),
            needs_reply=chat.needs_reply_count(),
        )
        return ctx


class ChatDetailView(PanelAccessMixin, TemplateView):
    template_name = "panel/chat/detail.html"
    nav_active = "chat"

    def get_conversation(self) -> Conversation:
        return get_object_or_404(Conversation.objects.select_related("member"), pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        conversation = self.get_conversation()
        chat.mark_read(conversation, side=ChatMessage.SENDER_ADMIN)
        return self.render_to_response(self.context(conversation, ChatMessageForm()))

    def context(self, conversation, form):
        items = list(chat.messages_for(conversation))
        member = conversation.member
        return self.get_context_data(
            conversation=conversation,
            chat_messages=items,
            last_id=items[-1].pk if items else 0,
            form=form,
            page_title=f"Chat #{conversation.pk} — {member.display_name}",
            other_chats=member.chats.exclude(pk=conversation.pk)[:10],
            orders=member.orders.all()[:5],
            refunds=Refund.objects.filter(order__member=member)[:5],
        )

    def post(self, request, *args, **kwargs):
        conversation = self.get_conversation()
        wants_json = request.headers.get("Accept", "").startswith("application/json")
        if request.POST.get("aksi") == "tutup":
            chat.close(conversation)
            audit.record(request, AuditLog.ACTION_UPDATE, conversation, target_type="obrolan", detail="Obrolan ditutup (Selesai)")
            messages.success(request, "Obrolan ditutup. Pelanggan tidak bisa membalas lagi di obrolan ini.")
            return redirect("panel:chat", pk=conversation.pk)
        form = ChatMessageForm(request.POST, request.FILES)
        if not conversation.is_open:
            error = "Obrolan ini sudah selesai."
        elif form.is_valid():
            message = chat.post_message(
                conversation, sender=ChatMessage.SENDER_ADMIN, text=form.cleaned_data["text"],
                image=form.cleaned_data["image"], reply_to_id=form.cleaned_data.get("reply_to"), admin_user=request.user,
            )
            if wants_json:
                return JsonResponse({"ok": True, "last_id": message.pk, "html": chat.render_messages([message], viewer="admin", request=request)})
            return redirect(reverse("panel:chat", args=[conversation.pk]) + f"#pesan-{message.pk}")
        else:
            error = " ".join(e for errors in form.errors.values() for e in errors)
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return self.render_to_response(self.context(conversation, form), status=400)


class ChatPollView(PanelAccessMixin, View):
    def get(self, request, pk: int):
        conversation = get_object_or_404(Conversation, pk=pk)
        try:
            after = max(0, int(request.GET.get("after", "0")))
        except ValueError:
            after = 0
        items = list(chat.messages_for(conversation, after))
        if items:
            chat.mark_read(conversation, side=ChatMessage.SENDER_ADMIN)
        return JsonResponse({
            "open": conversation.is_open,
            "last_id": items[-1].pk if items else after,
            "html": chat.render_messages(items, viewer="admin", request=request) if items else "",
        })


class ChatImageView(PanelAccessMixin, View):
    def get(self, request, msg: int):
        message = get_object_or_404(ChatMessage, pk=msg)
        if not message.image:
            raise Http404
        return files.serve_private(message.image)


class RefundProofView(PanelAccessMixin, View):
    def get(self, request, pk: int):
        refund = get_object_or_404(Refund, pk=pk)
        if not refund.transfer_proof:
            raise Http404
        return files.serve_private(refund.transfer_proof)
