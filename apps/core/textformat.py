"""Format teks sederhana yang aman untuk isi dari panel pengelola.

Pemilik cukup menulis teks biasa. Format yang didukung:

    ## Judul               -> sub-judul
    ### Judul kecil        -> sub-judul kecil
    - poin                 -> daftar berbutir
    1. poin                -> daftar bernomor
    **tebal**              -> huruf tebal
    [teks](https://...)    -> tautan (https, mailto, atau alamat di situs ini)
    baris kosong           -> paragraf baru

Semua teks di-escape lebih dulu, lalu hasil akhirnya disaring lagi dengan
daftar tag yang diizinkan (allowlist) memakai ``nh3``. Jadi HTML/script yang
diketik di panel tidak akan pernah dijalankan.
"""
from __future__ import annotations

import html
import re

import nh3
from django.utils.safestring import SafeString, mark_safe

ALLOWED_TAGS = {"p", "br", "strong", "ul", "ol", "li", "h2", "h3", "a", "code"}
ALLOWED_ATTRIBUTES = {"a": {"href"}}

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(((?:https://|mailto:|/)[^\s)]*)\)")
_UL = re.compile(r"^\s*[-*•]\s+(.*)$")
_OL = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def _inline(text: str) -> str:
    out = html.escape(text, quote=True)
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _LINK.sub(r'<a href="\2">\1</a>', out)
    return out


def render(text: str | None) -> SafeString:
    if not text:
        return mark_safe("")  # nosec B308 B703 - string kosong
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_tag:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{list_tag}>")
            items.clear()
            list_tag = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        if line.startswith("### ") or line.startswith("## "):
            flush_paragraph()
            flush_list()
            level = "h3" if line.startswith("### ") else "h2"
            blocks.append(f"<{level}>{_inline(line.lstrip('#').strip())}</{level}>")
            continue
        ul, ol = _UL.match(line), _OL.match(line)
        if ul or ol:
            flush_paragraph()
            tag = "ul" if ul else "ol"
            if list_tag and list_tag != tag:
                flush_list()
            list_tag = tag
            items.append(_inline((ul or ol).group(1)))
            continue
        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    cleaned = nh3.clean(
        "".join(blocks),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"https", "mailto"},
        link_rel="noopener noreferrer",
    )
    return mark_safe(cleaned)  # nosec B308 B703 - sudah di-escape & disaring allowlist nh3


def plain(text: str | None) -> str:
    """Versi teks polos (untuk meta description / structured data)."""
    if not text:
        return ""
    stripped = nh3.clean(str(render(text)), tags=set())
    return html.unescape(re.sub(r"\s+", " ", stripped)).strip()
