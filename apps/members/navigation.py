"""Menu area akun pelanggan: menu atas (layar lebar) dan menu bawah (HP).

Dipakai semua halaman /akun/... (termasuk dashboard toko di /akun/toko/...).
"""
from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from . import chat


@dataclass
class AkunTab:
    key: str
    label: str
    icon: str
    url: str
    active: bool = False
    badge: int = 0
    main: bool = False  # tombol tengah yang menonjol di menu bawah


TABS = [
    ("dashboard", "Dashboard", "home", "akun:dashboard"),
    ("pesanan", "Pesanan", "cart", "akun:pesanan-list"),
    ("toko", "Toko", "store", "toko:daftar"),
    ("chat", "Chat", "chat", "akun:chat-list"),
    ("akun", "Akun", "user", "akun:profil"),
]


def akun_tabs(active: str, member) -> list[AkunTab]:
    unread = chat.unread_for_member(member) if member else 0
    return [
        AkunTab(
            key=key, label=label, icon=icon, url=reverse(name), active=key == active,
            badge=unread if key == "chat" else 0, main=key == "toko",
        )
        for key, label, icon, name in TABS
    ]
