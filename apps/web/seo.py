"""Structured data schema.org (Organization, WebSite, Product/Offer, Service, FAQPage).

Halaman utama: organisasi + website + FAQ umum. Halaman solusi: paket solusi itu + FAQ-nya.
Paket yang harganya belum ditentukan (Rp0) tidak diberi Offer (harga palsu dilarang Google).
"""
from __future__ import annotations

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from apps.content.services import Snapshot
from apps.core.textformat import plain


def _offer(pkg, url: str, monthly: bool = True) -> dict:
    offer = {"@type": "Offer", "price": str(pkg.price), "priceCurrency": "IDR", "url": url,
             "availability": "https://schema.org/InStock"}
    if monthly:
        offer["priceSpecification"] = {
            "@type": "UnitPriceSpecification", "price": str(pkg.price), "priceCurrency": "IDR", "unitCode": "MON",
        }
    return offer


def structured_data(snap: Snapshot, solution: str = "") -> list[dict]:
    site_url = settings.SITE_URL
    org_id = f"{site_url}/#organisasi"
    same_as = [url for _, _, url in snap.settings.social_links]
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": org_id,
        "name": "HANS Project",
        "description": "Penyedia solusi digital: aplikasi kasir, Sistem Informasi Manajemen (SIM), serta jasa website & aplikasi.",
        "url": f"{site_url}/",
        "logo": f"{site_url}{static('img/icon-512.png')}",
    }
    if same_as:
        org["sameAs"] = same_as
    if snap.settings.email:
        org["email"] = snap.settings.email

    data: list[dict] = [org]
    if not solution:
        data.append({"@context": "https://schema.org", "@type": "WebSite", "name": "HANS Project", "url": f"{site_url}/", "inLanguage": "id"})

    if solution == "kasir":
        url = f"{site_url}{reverse('web:kasir')}#harga"
        for pkg in snap.pos_packages:
            data.append({
                "@context": "https://schema.org", "@type": "Product",
                "name": f"Aplikasi Kasir HANS Project — Paket {pkg.name}",
                "description": f"Aplikasi kasir online langganan bulanan. Cocok untuk: {pkg.tagline}",
                "brand": {"@id": org_id}, "offers": _offer(pkg, url),
            })
    elif solution == "sim":
        url = f"{site_url}{reverse('web:sim')}#harga"
        for pkg in snap.sim_packages:
            item = {
                "@context": "https://schema.org", "@type": "Product",
                "name": f"Sistem Informasi Manajemen (SIM) HANS Project — Paket {pkg.name}",
                "description": f"SIM online: data dari foto dokumen, surat online, cetak dari mana saja. Cocok untuk: {pkg.tagline}",
                "brand": {"@id": org_id},
            }
            if pkg.is_priced:
                item["offers"] = _offer(pkg, url)
            data.append(item)
    elif solution == "jasa":
        url = f"{site_url}{reverse('web:jasa')}#jasa"
        for pkg in snap.service_packages:
            data.append({
                "@context": "https://schema.org", "@type": "Service",
                "name": f"Jasa Pembuatan Website & Aplikasi — Paket {pkg.name}",
                "serviceType": "Pembuatan website dan aplikasi Android/iOS",
                "provider": {"@id": org_id},
                "areaServed": {"@type": "Country", "name": "Indonesia"},
                "offers": _offer(pkg, url, monthly=False),
            })

    faqs = snap.faq_topics.get(solution or "umum", [])
    if faqs:
        data.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f.question, "acceptedAnswer": {"@type": "Answer", "text": plain(f.answer)}}
                for f in faqs
            ],
        })
    return data
