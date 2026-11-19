"""Membuat aset gambar teroptimasi dari assets/logo-h.png (alat pengembang).

Hasilnya disimpan di static/img dan ikut disertakan di proyek, jadi server
produksi TIDAK perlu menjalankan skrip ini.

    .venv\\Scripts\\python.exe scripts\\build_assets.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "logo-h.png"
OUT = ROOT / "static" / "img"
FONT = ROOT / "scripts" / "fonts" / "PlusJakartaSans-var.ttf"

CREAM = (255, 251, 245)
INK = (59, 26, 18)
MAROON = (110, 18, 11)
GRADIENT = [(255, 194, 26), (255, 154, 31), (242, 107, 15), (179, 38, 15)]


def load_logo() -> Image.Image:
    img = Image.open(SRC).convert("RGBA")
    return img.crop(img.getbbox())  # buang ruang transparan di tepi


def square(img: Image.Image, pad_ratio: float = 0.0) -> Image.Image:
    side = int(max(img.size) * (1 + pad_ratio * 2))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def resized(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.Resampling.LANCZOS)


def on_background(img: Image.Image, size: int, pad_ratio: float, color=CREAM) -> Image.Image:
    bg = Image.new("RGBA", (size, size), color + (255,))
    inner = int(size * (1 - pad_ratio * 2))
    logo = resized(square(img), inner)
    bg.paste(logo, ((size - inner) // 2, (size - inner) // 2), logo)
    return bg.convert("RGB")


def gradient(width: int, height: int) -> Image.Image:
    """Gradasi diagonal emas -> oranye -> merah seperti logo."""
    base = Image.new("RGB", (width, height))
    px = base.load()
    stops = GRADIENT
    for x in range(width):
        for y in range(0, height, 1):
            t = min(1.0, max(0.0, (x / width) * 0.75 + (y / height) * 0.25))
            seg = min(int(t * (len(stops) - 1)), len(stops) - 2)
            local = t * (len(stops) - 1) - seg
            a, b = stops[seg], stops[seg + 1]
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * local) for i in range(3))
    return base


def font(size: int, weight: str = "ExtraBold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_name(weight)
    except (OSError, ValueError):
        pass
    return f


def og_image(logo: Image.Image) -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)
    # Bidang gradasi miring (meniru pilar logo) di sisi kanan.
    band = gradient(W, H)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(760, 0), (W, 0), (W, H), (640, H)], fill=255)
    img.paste(band, (0, 0), mask)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((760, 60, 1180, 480), fill=(255, 255, 255, 70))
    img.paste(glow.filter(ImageFilter.GaussianBlur(60)), (0, 0), glow.filter(ImageFilter.GaussianBlur(60)))
    lg = resized(square(logo), 400)
    img.paste(lg, (775, 115), lg)
    # Garis aksen tajam
    draw.polygon([(72, 92), (300, 92), (290, 102), (72, 102)], fill=GRADIENT[2])
    draw.text((72, 128), "HANS Project", font=font(44, "ExtraBold"), fill=MAROON)
    draw.text((72, 205), "Aplikasi kasir", font=font(64, "ExtraBold"), fill=INK)
    draw.text((72, 280), "mulai Rp25 ribu", font=font(64, "ExtraBold"), fill=(194, 65, 12))
    draw.text((72, 355), "sebulan", font=font(64, "ExtraBold"), fill=INK)
    draw.text((72, 465), "Catat jualan, hitung uang, cetak struk.", font=font(30, "Medium"), fill=(87, 83, 78))
    draw.text((72, 505), "Cukup pakai HP.", font=font(30, "Medium"), fill=(87, 83, 78))
    draw.text((72, 568), "hansproject.app", font=font(26, "Bold"), fill=MAROON)
    img.save(OUT / "og-image.jpg", "JPEG", quality=86, optimize=True, progressive=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logo = load_logo()
    sq = square(logo)

    for size in (64, 128, 256, 512):
        resized(sq, size).save(OUT / f"logo-h-{size}.webp", "WEBP", quality=88, method=6)
    resized(sq, 128).save(OUT / "logo-h-128.png", "PNG", optimize=True)

    # Favicon: sedikit dipertajam supaya bentuk "H" tetap jelas di 16-32 px.
    fav = resized(sq, 256).filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    fav.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    resized(fav, 32).save(OUT / "favicon-32.png", "PNG", optimize=True)

    on_background(logo, 180, 0.10).save(OUT / "apple-touch-icon.png", "PNG", optimize=True)
    on_background(logo, 192, 0.06).save(OUT / "icon-192.png", "PNG", optimize=True)
    on_background(logo, 512, 0.06).save(OUT / "icon-512.png", "PNG", optimize=True)
    on_background(logo, 512, 0.16).save(OUT / "icon-maskable-512.png", "PNG", optimize=True)
    og_image(logo)

    for f in sorted(OUT.iterdir()):
        if f.suffix in {".webp", ".png", ".ico", ".jpg"}:
            print(f"{f.name:28s} {f.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
