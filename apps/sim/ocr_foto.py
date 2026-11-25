"""Pembaca FOTO KK/KTP: PaddleOCR PP-OCRv4 (lewat RapidOCR + ONNX Runtime) dengan OpenCV.

Jauh lebih tahan daripada Tesseract untuk foto HP: fotokopi, cahaya tidak rata, sedikit buram,
miring/perspektif, bahkan foto yang diputar 90°. Semua berjalan di server sendiri (CPU cukup;
model ikut terpasang bersama paket, tidak ada data yang dikirim ke luar).

Alur KK:
1. Garis tabel dicari dengan OpenCV (morfologi), sudut luar tabel -> perspektif diluruskan
   dan halaman diputar sehingga tabel mendatar (lanskap).
2. Seluruh halaman dibaca sekali (deteksi + pengenalan teks). Bila tulisan "KARTU KELUARGA"/label kepala KK
   ada di bawah tabel, halaman terbalik -> posisi teks diputar 180°.
3. Garis baris & kolom tabel dideteksi (apps.sim.ocr) dan setiap teks dipasangkan ke selnya.
4. Spasi antarkata yang hilang ("HAIRULFITRI") dipulihkan dari kata-kata lain di KK yang sama
   dan daftar kata nama/tempat yang umum; isian baku dicocokkan tanpa memperhitungkan spasi.

Bila paket tidak terpasang (``available()`` False), apps.sim.ocr memakai Tesseract.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata
from dataclasses import dataclass

from PIL import Image, ImageOps

from . import ocr as base

log = logging.getLogger("hans")

_ENGINE = None
_ENGINE_LOCK = threading.Lock()
MAX_SIDE = 3200
MIN_SIDE = 2600


def available() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


_DEVICE = "cpu"


def _cuda_ready() -> bool:
    """CUDA tersedia bila paket onnxruntime-gpu terpasang (requirements/ocr-gpu.txt) dan driver NVIDIA ada."""
    try:
        import onnxruntime as ort
    except (ImportError, OSError):
        return False
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return False
    preload = getattr(ort, "preload_dlls", None)  # muat CUDA/cuDNN dari paket nvidia-* di venv
    if preload:
        try:
            preload()
        except (OSError, RuntimeError):
            return False
    return True


def _engine():
    """Mesin PaddleOCR (sekali per proses). OCR_DEVICE di .env: auto (GPU bila ada) | cpu | cuda."""
    global _ENGINE, _DEVICE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            import numpy as np
            from django.conf import settings
            from rapidocr_onnxruntime import RapidOCR

            wanted = (getattr(settings, "OCR_DEVICE", "") or "auto").lower()
            if wanted in ("auto", "cuda") and _cuda_ready():
                try:
                    engine = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
                    engine(np.full((64, 256, 3), 255, np.uint8))  # pemanasan
                    # ONNX Runtime diam-diam pindah ke CPU bila CUDA/cuDNN gagal: pastikan GPU benar-benar dipakai.
                    session = engine.text_det.infer.session
                    on_gpu = session.get_providers()[:1] == ["CUDAExecutionProvider"]
                    _ENGINE, _DEVICE = engine, ("cuda" if on_gpu else "cpu")
                    if not on_gpu:
                        log.warning("PaddleOCR: CUDA tidak aktif (driver/cuDNN), memakai CPU.")
                except Exception as exc:  # noqa: BLE001 - driver/VRAM bermasalah: jangan gagal, pakai CPU
                    log.warning("PaddleOCR GPU tidak bisa dipakai (%s), memakai CPU.", type(exc).__name__)
            if _ENGINE is None:
                _ENGINE, _DEVICE = RapidOCR(), "cpu"
            log.info("Pembaca foto KK/KTP memakai %s.", _DEVICE.upper())
        return _ENGINE


def device() -> str:
    """"cuda" atau "cpu" (setelah mesin dimuat)."""
    _engine()
    return _DEVICE


@dataclass
class Box:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def w(self) -> float:
        return self.x1 - self.x0


def _ocr(img, *, use_cls: bool = True) -> list[Box]:
    result, _ = _engine()(img, use_cls=use_cls)
    boxes = []
    for poly, text, score in result or []:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        text = unicodedata.normalize("NFKC", str(text)).strip()
        if text:
            boxes.append(Box(text, min(xs), min(ys), max(xs), max(ys), float(score)))
    return boxes


def _load(path: str):
    import numpy as np

    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
        elif max(im.size) < MIN_SIDE:  # hasil scan kecil: huruf tabel KK terlalu kecil untuk dideteksi
            factor = MIN_SIDE / max(im.size)
            im = im.resize((int(im.width * factor), int(im.height * factor)), Image.Resampling.LANCZOS)
        return np.asarray(im)[:, :, ::-1].copy()  # BGR untuk OpenCV


# ---------------------------------------------------------------------------
# Meluruskan halaman
# ---------------------------------------------------------------------------
def _order(pts):
    import numpy as np

    s = pts.sum(axis=1)
    d = pts[:, 1] - pts[:, 0]
    return np.float32([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


def _table_quad(img, divisor: int = 30, method: str = "silang"):
    """Empat sudut luar tabel KK (gabungan tabel atas & bawah), atau None.

    ``method``: "silang" = selubung titik persilangan garis (tahan tepi kertas/meja yang kontras);
    "kontur" = selubung jaring garis besar (tahan garis yang agak miring karena perspektif).
    """
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    # divisor kecil = kernel panjang (tahan huruf); besar = kernel pendek (tahan garis miring karena perspektif).
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, w // divisor), 1)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, h // divisor))))
    if method == "kontur":
        grid = cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((5, 5), np.uint8), iterations=2)
        contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        big = [c for c in contours if cv2.contourArea(c) > 0.02 * w * h]
        return _quad_from_hull(cv2.convexHull(np.vstack(big)), w, h) if big else None
    # Titik persilangan garis mendatar & tegak: tabel punya ratusan, tepi kertas/meja hanya di sudutnya.
    kernel = np.ones((7, 7), np.uint8)
    junctions = cv2.bitwise_and(cv2.dilate(horiz, kernel), cv2.dilate(vert, kernel))
    count, _, _, centroids = cv2.connectedComponentsWithStats(junctions)
    points = centroids[1:]
    if count < 20:
        return None
    radius = 0.08 * min(w, h)
    dist = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    dense = points[(dist < radius).sum(axis=1) >= 4]  # titik terpencil (sudut kertas) dibuang
    if len(dense) < 20:
        return None
    return _quad_from_hull(cv2.convexHull(dense.astype(np.float32)), w, h)


def _quad_from_hull(hull, w: int, h: int):
    import cv2

    peri = cv2.arcLength(hull, True)
    quad = None
    for eps in (0.01, 0.02, 0.03, 0.05):
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) == 4:
            quad = approx.reshape(4, 2).astype("float32")
            break
    if quad is None:
        quad = cv2.boxPoints(cv2.minAreaRect(hull)).astype("float32")
    if cv2.contourArea(quad) < 0.08 * w * h:
        return None
    return _order(quad)


def _rectify(img, quad):
    """Luruskan perspektif sehingga tabel menjadi persegi panjang mendatar, beri ruang untuk kepala & kaki KK."""
    import cv2
    import numpy as np

    tl, tr, br, bl = quad
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    if height > width:  # foto tegak (KK diputar 90°): sisi panjang tabel dijadikan mendatar
        tl, tr, br, bl = tr, br, bl, tl
        width, height = height, width
    W, H = int(width), int(height)
    px, pt, pb = int(W * 0.03), int(H * 0.45), int(H * 0.55)
    dst = np.float32([[px, pt], [px + W, pt], [px + W, pt + H], [px, pt + H]])
    matrix = cv2.getPerspectiveTransform(np.float32([tl, tr, br, bl]), dst)
    out = cv2.warpPerspective(img, matrix, (W + 2 * px, pt + H + pb), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return out, (pt, pt + H, px, px + W)  # batas tabel: atas, bawah, kiri, kanan


_TOP_WORDS = re.compile(r"KARTU|KELUARGA\b|NAMA\s*KEPALA|ALAMAT|KECAMATAN|KELURAHAN|PROVINSI|KODE\s*POS|RT\s*/\s*RW", re.I)


def _upside_down(boxes: list[Box], table: tuple[int, int]) -> bool:
    """Label kepala KK seharusnya di atas tabel. Bila lebih banyak di bawah tabel: halaman terbalik."""
    top = sum(1 for b in boxes if b.cy < table[0] and _TOP_WORDS.search(b.text))
    bottom = sum(1 for b in boxes if b.cy > table[1] and _TOP_WORDS.search(b.text))
    return bottom > top


def _flip(boxes: list[Box], width: int, height: int) -> list[Box]:
    return [Box(b.text, width - b.x1, height - b.y1, width - b.x0, height - b.y0, b.score) for b in boxes]


def _upright(img):
    """Tanpa tabel yang terdeteksi: putar 90° bila sebagian besar teks tegak."""
    import cv2

    boxes = _ocr(img)
    tall = sum(1 for b in boxes if b.h > b.w * 1.3 and len(b.text) >= 3)
    wide = sum(1 for b in boxes if b.w > b.h * 1.3 and len(b.text) >= 3)
    if tall > wide:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        boxes = _ocr(img)
    return img, boxes


# ---------------------------------------------------------------------------
# Spasi yang hilang
# ---------------------------------------------------------------------------
# Potongan nama/tempat yang umum di Indonesia (huruf besar). Dipakai HANYA untuk memisah teks yang spasinya
# hilang, mis. "SITIAMINAH" -> "SITI AMINAH"; teks yang sudah berspasi tidak diubah.
COMMON_WORDS = set("""
ABDUL ABDULLAH ABU ACHMAD ADE ADI ADITYA AGUS AHMAD AJI AKBAR ALI ALIF AMALIA AMIN AMINAH ANA ANAK ANDI ANGGA ANI
ANISA ANNISA ANTO APRIL ARIF ARIFIN ASTUTI AYU AZIZ BAGUS BAMBANG BAYU BUDI CAHYA CAHYO DANI DARMA DEDI DEVI DEWA
DEWI DIAN DIMAS DWI EKA ELI ENDANG ERNA FADIL FAHMI FAJAR FAJRI FAREL FATIMAH FEBRI FIRMAN FITRI FITRIA GALIH GILANG
HADI HAMIDAH HANDAYANI HARI HASAN HASANAH HENDRA HERI HIDAYAT HUSAIN IBRAHIM ILHAM IMAM INDAH INDRA INTAN IRFAN
IRMA ISMAIL JAYA JOKO JULI KARTIKA KURNIA KURNIAWAN LESTARI LINDA LUTFI MAHMUD MARIA MAULANA MEGA MUHAMAD
MUHAMMAD MUHAMMAT MOHAMMAD MOH NABILA NADIA NIA NOVI NUR NURUL PERMATA PRATAMA PUTRA PUTRI RAHAYU RAHMAD RAHMAN
RAHMAT RATNA RATU REZA RIZKI RIZKY RIZAL ROHMAH RUDI SALEH SANTOSO SARI SATRIA SETIA SETIAWAN SITI SLAMET SRI
SUKMA SURYA SUSANTI SYAHPUTRA SYAIFUL SYUKUR TAUFIK TEGUH TRI UMAR USMAN UTAMI WAHYU WATI WIBOWO WIDIA WULAN
YANTI YOGA YUDHA YULI YUSUF ZAINAL ZAHRA
TANJUNG KOTA SUNGAI PULAU BANDAR BATU KUALA MUARA LONG TELUK LUBUK TANAH BUKIT PADANG KAMPUNG TELUK SELOR PALAS
NUSA SIMPANG KEDUNG TAMAN BARU RAYA LAMA UTARA SELATAN TIMUR BARAT TENGAH HILIR HULU
""".split())
NAME_KEYS = {"nama", "nama_ayah", "nama_ibu", "tempat_lahir", "head"}


def _vocabulary(boxes: list[Box]) -> set[str]:
    words = set(COMMON_WORDS)
    for b in boxes:
        for token in re.findall(r"[A-Z]{3,}", b.text.upper()):
            if len(b.text.split()) >= 2:  # kata dari teks yang spasinya terbaca
                words.add(token)
    return words


def split_joined(token: str, vocab: set[str]) -> str:
    """'HAIRULFITRI' -> 'HAIRUL FITRI' bila bisa dipecah menjadi kata-kata yang dikenal
    (boleh satu potongan tak dikenal sepanjang >= 4 huruf). Selain itu dikembalikan apa adanya."""
    if len(token) < 5 or not token.isalpha() or token in COMMON_WORDS:
        return token
    if token[:-1] in vocab and token[-1] not in "AIUEO":  # inisial di akhir: 'SYUKURH' -> 'SYUKUR H'
        return f"{token[:-1]} {token[-1]}"
    if len(token) < 7 or token in vocab:
        return token
    n = len(token)
    best: dict[int, tuple[int, int, list[str]]] = {0: (0, 0, [])}  # posisi -> (tak dikenal, -jumlah dikenal, kata)
    for i in range(n):
        if i not in best:
            continue
        unknown, known, parts = best[i]
        for j in range(i + 2, n + 1):
            piece = token[i:j]
            if piece in vocab and len(piece) >= 3:
                cand = (unknown, known - 1, parts + [piece])
            elif len(piece) >= 4 and unknown == 0:
                cand = (1, known, parts + [piece])
            else:
                continue
            if j not in best or cand[:2] < best[j][:2]:
                best[j] = cand
    if n not in best:
        return token
    unknown, known, parts = best[n]
    if len(parts) < 2 or -known < 1 or len(parts) > 4:
        return token
    return " ".join(parts)


def transfer_spaces(text: str, spaced: str) -> str | None:
    """Pindahkan posisi spasi dari ``spaced`` (bacaan Tesseract) ke ``text`` (bacaan PaddleOCR yang hurufnya lebih
    akurat) bila deretan huruf/angkanya sama panjang dan hampir sama. Contoh: ':BUDISANTOSO' + 'BUDI SANTOSO'."""
    import difflib

    def core(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    a, b = core(text), core(spaced)
    if not a or len(a) != len(b) or difflib.SequenceMatcher(None, a, b).ratio() < 0.8:
        return None
    cuts, count = set(), 0
    for word in spaced.upper().split():
        count += len(core(word))
        cuts.add(count)
    out, seen = [], 0
    for ch in text:
        if ch.isspace():
            continue
        if ch.upper().isalnum():
            if seen in cuts and seen and out and out[-1] != " " and out[-1].isalnum():
                out.append(" ")
            seen += 1
        out.append(ch)
    return "".join(out)


def _is_standard(text: str) -> bool:
    """Isian baku (pendidikan, pekerjaan, status, hubungan) sudah dicocokkan tanpa spasi: tidak perlu Tesseract."""
    squashed = base._squash(text)
    words = base.EDUCATION_WORDS + base.JOB_WORDS + [w for w, _ in base.MARITAL_WORDS] + [w for w, _ in base.RELATION_WORDS]
    return any(base._squash(w) == squashed for w in words) or bool(base._snap(text, base.EDUCATION_WORDS + base.JOB_WORDS, 0.9))


def _respace(img, boxes: list[Box], cmd: str | None) -> None:
    """Teks huruf besar panjang tanpa spasi (mis. hasil scan kecil): baca potongannya dengan Tesseract untuk
    mendapatkan letak spasi. Hanya spasi yang dipakai; hurufnya tetap dari PaddleOCR."""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    import cv2

    if not cmd:
        return
    targets = [b for b in boxes if re.search(r"[A-Z]{9,}", b.text) and len(b.text) <= 80 and not _is_standard(b.text)][:40]
    if not targets:
        return
    lang = base._lang_arg(cmd)
    height, width = img.shape[:2]
    with tempfile.TemporaryDirectory(prefix="hp-spasi-") as tmp:
        def read(i_box):
            i, b = i_box
            pad = max(4, int(b.h * 0.25))
            crop = img[max(0, int(b.y0) - pad): min(height, int(b.y1) + pad), max(0, int(b.x0) - pad): min(width, int(b.x1) + pad)]
            if crop.size == 0:
                return b, ""
            scale = max(1.0, 48 / max(1.0, b.h))
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            path = f"{tmp}/b{i}.png"
            cv2.imwrite(path, crop)
            try:
                return b, base._run(cmd, path, psm=7, lang=lang).strip()
            except OSError:
                return b, ""

        with ThreadPoolExecutor(max_workers=3) as pool:
            for b, spaced in pool.map(read, enumerate(targets)):
                fixed = transfer_spaces(b.text, spaced) if " " in spaced.strip() else None
                if fixed:
                    b.text = fixed


def _fixer(boxes: list[Box]):
    vocab = _vocabulary(boxes)
    spaced = {}
    for b in boxes:  # versi berspasi dari teks yang sama di bagian lain KK, mis. nama ibu
        if " " in b.text.strip():
            spaced.setdefault(base._squash(b.text), b.text.strip().upper())

    def fix(key: str, text: str) -> str:
        if not text:
            return text
        text = re.sub(r"\b(JL|JLN|GG|KOMP|PERUM|BLOK|NO|DSN|DUSUN)\.(?=[A-Z0-9])", r"\1. ", text, flags=re.I)
        if key not in NAME_KEYS:
            return text
        if key != "head" and " " not in text.strip() and base._squash(text) in spaced:
            return spaced[base._squash(text)]
        source = text if key == "head" else text.upper()  # label kepala KK huruf kecil-besar: tidak disentuh
        return re.sub(r"[A-Z]{5,}", lambda m: split_joined(m.group(), vocab), source)

    return fix


# ---------------------------------------------------------------------------
# KK
# ---------------------------------------------------------------------------
def _lines(boxes: list[Box]) -> list[str]:
    """Kelompokkan kotak teks menjadi baris (urut atas -> bawah, kiri -> kanan)."""
    if not boxes:
        return []
    heights = sorted(b.h for b in boxes)
    tol = heights[len(heights) // 2] * 0.5
    rows: list[list[Box]] = []
    centers: list[float] = []
    for b in sorted(boxes, key=lambda b: b.cy):
        # Bandingkan dengan RATA-RATA tiap baris (bukan kotak terakhir) supaya baris yang rapat tidak menyambung.
        near = min(range(len(rows)), key=lambda i: abs(centers[i] - b.cy), default=None)
        if near is not None and abs(centers[near] - b.cy) <= tol:
            rows[near].append(b)
            centers[near] = sum(x.cy for x in rows[near]) / len(rows[near])
        else:
            rows.append([b])
            centers.append(b.cy)
    order = sorted(range(len(rows)), key=lambda i: centers[i])
    return [" ".join(b.text for b in sorted(rows[i], key=lambda b: b.x0)) for i in order]


def _cells(boxes: list[Box], group: list[base.Row], layout: list[str]) -> list[dict]:
    """Pasangkan teks ke sel tabel (kolom 0 = No dilewati)."""
    x_lo, x_hi = group[0].cols[0][0] - 6, group[0].cols[-1][1] + 6
    rows: list[dict[str, list[Box]]] = [{k: [] for k in layout} for _ in group]
    for b in boxes:
        if not (x_lo <= b.cx <= x_hi):
            continue
        r = next((i for i, row in enumerate(group) if row.top - 4 <= b.cy <= row.bottom + 4), None)
        if r is None:
            continue
        cols = group[r].cols
        c = next((i for i, (a, z) in enumerate(cols) if a - 4 <= b.cx <= z + 4), None)
        if c is None:
            c = min(range(len(cols)), key=lambda i: abs((cols[i][0] + cols[i][1]) / 2 - b.cx))
        if 1 <= c <= len(layout):
            rows[r][layout[c - 1]].append(b)
    return [{k: " ".join(b.text for b in sorted(v, key=lambda b: b.x0)) for k, v in row.items()} for row in rows]


def _line_ink(img, divisor: int = 40) -> Image.Image:
    """Gambar berisi GARIS lurus panjang saja (huruf & arsiran hilang): garis fotokopi yang pudar tetap terlihat."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 8)
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // divisor), 1)))
    # Garis kolom setinggi baris tabel, huruf hanya ±setengahnya: panjang kernel = 70% jarak antargaris baris.
    prof = (horiz > 0).mean(axis=1) * 255
    lines = base._bands(list(prof), max(0.3 * 255, 0.6 * float(prof.max() or 1)))
    gaps = sorted(b[0] - a[1] for a, b in zip(lines, lines[1:]) if b[0] - a[1] > 6)
    row_h = gaps[len(gaps) // 2] if gaps else h // 60
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, int(row_h * 0.7)))))
    # Tebalkan sedikit & sambung garis yang putus-putus (fotokopi).
    horiz = cv2.dilate(horiz, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)))
    vert = cv2.dilate(vert, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9)))
    return Image.fromarray(np.ascontiguousarray(cv2.bitwise_or(horiz, vert)))


RESCUE_SKIP = {"no_paspor", "no_kitap", "tanggal_perkawinan"}  # sering memang kosong ('-')
LOOSE_RESCUE = {"golongan_darah", "jenis_kelamin", "agama", "kewarganegaraan"}


def _rescue(img, group: list[base.Row], rows: list[dict], layout: list[str], active: list[int]) -> None:
    """Sel penting yang kosong pada baris anggota: baca ulang potongan selnya saja (tanpa tahap deteksi)."""
    for i in active:
        if not (0 <= i < len(rows)):
            continue
        row = group[i]
        for c, key in enumerate(layout, start=1):
            if key in RESCUE_SKIP or rows[i].get(key, "").strip() or c >= len(row.cols):
                continue
            x0, x1 = row.cols[c]
            crop = img[max(0, row.top + 1): row.bottom, max(0, x0 + 1): x1]
            if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
                continue
            result, _ = _engine()(crop, use_det=False, use_cls=False)
            if result:
                text, score = result[0][0], float(result[0][1])
                text = unicodedata.normalize("NFKC", str(text)).strip()
                # Kolom berpilihan terbatas tetap divalidasi saat normalisasi, jadi boleh lebih longgar.
                need = 0.3 if key in LOOSE_RESCUE else 0.6
                if score >= need and not base._empty(text) and base._normalize(key, text):
                    rows[i][key] = text


def _grid_quality(groups) -> tuple[int, int]:
    """(kelengkapan tabel, 1 bila susunan KK terbaru 10 + 9 kolom)."""
    a = next((g for g in groups if len(g[0].cols) - 1 in base.TABLE_A), None)
    b = next((g for g in groups if a and g[0].top > a[-1].top and len(g[0].cols) - 1 in base.TABLE_B), None)
    modern = int(bool(a and b and len(a[0].cols) == 10 and len(b[0].cols) == 9))
    return _has_tables(groups), modern


def _grid(img, x_range: tuple[int, int] | None = None):
    """Grid tabel. Dicoba apa adanya dan (bila ``x_range`` diketahui) tanpa garis di luar batas tabel
    (tepi kertas hasil scan), lalu dipilih yang paling utuh."""
    width = img.shape[1]
    best, best_q = [], (-1, -1)
    for divisor in (40, 25):
        _, rows = base._table_rows(_line_ink(img, divisor))
        variants = [rows]
        if x_range:
            lo, hi = x_range[0] - 15, x_range[1] + 15
            clipped = [base.Row(r.top, r.bottom, [ln for ln in r.lines if lo <= (ln[0] + ln[1]) / 2 <= hi]) for r in rows]
            variants.append([r for r in clipped if len(r.lines) >= 4])
        for candidate in variants:
            groups = base._groups(candidate, width)
            quality = _grid_quality(groups)
            if quality > best_q:
                best, best_q = groups, quality
        if best_q == (2, 1):
            break
    return best


def _has_tables(groups) -> int:
    """0 = tabel tidak terbaca, 1 = hanya tabel atas, 2 = tabel atas & bawah dengan 12 baris."""
    a = next((g for g in groups if len(g[0].cols) - 1 in base.TABLE_A), None)
    if a is None:
        return 0
    b = next((g for g in groups if g[0].top > a[-1].top and len(g[0].cols) - 1 in base.TABLE_B), None)
    return 2 if b is not None and len(a) >= 11 and len(b) >= 11 else 1


def read_kk(path: str, tesseract: str | None = None) -> tuple[dict, str] | None:
    import cv2

    original = _load(path)
    # Beberapa calon pelurusan; pakai yang menghasilkan tabel KK utuh (cek grid murah, tanpa OCR).
    chosen = None
    for divisor, method in ((30, "silang"), (30, "kontur"), (45, "silang"), (45, "kontur")):
        quad = _table_quad(original, divisor, method)
        if quad is None:
            continue
        rect, table = _rectify(original, quad)
        groups = _grid(rect, table[2:])
        complete = _has_tables(groups)
        if chosen is None or complete > chosen[3]:
            chosen = (rect, table, groups, complete)
        if complete == 2:
            break
    if chosen is not None:
        img, table, groups, _ = chosen
        boxes = _ocr(img)
        if _upside_down(boxes, table):
            img = cv2.rotate(img, cv2.ROTATE_180)
            boxes = _flip(boxes, img.shape[1], img.shape[0])
            groups = _grid(img, table[2:])  # margin kiri = kanan, jadi batasnya tetap
    else:
        img, boxes = _upright(original)
        groups = _grid(img)
    if not boxes:
        return None
    _respace(img, boxes, tesseract)
    fix = _fixer(boxes)
    table_a = next((g for g in groups if len(g[0].cols) - 1 in base.TABLE_A), None)
    if table_a is None:  # tabel tidak terbaca: susun baris teks lalu pakai pembaca teks biasa
        text = "\n".join(_lines(boxes))
        data = base.parse_kk("\n".join(fix("head", line) for line in text.splitlines()))
        data["metode"] = "foto-teks"
        return data, text
    table_b = next((g for g in groups if g[0].top > table_a[-1].top and len(g[0].cols) - 1 in base.TABLE_B), None)
    layout_a = base.TABLE_A[len(table_a[0].cols) - 1]
    rows_a = _cells(boxes, table_a, layout_a)
    rows_b = _cells(boxes, table_b, base.TABLE_B[len(table_b[0].cols) - 1]) if table_b else []
    # Baris anggota = baris tabel atas yang berisi NIK (>= 10 angka) atau nama.
    active = [i for i, r in enumerate(rows_a) if base._is_data_row(r)
              and (len(re.sub(r"\D", "", r.get("nik", ""))) >= 10 or len(base._name(r.get("nama", "")).replace(" ", "")) >= 3)]
    _rescue(img, table_a, rows_a, layout_a, active)
    if table_b:
        offset = len(rows_b) - len(rows_a)
        _rescue(img, table_b, rows_b, base.TABLE_B[len(table_b[0].cols) - 1], [i + offset for i in active])
    end = (table_b or table_a)[-1].bottom
    head = _lines([b for b in boxes if b.cy < table_a[0].top])
    foot = _lines([b for b in boxes if b.cy > end])
    data, text = base.assemble_kk(rows_a, rows_b, head, foot, fix=fix, method="foto")
    if len(data.get("no_kk", "")) != 16 and table_a[0].top > 40:
        # No. KK (huruf segmen) kadang dikira terbalik oleh pemeriksa arah per baris: baca ulang bagian
        # kepala KK dari gambar yang sudah tegak, tanpa pemeriksa arah.
        again = base.parse_head_lines(_lines(_ocr(img[: table_a[0].top], use_cls=False)))
        if len(again.get("no_kk", "")) == 16:
            data["no_kk"] = base._region_fix(again["no_kk"], [m.get("nik", "") for m in data.get("anggota", [])])
    return data, text


def read_lines(path: str) -> str:
    """KTP/dokumen lain: teks per baris (halaman diputar otomatis bila tegak)."""
    img, boxes = _upright(_load(path))
    return "\n".join(_lines(boxes))
