"""CRUD generik untuk panel pengelola.

Setiap jenis data cukup didaftarkan sebagai ``Section`` di ``registry.py``.
Daftar, tambah, ubah, hapus, dan geser urutan otomatis tersedia, lengkap
dengan pencatatan riwayat perubahan.

Contoh:

    faq = Section(key="faq", model=Faq, form_class=FaqForm, title="FAQ",
                  singular="pertanyaan", icon="help",
                  columns=[Column("question", "Pertanyaan"), Column("is_active", "Tampil", "bool")])
    urlpatterns += faq.urls()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

from django.contrib import messages
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.views.generic import TemplateView

from apps.content import audit
from apps.content.models import AuditLog
from apps.core import formatting
from apps.core.templatetags.ui import icon

from .mixins import PanelAccessMixin


@dataclass
class Column:
    attr: str
    label: str
    kind: str = "text"  # text | bool | money | muted

    def render(self, obj: Model):
        value: Any = obj
        for part in self.attr.split("."):
            value = getattr(value, part, "")
            if callable(value):
                value = value()
        if isinstance(value, datetime):
            value = date_format(localtime(value), "j M Y, H:i")
        elif isinstance(value, date):
            value = date_format(value, "j M Y")
        if self.kind == "bool":
            return icon("check", "icon-ok", label="Ya") if value else icon("x", "icon-off", label="Tidak")
        if self.kind == "money":
            return formatting.rupiah(value) if value not in (None, "") else "–"
        text = str(value) if value not in (None, "") else "–"
        if len(text) > 90:
            text = text[:87] + "…"
        if self.kind == "muted":
            return format_html('<span class="muted">{}</span>', text)
        return text


@dataclass
class InlineSpec:
    """Tabel isian tambahan di bawah form utama (formset)."""

    prefix: str
    title: str
    formset_class: Any
    help: str = ""
    inline: bool = True  # True: inlineformset (terikat ke objek). False: modelformset biasa.
    queryset: Callable[[], QuerySet] | None = None

    def build(self, request, instance):
        data = request.POST if request.method == "POST" else None
        files = request.FILES if request.method == "POST" else None
        if self.inline:
            return self.formset_class(data, files, instance=instance, prefix=self.prefix)
        return self.formset_class(data, files, queryset=self.queryset(), prefix=self.prefix)


@dataclass
class Section:
    key: str
    model: type[Model]
    form_class: Any
    title: str
    singular: str
    icon: str
    columns: list[Column]
    description: str = ""
    inlines: list[InlineSpec] = field(default_factory=list)
    fieldsets: list[tuple[str, list[str]]] | None = None
    can_create: bool = True
    can_delete: bool = True
    orderable: bool = True
    singleton: bool = False
    nav_group: str = "Konten"
    queryset: Callable[[], QuerySet] | None = None
    # Template tambahan di atas form ubah (mis. data pelanggan & bukti bayar). Menerima ``object``.
    detail_template: str = ""

    def get_queryset(self) -> QuerySet:
        return self.queryset() if self.queryset else self.model.objects.all()

    def url_name(self, action: str) -> str:
        return f"panel:{self.key}-{action}"

    def urls(self) -> list:
        if self.singleton:
            return [path(f"{self.key}/", SectionFormView.as_view(section=self), name=f"{self.key}")]
        patterns = [
            path(f"{self.key}/", SectionListView.as_view(section=self), name=f"{self.key}-list"),
            path(f"{self.key}/<int:pk>/ubah/", SectionFormView.as_view(section=self), name=f"{self.key}-update"),
        ]
        if self.can_create:
            patterns.append(path(f"{self.key}/baru/", SectionFormView.as_view(section=self), name=f"{self.key}-create"))
        if self.can_delete:
            patterns.append(path(f"{self.key}/<int:pk>/hapus/", SectionDeleteView.as_view(section=self), name=f"{self.key}-delete"))
        if self.orderable:
            patterns.append(
                path(f"{self.key}/<int:pk>/geser/<str:direction>/", SectionMoveView.as_view(section=self), name=f"{self.key}-move")
            )
        return patterns

    @property
    def nav_url(self) -> str:
        return reverse(f"panel:{self.key}" if self.singleton else self.url_name("list"))


class SectionMixin(PanelAccessMixin):
    section: Section | None = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = self.section
        return ctx

    @property
    def nav_active(self):  # type: ignore[override]
        return self.section.key


class SectionListView(SectionMixin, TemplateView):
    template_name = "panel/crud/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        s = self.section
        objects = list(s.get_queryset())
        ctx["page_title"] = s.title
        ctx["create_url"] = reverse(s.url_name("create")) if s.can_create else ""
        ctx["rows"] = [
            {
                "obj": obj,
                "cells": [(col.label, col.render(obj)) for col in s.columns],
                "update_url": reverse(s.url_name("update"), args=[obj.pk]),
                "delete_url": reverse(s.url_name("delete"), args=[obj.pk]) if s.can_delete else "",
                "up_url": reverse(s.url_name("move"), args=[obj.pk, "naik"]) if s.orderable else "",
                "down_url": reverse(s.url_name("move"), args=[obj.pk, "turun"]) if s.orderable else "",
            }
            for obj in objects
        ]
        return ctx


class SectionFormView(SectionMixin, TemplateView):
    template_name = "panel/crud/form.html"

    def get_object(self):
        if self.section.singleton:
            return self.section.model.load()
        pk = self.kwargs.get("pk")
        if pk is None:
            if not self.section.can_create:
                raise Http404
            return None
        return get_object_or_404(self.section.get_queryset(), pk=pk)

    def build_forms(self, obj):
        request = self.request
        if request.method == "POST":
            form = self.section.form_class(request.POST, request.FILES, instance=obj)
        else:
            form = self.section.form_class(instance=obj)
        formsets = [(spec, spec.build(request, obj or self.section.model())) for spec in self.section.inlines]
        return form, formsets

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        form, formsets = self.build_forms(obj)
        return self.render_to_response(self.get_context_data(form=form, formsets=formsets, object=obj))

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        is_new = obj is None
        form, formsets = self.build_forms(obj)
        if form.is_valid() and all(fs.is_valid() for _, fs in formsets):
            with transaction.atomic():
                saved = form.save()
                changes = [audit.changed_fields_detail(form)]
                for spec, fs in formsets:
                    if spec.inline:
                        fs.instance = saved
                    fs.save()
                    if fs.has_changed():
                        changes.append(f"{spec.title} diubah")
                audit.record(
                    request,
                    AuditLog.ACTION_CREATE if is_new else AuditLog.ACTION_UPDATE,
                    saved,
                    target_type=self.section.singular,
                    detail="; ".join(c for c in changes if c),
                )
            messages.success(request, f"{self.section.singular.capitalize()} berhasil disimpan.")
            if self.section.singleton:
                return redirect(f"panel:{self.section.key}")
            if "simpan_lanjut" in request.POST:
                return redirect(self.section.url_name("update"), pk=saved.pk)
            return redirect(self.section.url_name("list"))
        messages.error(request, "Ada isian yang perlu diperbaiki. Lihat tulisan merah di bawah.")
        return self.render_to_response(self.get_context_data(form=form, formsets=formsets, object=obj), status=400)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj, form = kwargs.get("object"), kwargs.get("form")
        if self.section.singleton:
            ctx["page_title"] = self.section.title
        else:
            ctx["page_title"] = f"Ubah {self.section.singular}" if obj else f"Tambah {self.section.singular}"
            ctx["list_url"] = reverse(self.section.url_name("list"))
        if form is not None and self.section.fieldsets:
            ctx["fieldsets"] = [(title, [form[name] for name in names if name in form.fields]) for title, names in self.section.fieldsets]
        return ctx


class SectionDeleteView(SectionMixin, TemplateView):
    template_name = "panel/crud/delete.html"

    def get_object(self):
        return get_object_or_404(self.section.get_queryset(), pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        return self.render_to_response(
            self.get_context_data(
                object=obj,
                page_title=f"Hapus {self.section.singular}",
                list_url=reverse(self.section.url_name("list")),
            )
        )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        label = str(obj)
        with transaction.atomic():
            obj.delete()
            audit.record(request, AuditLog.ACTION_DELETE, target_type=self.section.singular, target_repr=label)
        messages.success(request, f"{self.section.singular.capitalize()} '{label}' sudah dihapus.")
        return redirect(self.section.url_name("list"))


class SectionMoveView(SectionMixin, TemplateView):
    """Geser urutan satu baris ke atas/bawah lalu rapikan nomor urut (10, 20, 30, ...)."""

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])

    def post(self, request, *args, **kwargs):
        direction = kwargs["direction"]
        if direction not in ("naik", "turun"):
            raise Http404
        items = list(self.section.get_queryset())
        index = next((i for i, o in enumerate(items) if o.pk == kwargs["pk"]), None)
        if index is None:
            raise Http404
        swap = index - 1 if direction == "naik" else index + 1
        if 0 <= swap < len(items):
            items[index], items[swap] = items[swap], items[index]
            with transaction.atomic():
                for n, item in enumerate(items, start=1):
                    if item.order != n * 10:
                        item.order = n * 10
                        item.save(update_fields=["order"])
        return redirect(self.section.url_name("list"))
