"""Tag & filter template yang dipakai ulang di seluruh situs dan panel.

Dimuat otomatis (builtins), jadi tidak perlu ``{% load ui %}``.
"""
from __future__ import annotations

import json

from django import template
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core import formatting, textformat

register = template.Library()


@register.filter
def rupiah(value):
    return formatting.rupiah(value)


@register.filter
def rupiah_short(value):
    return formatting.rupiah_short(value)


@register.filter
def thousands(value):
    return formatting.thousands(value or 0)


@register.filter
def md(value):
    """Ubah teks berformat sederhana menjadi HTML aman (lihat core/textformat.py)."""
    return textformat.render(value)


@register.filter
def md_plain(value):
    return textformat.plain(value)


_JSON_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.filter
def jsonld(value):
    """JSON untuk <script type="application/ld+json">, aman dari penutupan tag </script>."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":")).translate(_JSON_ESCAPES)
    return mark_safe(text)  # nosec B308 B703 - karakter < > & sudah di-escape


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key, "")
    except AttributeError:
        return ""


@register.simple_tag
def icon(name: str, css: str = "", label: str = ""):
    """Ikon SVG dari sprite ``static/img/icons.svg``.

    ``{% icon "check" %}`` atau ``{% icon "instagram" "icon-lg" label="Instagram" %}``
    """
    href = f"{static('img/icons.svg')}#i-{name}"
    if label:
        return format_html(
            '<svg class="icon {}" role="img" aria-label="{}"><use href="{}"></use></svg>', css, label, href
        )
    return format_html('<svg class="icon {}" aria-hidden="true" focusable="false"><use href="{}"></use></svg>', css, href)
