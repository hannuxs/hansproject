"""Login dengan Google (OpenID Connect, "authorization code flow" + PKCE).

Alurnya:
1. ``start()`` membuat ``state`` (anti-CSRF), ``nonce`` (anti-replay), dan PKCE,
   lalu mengarahkan pengunjung ke halaman login Google.
2. Google mengembalikan pengunjung ke ``/akun/google/callback/`` membawa ``code``.
3. ``exchange_code()`` menukar ``code`` dengan ``id_token`` langsung ke server
   Google lewat HTTPS (sertifikat diperiksa) memakai Client Secret.
4. ``validate_claims()`` memeriksa penerbit, tujuan (Client ID), masa berlaku,
   nonce, dan bahwa email sudah diverifikasi Google.

Karena ``id_token`` diterima langsung dari server Google lewat HTTPS (bukan
lewat browser), tanda tangannya tidak perlu diperiksa ulang (OpenID Connect
Core 3.1.3.7 butir 6; juga dianjurkan dokumentasi Google). Jadi tidak perlu
library tambahan.

Google hanya memastikan identitas. Data pelanggan disimpan di database sendiri.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 - alamat, bukan password
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
SCOPES = "openid email profile"
CLOCK_SKEW = 120  # detik toleransi selisih jam server
TIMEOUT = 10


class GoogleLoginError(Exception):
    """Login gagal. Pesannya aman untuk dicatat di log (tanpa token/rahasia)."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return settings.GOOGLE_REDIRECT_URI or settings.SITE_URL + reverse("akun:google-callback")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def start() -> tuple[str, dict]:
    """Kembalikan (alamat login Google, data yang wajib disimpan sampai callback)."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
        "include_granted_scopes": "true",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}", {"state": state, "nonce": nonce, "verifier": verifier}


def state_matches(expected: str, received: str) -> bool:
    return bool(expected and received) and hmac.compare_digest(expected.encode(), received.encode())


def _post_token(data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode("ascii")
    request = urllib.request.Request(  # noqa: S310 - alamat tetap https Google
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=context) as response:  # nosec B310
            return json.loads(response.read(65536))
    except urllib.error.HTTPError as exc:
        # Isi balasan error tidak dicatat (bisa memuat data permintaan).
        raise GoogleLoginError(f"Google menolak penukaran kode (HTTP {exc.code}).") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GoogleLoginError(f"Tidak bisa menghubungi Google: {type(exc).__name__}.") from None
    except ValueError:
        raise GoogleLoginError("Balasan Google bukan JSON yang valid.") from None


def _decode_payload(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as exc:
        raise GoogleLoginError("id_token tidak bisa dibaca.") from exc


def exchange_code(code: str, verifier: str) -> dict:
    """Tukar ``code`` dengan klaim identitas (isi id_token). Dipanggil dari callback."""
    data = _post_token(
        {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
    )
    id_token = data.get("id_token")
    if not isinstance(id_token, str):
        raise GoogleLoginError("Balasan Google tidak berisi id_token.")
    return _decode_payload(id_token)


def validate_claims(claims: dict, nonce: str, now: float | None = None) -> GoogleIdentity:
    now = time.time() if now is None else now
    if claims.get("iss") not in ISSUERS:
        raise GoogleLoginError("Penerbit token bukan Google.")
    aud = claims.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    if settings.GOOGLE_CLIENT_ID not in audiences:
        raise GoogleLoginError("Token bukan untuk aplikasi ini.")
    try:
        exp, iat = float(claims["exp"]), float(claims.get("iat", now))
    except (KeyError, TypeError, ValueError) as exc:
        raise GoogleLoginError("Token tanpa masa berlaku.") from exc
    if exp < now - CLOCK_SKEW or iat > now + CLOCK_SKEW:
        raise GoogleLoginError("Token sudah kedaluwarsa atau waktunya tidak wajar.")
    if not state_matches(nonce, str(claims.get("nonce", ""))):
        raise GoogleLoginError("Nonce tidak cocok.")
    sub, email = str(claims.get("sub") or ""), str(claims.get("email") or "").strip().lower()
    if not sub or len(sub) > 255:
        raise GoogleLoginError("Token tanpa ID akun.")
    if not email or claims.get("email_verified") not in (True, "true"):
        raise GoogleLoginError("Email akun Google belum terverifikasi.")
    name = str(claims.get("name") or "").strip()[:120]
    return GoogleIdentity(sub=sub, email=email[:254], name=name)
