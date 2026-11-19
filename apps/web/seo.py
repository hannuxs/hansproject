"""Structured data schema.org (Organization, WebSite, Product/Offer, Service, FAQPage)."""
from __future__ import annotations

from django.conf import settings
from django.templatetags.static import static

from apps.content.services import Snapshot
from apps.core.textformat import plain


def structured_data(snap: Snapshot) -> list[dict]:
    site_url = settings.SITE_URL
    org_id = f"{site_url}/#organisasi"
    same_as = [url for _, _, url in snap.settings.social_links]
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": org_id,
        "name": "HANS Project",
        "url": f"{site_url}/",
        "logo": f"{site_url}{static('img/icon-512.png')}",
    }
    if same_as:
        org["sameAs"] = same_as
    if snap.settings.email:
        org["email"] = snap.settings.email

    data: list[dict] = [
        org,
        {"@context": "https://schema.org", "@type": "WebSite", "name": "HANS Project", "url": f"{site_url}/", "inLanguage": "id"},
    ]
    for pkg in snap.pos_packages:
        data.append({
            "@context": "https://schema.org",
            "@type": "Product",
            "name": f"Aplikasi Kasir HANS Project — Paket {pkg.name}",
            "description": f"Aplikasi kasir online langganan bulanan. Cocok untuk: {pkg.tagline}",
            "brand": {"@id": org_id},
            "offers": {
                "@type": "Offer",
                "price": str(pkg.price),
                "priceCurrency": "IDR",
                "url": f"{site_url}/#harga",
                "availability": "https://schema.org/InStock",
                "priceSpecification": {
                    "@type": "UnitPriceSpecification",
                    "price": str(pkg.price),
                    "priceCurrency": "IDR",
                    "unitCode": "MON",
                },
            },
        })
    for pkg in snap.service_packages:
        data.append({
            "@context": "https://schema.org",
            "@type": "Service",
            "name": f"Jasa Pembuatan Website & Aplikasi — Paket {pkg.name}",
            "serviceType": "Pembuatan website dan aplikasi Android/iOS",
            "provider": {"@id": org_id},
            "areaServed": {"@type": "Country", "name": "Indonesia"},
            "offers": {"@type": "Offer", "price": str(pkg.price), "priceCurrency": "IDR", "url": f"{site_url}/#jasa"},
        })
    if snap.faqs:
        data.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f.question, "acceptedAnswer": {"@type": "Answer", "text": plain(f.answer)}}
                for f in snap.faqs
            ],
        })
    return data
