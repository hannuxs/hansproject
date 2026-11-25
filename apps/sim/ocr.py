"""Baca foto KK/KTP dengan Tesseract OCR (lokal, data tidak keluar server).

Tesseract dipanggil sebagai program terpisah (tanpa shell), dengan batas waktu dan
maksimal SATU dokumen dibaca pada satu waktu, supaya server tetap ringan.

Pemasangan (Windows): jalankan ``pasang-ocr.bat`` (Tesseract + data bahasa ``ind``).
Bila Tesseract belum terpasang, gambar tetap tersimpan dan data diisi manual.

KK dibaca mengikuti STRUKTUR TABELNYA (format Dukcapil):
1. Gambar diluruskan (deskew) dan garis tabel dideteksi dari proyeksi piksel.
2. Setiap kolom tabel dipotong dan dibaca terpisah (kolom NIK & tanggal: angka saja),
   lalu kata-katanya dipasangkan ke baris tabel lewat posisinya.
3. Kepala KK (No. KK, alamat, RT/RW, kelurahan, ...) dibaca dari bagian atas,
   tanggal dikeluarkan dari bagian bawah.
Bila garis tabel tidak terdeteksi (foto miring/terpotong), dipakai pembacaan teks biasa.

Hasilnya selalu DRAF: pengurus memeriksa & membetulkan di formulir sebelum disimpan.
"""
from __future__ import annotations

import csv
import difflib
import io
import logging
import os
import re
import shutil
import subprocess  # nosec B404 - memanggil tesseract dengan argumen list, tanpa shell
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date

from django.conf import settings
from PIL import Image, ImageFilter, ImageOps

log = logging.getLogger("hans")

_LOCK = threading.BoundedSemaphore(1)
_LANGS: dict[str, list[str]] = {}
TIMEOUT_SECONDS = 120
CALL_TIMEOUT = 40
MAX_OCR_PIXELS = 30_000_000


@dataclass
class OcrResult:
    ok: bool
    text: str = ""
    message: str = ""
    available: bool = True
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Program Tesseract
# ---------------------------------------------------------------------------
def tesseract_cmd() -> str | None:
    configured = getattr(settings, "TESSERACT_CMD", "") or ""
    candidates = [configured] if configured else []
    candidates += [r"C:\Program Files\Tesseract-OCR\tesseract.exe", "tesseract"]
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isabs(candidate):
            if os.path.isfile(candidate):
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def is_available() -> bool:
    return tesseract_cmd() is not None


def _data_dir_args() -> list[str]:
    folder = getattr(settings, "TESSERACT_DATA_DIR", "") or ""
    if folder and os.path.isfile(os.path.join(folder, "eng.traineddata")):
        return ["--tessdata-dir", folder]
    return []


def _languages(cmd: str) -> list[str]:
    key = cmd + "|" + "|".join(_data_dir_args())
    if key not in _LANGS:
        try:
            out = subprocess.run(  # nosec B603 - program & argumen tetap
                [cmd, *_data_dir_args(), "--list-langs"], capture_output=True, text=True, timeout=20, check=False
            )
            _LANGS[key] = [line.strip() for line in (out.stdout or "").splitlines()[1:] if line.strip()]
        except (OSError, subprocess.SubprocessError):
            _LANGS[key] = []
    return _LANGS[key]


def _lang_arg(cmd: str) -> str:
    wanted = getattr(settings, "TESSERACT_LANG", "") or "ind+eng"
    have = set(_languages(cmd))
    chosen = [lang for lang in wanted.split("+") if lang in have]
    return "+".join(chosen) or "eng"


def has_indonesian() -> bool:
    cmd = tesseract_cmd()
    return bool(cmd) and "ind" in _languages(cmd)


def _run(cmd: str, image_path: str, *, psm: int, lang: str, tsv: bool = False, whitelist: str = "") -> str:
    args = [cmd, image_path, "stdout", *_data_dir_args(), "-l", lang, "--psm", str(psm)]
    if whitelist:
        args += ["-c", f"tessedit_char_whitelist={whitelist}"]
    if tsv:  # bukan file konfigurasi "tsv": tidak ada di folder data bahasa sendiri
        args += ["-c", "tessedit_create_tsv=1"]
    proc = subprocess.run(args, capture_output=True, timeout=CALL_TIMEOUT, check=False)  # nosec B603
    if proc.returncode != 0:
        raise OSError(f"tesseract exit {proc.returncode}")
    return proc.stdout.decode("utf-8", errors="replace")


@dataclass
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int

    @property
    def cx(self) -> float:
        return self.left + self.width / 2

    @property
    def cy(self) -> float:
        return self.top + self.height / 2


def _tsv_words(output: str) -> list[Word]:
    words = []
    reader = csv.reader(io.StringIO(output), delimiter="\t", quoting=csv.QUOTE_NONE)
    next(reader, None)
    for row in reader:
        if len(row) < 12 or row[0] != "5" or not row[11].strip():
            continue
        try:
            words.append(Word(row[11].strip(), int(row[6]), int(row[7]), int(row[8]), int(row[9])))
        except ValueError:
            continue
    return words


# ---------------------------------------------------------------------------
# Pengolahan gambar (Pillow saja)
# ---------------------------------------------------------------------------
def _otsu(gray: Image.Image) -> int:
    hist = gray.histogram()[:256]
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))
    sum_b = weight_b = 0
    best, threshold = -1.0, 128
    for i, h in enumerate(hist):
        weight_b += h
        if weight_b == 0:
            continue
        weight_f = total - weight_b
        if weight_f == 0:
            break
        sum_b += i * h
        mean_b = sum_b / weight_b
        mean_f = (sum_all - sum_b) / weight_f
        between = weight_b * weight_f * (mean_b - mean_f) ** 2
        if between > best:
            best, threshold = between, i
    return threshold


def _ink(gray: Image.Image, *, lenient: bool = False) -> Image.Image:
    """Gambar 'tinta': 255 = gelap (teks/garis), 0 = kertas. ``lenient``: garis pudar (foto buram) ikut terhitung."""
    t = _otsu(gray)
    if lenient:
        t = t + (255 - t) // 4
    return gray.point(lambda v: 255 if v <= t else 0)


def _profile(img: Image.Image, axis: str) -> list[int]:
    """Rata-rata tinta per baris (axis='y') atau per kolom (axis='x'), 0–255."""
    if axis == "y":
        return list(img.resize((1, img.height), Image.Resampling.BOX).getdata())
    return list(img.resize((img.width, 1), Image.Resampling.BOX).getdata())


def _line_mask(ink: Image.Image, length: int, vertical: bool) -> Image.Image:
    """Piksel milik garis lurus >= ``length`` piksel (rata-rata kotak sepanjang garis hampir penuh tinta)."""
    w, h = ink.size
    mask = Image.new("L", (w, h), 0)
    for offset in (0, length // 2):
        if vertical:
            part = ink.crop((0, offset, w, h))
            if part.height < length:
                continue
            small = part.resize((w, part.height // length), Image.Resampling.BOX)
            big = small.point(lambda v: 255 if v > 210 else 0).resize((w, small.height * length), Image.Resampling.NEAREST)
            mask.paste(255, (0, offset), big)
        else:
            part = ink.crop((offset, 0, w, h))
            if part.width < length:
                continue
            small = part.resize((part.width // length, h), Image.Resampling.BOX)
            big = small.point(lambda v: 255 if v > 210 else 0).resize((small.width * length, h), Image.Resampling.NEAREST)
            mask.paste(255, (offset, 0), big)
    return mask.filter(ImageFilter.MaxFilter(5))


def _erase_lines(gray: Image.Image, *, h_len: int | None = None, v_len: int | None = None) -> Image.Image:
    """Hapus garis kotak/garis bawah dari potongan gambar supaya tulisan di dalamnya terbaca."""
    ink = _ink(gray)
    h_len = h_len or max(40, gray.width // 30)
    v_len = v_len or max(40, gray.height // 5)
    mask = _line_mask(ink, h_len, False)
    mask.paste(255, (0, 0), _line_mask(ink, v_len, True))
    out = gray.copy()
    out.paste(255, (0, 0), mask)
    return out


def _deskew_angle(ink: Image.Image) -> float:
    """Sudut kemiringan (derajat) yang membuat garis tabel paling tajam (variasi proyeksi baris terbesar)."""
    scale = 1000 / ink.width
    small = ink.resize((1000, max(1, int(ink.height * scale))), Image.Resampling.BOX)

    def score(angle: float) -> float:
        prof = _profile(small.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=0), "y")
        return sum(v * v for v in prof)

    best = max((a / 2 for a in range(-10, 11)), key=score)
    return max((best + a / 10 for a in range(-5, 6)), key=score)


def _bands(values: list[int], threshold: float, *, gap: int = 2) -> list[tuple[int, int]]:
    """Kelompok indeks berurutan yang nilainya > threshold, mis. letak garis tabel."""
    bands: list[list[int]] = []
    for i, v in enumerate(values):
        if v > threshold:
            if bands and i - bands[-1][1] <= gap:
                bands[-1][1] = i
            else:
                bands.append([i, i])
    return [(a, b) for a, b in bands]


@dataclass
class Row:
    top: int
    bottom: int
    lines: list[tuple[int, int]]  # garis kolom (x0, x1) yang terdeteksi di baris ini
    cols: list[tuple[int, int]] = field(default_factory=list)  # (x0, x1) bagian dalam setiap sel, diisi _groups


def _table_rows(ink: Image.Image) -> tuple[list[tuple[int, int]], list[Row]]:
    """Garis horizontal tabel + baris-baris di antaranya beserta garis kolom yang terdeteksi."""
    prof = _profile(ink, "y")
    # Garis tabel (selebar tabel) jauh lebih pekat daripada baris tulisan, juga pada foto buram.
    h_lines = _bands(prof, max(0.35 * 255, 0.72 * max(prof or [0])))
    min_h = max(8, ink.height // 160)
    rows = []
    for (_, a_end), (b_start, _) in zip(h_lines, h_lines[1:]):
        top, bottom = a_end + 1, b_start - 1
        if bottom - top < min_h:
            continue
        # Garis kolom menyentuh tepi atas DAN bawah baris; huruf (ada jarak ke garis) biasanya tidak.
        whole = _profile(ink.crop((0, top, ink.width, bottom + 1)), "x")
        edge = 3
        upper = _profile(ink.crop((0, top, ink.width, top + edge)), "x")
        lower = _profile(ink.crop((0, bottom + 1 - edge, ink.width, bottom + 1)), "x")
        joined = [min(a, b, c) if a > 0.8 * 255 else 0 for a, b, c in zip(whole, upper, lower)]
        v_lines = _bands(joined, 0.55 * 255, gap=2)
        if len(v_lines) >= 4:
            rows.append(Row(top, bottom, v_lines))
    return h_lines, rows


def _hits(lines: list[tuple[int, int]], centers: list[float], tol: float) -> int:
    return sum(1 for c in centers if any(abs((a + b) / 2 - c) <= tol for a, b in lines))


def _consensus(group: list[Row], tol: float, share: float, *, with_count: bool = False) -> list:
    """Garis kolom yang muncul di >= ``share`` baris kelompok (garis palsu dari huruf tebal tersaring)."""
    clusters: list[list[tuple[int, int]]] = []
    for row in group:
        for line in row.lines:
            center = (line[0] + line[1]) / 2
            for cluster in clusters:
                if abs(sum((a + b) / 2 for a, b in cluster) / len(cluster) - center) <= tol:
                    cluster.append(line)
                    break
            else:
                clusters.append([line])
    need = max(1, int(len(group) * share + 0.5))
    picked = [c for c in clusters if len(c) >= need]
    out = []
    for cluster in sorted(picked, key=lambda c: sum(a for a, _ in c) / len(c)):
        xs0 = sorted(a for a, _ in cluster)
        xs1 = sorted(b for _, b in cluster)
        out.append((xs0[len(xs0) // 2], xs1[len(xs1) // 2], len(cluster)))
    return [(a, b) for a, b, _ in out] if not with_count else out  # type: ignore[return-value]


def _groups(rows: list[Row], width: int) -> list[list[Row]]:
    """Baris berurutan yang garis kolomnya (hampir) sama = badan satu tabel. Kolom ditentukan konsensus."""
    tol = width * 0.011
    groups: list[list[Row]] = []
    for row in rows:
        if groups:
            core_lines = _consensus(groups[-1], tol, 0.5)
            core = [(a + b) / 2 for a, b in core_lines]
            own = [(a + b) / 2 for a, b in row.lines]
            # Cocok bila hampir semua garis inti ada di baris ini, atau hampir semua garis baris ini ada di inti
            # (baris berhuruf tebal punya garis palsu tambahan; baris kosong tidak).
            if core and (_hits(row.lines, core, tol) >= 0.8 * len(core) or _hits(core_lines, own, tol) >= 0.8 * len(own)):
                groups[-1].append(row)
                continue
        groups.append([row])
    out = []
    for group in groups:
        if len(group) < 4:
            continue
        counted = _consensus(group, tol, 0.6, with_count=True)
        # Masih ada garis palsu (huruf tebal di posisi sama tiap baris)? Buang yang paling jarang muncul
        # sampai jumlah kolom cocok dengan format KK.
        known = set(TABLE_A) | set(TABLE_B)
        while len(counted) - 2 not in known and len(counted) - 2 > min(known):
            inner = counted[1:-1]
            weakest = min(inner, key=lambda line: line[2])
            if weakest[2] >= len(group) * 0.9:
                break
            counted.remove(weakest)
        lines = [(a, b) for a, b, _ in counted]
        cols = [(a[1] + 1, b[0] - 1) for a, b in zip(lines, lines[1:]) if b[0] - a[1] > 6]
        if len(cols) < 7:
            continue
        out.append(_split_tall([Row(r.top, r.bottom, r.lines, cols) for r in group]))
    return out


def _split_tall(group: list[Row]) -> list[Row]:
    """Garis antarbaris yang tidak terdeteksi (foto buram) membuat dua baris menyatu: bagi rata lagi."""
    heights = sorted(r.bottom - r.top for r in group)
    normal = heights[len(heights) // 2]
    out = []
    for row in group:
        count = round((row.bottom - row.top) / normal) if normal else 1
        if count >= 2 and row is not group[0]:
            step = (row.bottom - row.top) / count
            out += [Row(int(row.top + i * step), int(row.top + (i + 1) * step) - 1, row.lines, row.cols) for i in range(count)]
        else:
            out.append(row)
    return out


def _save(img: Image.Image, folder: str, name: str) -> str:
    path = os.path.join(folder, name)
    img.save(path, "PNG")
    return path


# ---------------------------------------------------------------------------
# Kosakata KK (ejaan Dukcapil)
# ---------------------------------------------------------------------------
_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1", "|": "1", "!": "1", "S": "5", "B": "8", "Z": "2"})
_NIK = re.compile(r"(?<![0-9A-Za-z])([0-9OoDQIl|!SBZ]{16})(?![0-9A-Za-z])")
_DATE = re.compile(r"(\d{1,2})\s*[-/.,]\s*(\d{1,2})\s*[-/.,]\s*(\d{4})")
RELIGION_WORDS = {
    "ISLAM": "Islam", "KRISTEN": "Kristen", "PROTESTAN": "Kristen", "KATOLIK": "Katolik", "KATHOLIK": "Katolik",
    "HINDU": "Hindu", "BUDHA": "Buddha", "BUDDHA": "Buddha", "KONGHUCU": "Konghucu", "KHONGHUCU": "Konghucu",
    "KEPERCAYAAN": "Kepercayaan",
}
# Nilai status perkawinan di KK -> pilihan di sistem (urut dari yang terpanjang).
MARITAL_WORDS = [
    ("CERAI HIDUP BELUM TERCATAT", "Cerai Hidup Belum Tercatat"), ("CERAI MATI BELUM TERCATAT", "Cerai Mati Belum Tercatat"),
    ("KAWIN BELUM TERCATAT", "Kawin Belum Tercatat"), ("CERAI HIDUP TERCATAT", "Cerai Hidup Tercatat"),
    ("CERAI MATI TERCATAT", "Cerai Mati Tercatat"), ("CERAI BELUM TERCATAT", "Cerai Belum Tercatat"),
    ("CERAI TERCATAT", "Cerai Tercatat"), ("KAWIN TERCATAT", "Kawin Tercatat"), ("BELUM KAWIN", "Belum Kawin"),
    ("CERAI HIDUP", "Cerai Hidup"), ("CERAI MATI", "Cerai Mati"), ("KAWIN", "Kawin"),
]
RELATION_WORDS = [
    ("KEPALA KELUARGA", "Kepala Keluarga"), ("FAMILI LAIN", "Famili Lain"), ("ORANG TUA", "Orang Tua"),
    ("MENANTU", "Menantu"), ("MERTUA", "Mertua"), ("PEMBANTU", "Pembantu"), ("LAINNYA", "Lainnya"),
    ("SUAMI", "Suami"), ("ISTRI", "Istri"), ("CUCU", "Cucu"), ("ANAK", "Anak"),
]
EDUCATION_WORDS = [
    "TIDAK/BELUM SEKOLAH", "BELUM TAMAT SD/SEDERAJAT", "TAMAT SD/SEDERAJAT", "SLTP/SEDERAJAT", "SLTA/SEDERAJAT",
    "DIPLOMA I/II", "AKADEMI/DIPLOMA III/SARJANA MUDA", "DIPLOMA IV/STRATA I", "STRATA II", "STRATA III",
]
JOB_WORDS = [
    "BELUM/TIDAK BEKERJA", "MENGURUS RUMAH TANGGA", "PELAJAR/MAHASISWA", "PENSIUNAN", "PEGAWAI NEGERI SIPIL",
    "TENTARA NASIONAL INDONESIA", "KEPOLISIAN RI", "PERDAGANGAN", "PETANI/PEKEBUN", "PETERNAK", "NELAYAN/PERIKANAN",
    "INDUSTRI", "KONSTRUKSI", "TRANSPORTASI", "KARYAWAN SWASTA", "KARYAWAN BUMN", "KARYAWAN BUMD", "KARYAWAN HONORER",
    "BURUH HARIAN LEPAS", "BURUH TANI/PERKEBUNAN", "BURUH NELAYAN/PERIKANAN", "BURUH PETERNAKAN",
    "PEMBANTU RUMAH TANGGA", "TUKANG CUKUR", "TUKANG LISTRIK", "TUKANG BATU", "TUKANG KAYU", "TUKANG SOL SEPATU",
    "TUKANG LAS/PANDAI BESI", "TUKANG JAHIT", "TUKANG GIGI", "PENATA RIAS", "PENATA BUSANA", "PENATA RAMBUT",
    "MEKANIK", "SENIMAN", "TABIB", "PARAJI", "PERANCANG BUSANA", "PENTERJEMAH", "IMAM MASJID", "PENDETA", "PASTOR",
    "WARTAWAN", "USTADZ/MUBALIGH", "JURU MASAK", "PROMOTOR ACARA", "ANGGOTA DPR-RI", "ANGGOTA DPD", "ANGGOTA BPK",
    "PRESIDEN", "WAKIL PRESIDEN", "ANGGOTA MAHKAMAH KONSTITUSI", "ANGGOTA KABINET/KEMENTERIAN", "DUTA BESAR",
    "GUBERNUR", "WAKIL GUBERNUR", "BUPATI", "WAKIL BUPATI", "WALIKOTA", "WAKIL WALIKOTA", "ANGGOTA DPRD PROVINSI",
    "ANGGOTA DPRD KABUPATEN/KOTA", "DOSEN", "GURU", "PILOT", "PENGACARA", "NOTARIS", "ARSITEK", "AKUNTAN", "KONSULTAN",
    "DOKTER", "BIDAN", "PERAWAT", "APOTEKER", "PSIKIATER/PSIKOLOG", "PENYIAR TELEVISI", "PENYIAR RADIO", "PELAUT",
    "PENELITI", "SOPIR", "PIALANG", "PARANORMAL", "PEDAGANG", "PERANGKAT DESA", "KEPALA DESA", "BIARAWATI",
    "WIRASWASTA", "LAINNYA",
]
BLOOD_TYPES = ["A", "B", "AB", "O", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "TIDAK TAHU"]


def _digits(value: str) -> str:
    return value.translate(_DIGIT_FIX)


def find_niks(text: str) -> list[str]:
    seen, out = set(), []
    for match in _NIK.finditer(text or ""):
        nik = _digits(match.group(1))
        if nik.isdigit() and nik not in seen:
            seen.add(nik)
            out.append(nik)
    return out


def parse_date(value: str) -> str:
    """'17-08-1990' -> '1990-08-17' (ISO) atau '' bila tidak masuk akal."""
    value = _digits(value or "")
    match = _DATE.search(value) or re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", value)
    if not match:
        return ""
    day, month, year = (int(x) for x in match.groups())
    try:
        parsed = date(year, month, day)
    except ValueError:
        return ""
    if not (1900 <= parsed.year <= date.today().year):
        return ""
    return parsed.isoformat()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" :;.,-_|=~'\"")


def _empty(value: str) -> bool:
    return not re.sub(r"[\s\-–—_.|:;,'\"~=]+", "", value or "")


def _snap(value: str, options: list[str], cutoff: float) -> str:
    """Cocokkan hasil baca ke ejaan baku terdekat (mis. 'SLTA/SEDERAJAI' -> 'SLTA/SEDERAJAT')."""
    upper = _clean(value).upper()
    if not upper:
        return ""
    if upper in options:
        return upper
    match = difflib.get_close_matches(upper, options, n=1, cutoff=cutoff)
    return match[0] if match else ""


def _gender(text: str) -> str:
    upper = re.sub(r"[^A-Z]", "", (text or "").upper())
    if not upper:
        return ""
    if "PEREM" in upper or "WANITA" in upper or difflib.SequenceMatcher(None, upper, "PEREMPUAN").ratio() > 0.6:
        return "P"
    if "LAKI" in upper or "PRIA" in upper or difflib.SequenceMatcher(None, upper, "LAKILAKI").ratio() > 0.6:
        return "L"
    return ""


def _pick(text: str, pairs) -> str:
    """Nilai baku dari kata kunci (cocok persis dulu, lalu yang paling mirip)."""
    upper = _clean(text).upper()
    if not upper:
        return ""
    items = list(pairs.items()) if isinstance(pairs, dict) else list(pairs)
    for word, value in items:
        if word in upper:
            return value
    words = [w for w, _ in items]
    match = difflib.get_close_matches(upper, words, n=1, cutoff=0.7)
    return dict(items)[match[0]] if match else ""


def _name(text: str) -> str:
    text = re.sub(r"[^A-Za-z .,'`-]", " ", text or "")
    tokens = text.split()
    # Isi KK huruf besar semua: potongan huruf kecil biasanya sisa garis/noda yang terbaca huruf.
    if any(t.isupper() and len(t) >= 2 for t in tokens):
        tokens = [t for t in tokens if not any(ch.islower() for ch in t)]
    return _clean(" ".join(tokens)).upper()[:100]


def _place(text: str) -> str:
    return _name(text)[:60]


def _blood(text: str) -> str:
    upper = re.sub(r"\s+", " ", (text or "").upper()).strip(" -.")
    if not upper:
        return ""
    if "TIDAK" in upper or "TAHU" in upper:
        return "TIDAK TAHU"
    upper = upper.replace("0", "O").replace(" ", "")
    return upper if upper in BLOOD_TYPES else ""


def _doc_number(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()
    return value[:30] if len(value) >= 4 else ""


def _nik_value(text: str) -> str:
    digits = re.sub(r"\D", "", _digits(re.sub(r"\s+", "", text or "")))
    return digits if 8 <= len(digits) <= 18 else ""


# ---------------------------------------------------------------------------
# Kepala KK (label : nilai, dua kolom dalam satu baris)
# ---------------------------------------------------------------------------
_HEAD_LABELS = [
    ("kepala_nama", r"nama\s*kepala\s*keluarga"),
    ("kelurahan", r"desa\s*/?\s*kelurahan|kelurahan\s*/?\s*desa"),
    ("kota", r"kabupaten\s*/?\s*kota"),
    ("kecamatan", r"kecamatan"),
    ("provinsi", r"provinsi"),
    ("alamat", r"alamat"),
    ("rt_rw", r"rt\s*/\s*rw"),
    ("kode_pos", r"kode\s*pos"),
]
_HEAD_RE = re.compile("|".join(f"(?P<{key}>{pattern})" for key, pattern in _HEAD_LABELS), re.IGNORECASE)


def _head_value(raw: str) -> str:
    """Nilai setelah label: buang titik dua yang terbaca '1'/'i', dan potongan huruf kecil (noda) di ujung."""
    value = _clean(raw)
    value = re.sub(r"^[1Il|!:;,.]\s+(?=[A-Za-z])", "", value)
    tokens = value.split()
    if any(t.isupper() and len(t) >= 2 for t in tokens):
        tokens = [t for t in tokens if not any(ch.islower() for ch in t)]
    return _clean(" ".join(tokens))


def parse_head_lines(lines: list[str]) -> dict:
    """'Nama Kepala Keluarga : BUDI   Desa/Kelurahan : SUKAMAJU' -> {kepala_nama: BUDI, kelurahan: SUKAMAJU}."""
    data: dict = {}
    for line in lines:
        matches = list(_HEAD_RE.finditer(line))
        for i, match in enumerate(matches):
            key = match.lastgroup
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            value = _head_value(line[match.end():end])
            if key and value and key not in data:
                data[key] = value
        if "no_kk" not in data:
            niks = find_niks(line.replace(" ", "")) if re.search(r"\bN[o0]\b|KELUARGA", line, re.I) else []
            if niks:
                data["no_kk"] = niks[0]
        if "tanggal_dikeluarkan" not in data and re.search(r"dikeluarkan", line, re.I):
            data["tanggal_dikeluarkan"] = parse_date(line)
    if "rt_rw" in data:
        nums = re.findall(r"\d{1,3}", _digits(data.pop("rt_rw")))
        if len(nums) >= 2:
            data["rt"], data["rw"] = nums[0].zfill(3), nums[1].zfill(3)
    if "kode_pos" in data:
        digits = re.findall(r"\d{5}", _digits(data["kode_pos"].replace(" ", "")))
        data["kode_pos"] = digits[0] if digits else ""
    for key in ("alamat", "kelurahan", "kecamatan", "kota", "provinsi"):
        if key in data:
            data[key] = re.sub(r"[^A-Za-z0-9 .,/'-]", "", data[key]).strip().upper()[:100]
    if "kepala_nama" in data:
        data["kepala_nama"] = _name(data["kepala_nama"])
    return data


# ---------------------------------------------------------------------------
# Tabel anggota keluarga
# ---------------------------------------------------------------------------
# Susunan kolom menurut jumlah kolom (setelah kolom No). KK 2020+: 9 & 8 kolom; KK lama: 8 & 7.
TABLE_A = {
    9: ["nama", "nik", "jenis_kelamin", "tempat_lahir", "tanggal_lahir", "agama", "pendidikan", "pekerjaan", "golongan_darah"],
    8: ["nama", "nik", "jenis_kelamin", "tempat_lahir", "tanggal_lahir", "agama", "pendidikan", "pekerjaan"],
}
TABLE_B = {
    8: ["status_perkawinan", "tanggal_perkawinan", "hubungan", "kewarganegaraan", "no_paspor", "no_kitap", "nama_ayah", "nama_ibu"],
    7: ["status_perkawinan", "hubungan", "kewarganegaraan", "no_paspor", "no_kitap", "nama_ayah", "nama_ibu"],
}
DIGIT_COLUMNS = {"nik": "0123456789", "tanggal_lahir": "0123456789-", "tanggal_perkawinan": "0123456789-"}
_HEADER_WORDS = re.compile(r"PASPOR|KITAP|KITAS|AYAH\b|^IBU$|NAMA LENGKAP|KELAMIN|PENDIDIKAN|PEKERJAAN|KEWARGANEGARAAN", re.I)


def _normalize(key: str, text: str) -> str:
    if _empty(text):
        return ""
    if key == "nik":
        return _nik_value(text)
    if key in ("tanggal_lahir", "tanggal_perkawinan"):
        return parse_date(text)
    if key == "jenis_kelamin":
        return _gender(text)
    if key == "agama":
        return _pick(text, RELIGION_WORDS)
    if key == "pendidikan":
        return _snap(text, EDUCATION_WORDS, 0.6)
    if key == "pekerjaan":
        return _snap(text, JOB_WORDS, 0.75) or _clean(re.sub(r"[^A-Za-z0-9 /().-]", " ", text)).upper()[:60]
    if key == "golongan_darah":
        return _blood(text)
    if key == "status_perkawinan":
        return _pick(text, MARITAL_WORDS)
    if key == "hubungan":
        return _pick(text, RELATION_WORDS)
    if key == "kewarganegaraan":
        upper = text.upper()
        return "WNA" if "WNA" in upper else "WNI" if "WN" in upper or "W" in upper else ""
    if key in ("no_paspor", "no_kitap"):
        return _doc_number(text)
    if key == "tempat_lahir":
        return _place(text)
    return _name(text)


def _column_image(gray: Image.Image, group: list[Row], col: int, h_lines: list[tuple[int, int]], scale: float):
    """Potongan satu kolom tabel (semua baris), garis horizontal dihapus, diperbesar & diberi tepi putih."""
    x0 = min(r.cols[col][0] for r in group) + 3
    x1 = max(r.cols[col][1] for r in group) - 4
    top, bottom = group[0].top, group[-1].bottom
    crop = gray.crop((x0, top, x1, bottom))
    paint = Image.new("L", (crop.width, 1), 255)
    for a, b in h_lines:  # garis baris + tepi abu-abunya diputihkan
        if top <= b and a <= bottom:
            for y in range(max(0, a - top - 2), min(crop.height, b - top + 3)):
                crop.paste(paint, (0, y))
    if scale != 1:
        crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
    pad = 20
    canvas = Image.new("L", (crop.width + pad * 2, crop.height + pad * 2), 255)
    canvas.paste(ImageOps.autocontrast(crop, cutoff=1), (pad, pad))
    return canvas, pad, top


def _read_column(cmd: str, lang: str, gray: Image.Image, group: list[Row], col: int, key: str,
                 h_lines: list[tuple[int, int]], scale: float, folder: str, psm: int = 6) -> list[str]:
    """Baca satu kolom tabel (semua baris sekaligus) -> teks per baris."""
    canvas, pad, top = _column_image(gray, group, col, h_lines, scale)
    path = _save(canvas, folder, f"col-{group[0].top}-{col}-{int(scale * 100)}-{psm}.png")
    whitelist = DIGIT_COLUMNS.get(key, "")
    words = _tsv_words(_run(cmd, path, psm=psm, lang="eng" if whitelist else lang, tsv=True, whitelist=whitelist))
    cells: list[list[Word]] = [[] for _ in group]
    for word in words:
        y = (word.cy - pad) / scale + top
        for i, row in enumerate(group):
            if row.top - 2 <= y <= row.bottom + 2:
                cells[i].append(word)
                break
    return [" ".join(w.text for w in sorted(c, key=lambda w: w.left)) for c in cells]


def _vote(key: str, readings: list[list[str]]) -> list[str]:
    """Kolom angka dibaca beberapa kali (skala berbeda); per baris pilih hasil sah yang paling sering muncul."""
    out = []
    for values in zip(*readings):
        normalized = [_normalize(key, v) for v in values]
        valid = [v for v in normalized if v and (key != "nik" or len(v) == 16)]
        pool = valid or [v for v in normalized if v]
        if not pool:  # tidak ada bacaan sah: biarkan kosong (diisi pengurus), jangan isi teks acak
            out.append("")
            continue
        best = max(pool, key=lambda v: (pool.count(v), v == normalized[len(normalized) // 2]))
        out.append(best)
    return out


def _merge_text(values) -> str:
    filled = [v.strip() for v in values if not _empty(v)]
    if not filled:
        return values[0]
    best = filled[0]
    for other in filled[1:]:
        a, b = _name(best), _name(other)
        if b and a != b and a.startswith(b + " ") and len(a) - len(b) <= 4:
            best = other  # 'NAMA SI' vs 'NAMA': potongan pendek di ujung = sisa garis tabel
        elif a.replace(" ", "") == b.replace(" ", "") and b.count(" ") > a.count(" "):
            best = other  # 'SITIAMINAH' vs 'SITI AMINAH': spasi antarkata sering hilang
    return best


def _read_table(cmd, lang, gray, group, layout, h_lines, scale, folder, pool) -> list[dict]:
    """Baca semua kolom satu tabel -> daftar baris {kunci: teks}. Kolom angka dibaca 3x lalu divoting."""
    jobs = {}
    for i, key in enumerate(layout):
        # Angka: 3 skala lalu voting. Teks: blok (psm 6) + teks jarang (psm 11, lebih peka spasi antarkata).
        modes = [(scale * 0.85, 6), (scale, 6), (scale * 1.15, 6)] if key in DIGIT_COLUMNS else [(scale, 6), (scale, 11)]
        jobs[key] = [pool.submit(_read_column, cmd, lang, gray, group, i + 1, key, h_lines, s, folder, psm)
                     for s, psm in modes]
    columns = {}
    for key, futures in jobs.items():
        readings = [f.result() for f in futures]
        if key in DIGIT_COLUMNS:
            columns[key] = _vote(key, readings)
        else:  # kolom teks: bacaan utama; kosong -> bacaan kedua; beda hanya di ujung -> yang lebih pendek (noda garis)
            columns[key] = [_merge_text(values) for values in zip(*readings)]
    return [{key: columns[key][i] for key in layout} for i in range(len(group))]


def _text_lines(gray: Image.Image) -> list[tuple[int, int]]:
    """Letak baris-baris tulisan pada kepala KK. Logo Garuda di kiri diabaikan saat mencari baris
    (logonya setinggi beberapa baris sehingga semua baris akan menyatu)."""
    prof = _profile(_ink(gray.crop((int(gray.width * 0.2), 0, gray.width, gray.height))), "y")
    return [(a, b) for a, b in _bands(prof, 4, gap=2) if b - a >= 7]


def _read_line(cmd: str, lang: str, gray: Image.Image, band: tuple[int, int], folder: str, name: str,
               *, scale: float | None = None, blur: float = 0, whitelist: str = "") -> str:
    a, b = band
    crop = gray.crop((0, max(0, a - 4), gray.width, min(gray.height, b + 5)))
    scale = scale or min(3.5, max(1.5, 46 / max(1, b - a)))
    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.Resampling.LANCZOS)
    if blur:
        crop = crop.filter(ImageFilter.GaussianBlur(blur))
    path = _save(ImageOps.autocontrast(crop, cutoff=1), folder, f"{name}.png")
    return _run(cmd, path, psm=7, lang="eng" if whitelist else lang, whitelist=whitelist).strip()


# Huruf nomor KK bergaya segmen: huruf yang sering tertukar dengan angka.
_SEGMENT_FIX = str.maketrans({"b": "6", "G": "6", "L": "1", "l": "1", "I": "1", "e": "2", "Z": "2", "z": "2", "S": "5",
                              "s": "5", "O": "0", "o": "0", "D": "0", "Q": "0", "g": "9", "q": "9", "B": "8", "A": "4"})


def _kk_number(cmd: str, gray: Image.Image, band: tuple[int, int], folder: str, pool) -> str:
    """No. KK (huruf bergaya segmen): dibaca dengan beberapa variasi skala & blur, huruf yang mirip angka
    diterjemahkan (b->6, L->1, e->2, ...), lalu dipilih hasil 16 angka yang paling sering muncul."""
    variants = [(s, b) for s in (1.5, 1.75, 2.0, 2.25, 2.5) for b in (1, 2)]
    raw_jobs = [pool.submit(_read_line, cmd, "eng", gray, band, folder, f"nokk-{i}", scale=s, blur=b)
                for i, (s, b) in enumerate(variants)]
    digit_jobs = [pool.submit(_read_line, cmd, "eng", gray, band, folder, f"nokkd-{i}", scale=s, blur=1,
                              whitelist="0123456789") for i, s in enumerate((1.75, 2.0, 2.5))]
    readings = []
    for job in raw_jobs:
        text = re.sub(r"^\W*N\s*[o0]\W*", "", job.result())
        text = re.sub(r"1L|L1", "L", re.sub(r"\s+", "", text))  # angka 1 berkaki kadang terbaca '1L'
        readings.append(re.sub(r"\D", "", text.translate(_SEGMENT_FIX)))
    partial = [re.sub(r"\D", "", job.result()) for job in digit_jobs]

    def plausible(candidate: str) -> int:
        day, month = int(candidate[6:8]), int(candidate[8:10])
        return int(1 <= day <= 31 and 1 <= month <= 12)

    full = [r for r in readings + partial if len(r) == 16]
    if full:
        def support(candidate: str) -> tuple[int, int]:
            score = sum(2 for r in full if r == candidate)
            score += sum(1 for r in readings + partial if 12 <= len(r) < 16 and r in candidate)
            return score, plausible(candidate)

        return max(full, key=support)
    near = sorted((r for r in readings + partial if 12 <= len(r) <= 17), key=lambda r: abs(16 - len(r)))
    return near[0] if near else ""


def _region_fix(no_kk: str, niks: list[str]) -> str:
    """6 angka pertama No. KK = kode wilayah; biasanya sama dengan awal NIK salah satu anggota.
    Bila hanya beda SATU angka dari awal NIK anggota, pakai kode wilayah dari NIK (lebih mudah dibaca mesin)."""
    if len(no_kk) != 16:
        return no_kk
    for nik in niks:
        if len(nik) == 16 and nik[:6] != no_kk[:6] and sum(a != b for a, b in zip(nik[:6], no_kk[:6])) == 1:
            return nik[:6] + no_kk[6:]
    return no_kk


def _is_data_row(raw: dict) -> bool:
    texts = [t for t in raw.values() if not _empty(t)]
    if not texts:
        return False
    if all(re.fullmatch(r"\(?\s*\d{1,2}\s*\)?", t.strip()) for t in texts):
        return False  # baris nomor kolom (1) (2) (3) ...
    return not any(_HEADER_WORDS.search(t) for t in texts)


def _is_member(row: dict) -> bool:
    """Baris kosong di KK berisi '-' yang kadang terbaca huruf acak: wajib ada NIK, atau nama + beberapa isian."""
    if len(row.get("nik", "")) >= 10:
        return True
    name = row.get("nama", "")
    filled = sum(1 for k in ("jenis_kelamin", "tanggal_lahir", "agama", "hubungan", "status_perkawinan") if row.get(k))
    return len(name.replace(" ", "")) >= 3 and filled >= 2


def _read_structured(cmd: str, path: str, folder: str) -> tuple[dict, str] | None:
    lang = _lang_arg(cmd)
    with Image.open(path) as img:
        gray = ImageOps.exif_transpose(img).convert("L")
    if gray.width < 1600:
        factor = 1600 / gray.width
        gray = gray.resize((1600, int(gray.height * factor)), Image.Resampling.LANCZOS)
    angle = _deskew_angle(_ink(gray))
    if abs(angle) >= 0.05:
        gray = gray.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)
    h_lines, rows = _table_rows(_ink(gray))
    groups = _groups(rows, gray.width)
    if not any(len(g[0].cols) - 1 in TABLE_A for g in groups):  # garis pudar: coba ambang lebih longgar
        h_lines, rows = _table_rows(_ink(gray, lenient=True))
        groups = _groups(rows, gray.width)
    table_a = next((g for g in groups if len(g[0].cols) - 1 in TABLE_A), None)
    if table_a is None:
        return None
    table_b = next((g for g in groups if g[0].top > table_a[-1].top and len(g[0].cols) - 1 in TABLE_B), None)
    # Huruf di tabel KK kecil: perbesar potongan kolom supaya setara lebar halaman ±4000 piksel.
    scale = min(4.0, max(1.0, 3500 / gray.width))
    workers = max(1, min(4, int(getattr(settings, "TESSERACT_WORKERS", 3) or 1)))
    head = gray.crop((0, 0, gray.width, max(1, table_a[0].top - 3)))
    foot_top = (table_b or table_a)[-1].bottom + 4
    foot = gray.crop((0, foot_top, int(gray.width * 0.5), min(gray.height, foot_top + max(40, (gray.height - foot_top) // 2))))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        bands = _text_lines(head)
        line_jobs = [pool.submit(_read_line, cmd, lang, head, band, folder, f"head-{i}") for i, band in enumerate(bands)]
        foot_job = None
        if foot.height >= 30:
            foot_big = foot.resize((foot.width * 3, foot.height * 3), Image.Resampling.LANCZOS)
            foot_path = _save(_erase_lines(foot_big), folder, "foot.png")
            foot_job = pool.submit(_run, cmd, foot_path, psm=6, lang=lang)
        rows_a = _read_table(cmd, lang, gray, table_a, TABLE_A[len(table_a[0].cols) - 1], h_lines, scale, folder, pool)
        rows_b = (_read_table(cmd, lang, gray, table_b, TABLE_B[len(table_b[0].cols) - 1], h_lines, scale, folder, pool)
                  if table_b else [])
        head_lines = [job.result() for job in line_jobs]
        foot_text = foot_job.result() if foot_job else ""
        no_band = next((band for band, text in zip(bands, head_lines)
                        if re.match(r"^\W*N\s*[o0]\W", text) and len(re.sub(r"\D", "", text.translate(_SEGMENT_FIX))) >= 8), None)
        if no_band is None:  # baris dengan angka terbanyak di bagian atas
            scored = [(len(re.findall(r"\d", t)), band) for band, t in zip(bands[:6], head_lines[:6])]
            no_band = max(scored)[1] if scored and max(scored)[0] >= 10 else None
        # No. KK: tanpa logo di kiri & tanpa tepi kanan (noda), dibaca dengan beberapa variasi.
        no_area = head.crop((int(head.width * 0.15), 0, int(head.width * 0.9), head.height))
        no_kk = _kk_number(cmd, no_area, no_band, folder, pool) if no_band else ""
    data = parse_head_lines(head_lines + foot_text.splitlines())
    # Pasangkan baris tabel atas & bawah dari bawah ke atas (keduanya berisi 10 baris anggota di bagian akhir).
    offset = len(rows_b) - len(rows_a)
    members = []
    for i, raw in enumerate(rows_a):
        if not _is_data_row(raw):
            continue
        row = {key: _normalize(key, value) if key not in DIGIT_COLUMNS else value for key, value in raw.items()}
        j = i + offset
        if 0 <= j < len(rows_b) and _is_data_row(rows_b[j]):
            row.update({key: _normalize(key, value) if key not in DIGIT_COLUMNS else value for key, value in rows_b[j].items()})
        if _is_member(row):
            if not row.get("kewarganegaraan"):
                row["kewarganegaraan"] = "WNI"
            members.append(row)
    data["anggota"] = members[:15]
    data["metode"] = "tabel"
    if no_kk:
        data["no_kk"] = _region_fix(no_kk, [m.get("nik", "") for m in members])
    text_lines = [line for line in head_lines if line]
    for m in members:
        text_lines.append(" | ".join(str(v) for v in m.values() if v))
    text_lines += ["", foot_text.strip()]
    return data, "\n".join(text_lines).strip()


def _prepare_plain(path: str, out_dir: str) -> str:
    """Abu-abu, perbesar bila kecil, kontras & tajamkan: membantu Tesseract membaca fotokopi."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        if img.width < 1800:
            scale = 1800 / img.width
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=1).filter(ImageFilter.SHARPEN)
        return _save(img, out_dir, "input.png")


def read_text(field_file, *, kind: str = "kk") -> OcrResult:
    """OCR sebuah gambar di penyimpanan pribadi. Tidak pernah melempar error ke view."""
    cmd = tesseract_cmd()
    if not cmd:
        return OcrResult(False, message="Mesin pembaca (Tesseract OCR) belum terpasang di server.", available=False)
    if not _LOCK.acquire(timeout=30):
        return OcrResult(False, message="Mesin pembaca sedang dipakai. Tekan 'Baca ulang' sebentar lagi.")
    try:
        with tempfile.TemporaryDirectory(prefix="hp-ocr-") as tmp:
            source = os.path.join(tmp, "source")
            with field_file.storage.open(field_file.name, "rb") as src, open(source, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            with Image.open(source) as probe:
                if probe.width * probe.height > MAX_OCR_PIXELS:
                    raise ValueError("too large")
            structured = None
            if kind == "kk":
                try:
                    structured = _read_structured(cmd, source, tmp)
                except (OSError, subprocess.SubprocessError) as exc:
                    log.warning("OCR tabel KK gagal (%s), pakai pembacaan teks biasa.", type(exc).__name__)
            if structured:
                data, text = structured
            else:
                prepared = _prepare_plain(source, tmp)
                text = _run(cmd, prepared, psm=4 if kind == "ktp" else 6, lang=_lang_arg(cmd)).strip()
                data = parse_ktp(text) if kind == "ktp" else parse_kk(text) if kind == "kk" else {}
            if kind == "kk":
                data = finish_kk(data)
            if not text.strip() and not data.get("anggota"):
                return OcrResult(False, message="Tulisan tidak terbaca. Foto ulang lebih terang, lurus, dan tidak buram.")
    except subprocess.TimeoutExpired:
        return OcrResult(False, message="Pembacaan terlalu lama dan dihentikan. Coba foto dengan ukuran lebih kecil.")
    except (OSError, ValueError) as exc:
        log.warning("OCR error: %s", type(exc).__name__)
        return OcrResult(False, message="Gambar tidak bisa dibaca.")
    finally:
        _LOCK.release()
    return OcrResult(True, text=text[:20000], data=data)


# ---------------------------------------------------------------------------
# Cadangan: parser teks biasa (bila garis tabel tidak terdeteksi) & KTP
# ---------------------------------------------------------------------------
def _after_label(line: str, labels: tuple[str, ...]) -> str | None:
    upper = line.upper()
    for label in labels:
        pos = upper.find(label)
        if pos != -1:
            rest = line[pos + len(label):]
            if ":" in rest[:8]:
                rest = rest.split(":", 1)[1]
            return _clean(rest)
    return None


def parse_ktp(text: str) -> dict:
    data: dict = {}
    niks = find_niks(text)
    if niks:
        data["nik"] = niks[0]
    fields = [
        ("nama", ("NAMA",)),
        ("ttl", ("TEMPAT/TGL LAHIR", "TEMPAT/TGL. LAHIR", "TEMPAT / TGL LAHIR", "TGL LAHIR", "LAHIR")),
        ("alamat", ("ALAMAT",)),
        ("rt_rw", ("RT/RW", "RT / RW")),
        ("kelurahan", ("KEL/DESA", "KEL / DESA", "DESA")),
        ("kecamatan", ("KECAMATAN",)),
        ("pekerjaan", ("PEKERJAAN",)),
        ("status_perkawinan", ("STATUS PERKAWINAN", "PERKAWINAN")),
        ("agama", ("AGAMA",)),
        ("kewarganegaraan", ("KEWARGANEGARAAN",)),
    ]
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        upper = line.upper()
        if "jenis_kelamin" not in data and ("KELAMIN" in upper or "LAKI" in upper or "PEREMPUAN" in upper):
            gender = _gender(line.split("Gol")[0] if "Gol" in line else line)
            if gender:
                data["jenis_kelamin"] = gender
        if "golongan_darah" not in data and re.search(r"gol\.?\s*darah", line, re.I):
            data["golongan_darah"] = _blood(re.split(r"darah\s*:?", line, flags=re.I)[-1])
        for key, labels in fields:
            if key in data:
                continue
            value = _after_label(line, labels)
            if value:
                data[key] = value
                break
    if "ttl" in data:
        ttl = data.pop("ttl")
        data["tanggal_lahir"] = parse_date(ttl)
        data["tempat_lahir"] = _place(re.sub(r"[\d/.-]+", " ", ttl.split(",")[0]))
    if "agama" in data:
        data["agama"] = _pick(data["agama"], RELIGION_WORDS)
    if "status_perkawinan" in data:
        data["status_perkawinan"] = _pick(data["status_perkawinan"], MARITAL_WORDS)
    if "pekerjaan" in data:
        data["pekerjaan"] = _normalize("pekerjaan", data["pekerjaan"])
    if "kewarganegaraan" in data:
        data["kewarganegaraan"] = _normalize("kewarganegaraan", data["kewarganegaraan"])
    if "rt_rw" in data:
        nums = re.findall(r"\d{1,3}", _digits(data.pop("rt_rw")))
        if len(nums) >= 2:
            data["rt"], data["rw"] = nums[0].zfill(3), nums[1].zfill(3)
    if "nama" in data:
        data["nama"] = _name(data["nama"])
    for key in ("alamat", "kelurahan", "kecamatan"):
        if key in data:
            data[key] = data[key].upper()
    return data


def _parse_member_row(line: str, nik: str) -> dict:
    """Satu baris teks tabel KK bagian atas: No | Nama | NIK | JK | Tempat lahir | Tgl lahir | Agama | Pendidikan | Pekerjaan."""
    raw = _digits(line)
    pos = raw.find(nik)
    before = line[:pos] if pos != -1 else ""
    after = line[pos + 16:] if pos != -1 else line
    row = {"nik": nik, "nama": _name(re.sub(r"^\s*\d{1,2}[\s.)|]+", "", before))}
    row["jenis_kelamin"] = _gender(after[:20])
    row["tanggal_lahir"] = parse_date(after)
    row["agama"] = _pick(after, RELIGION_WORDS) if any(w in after.upper() for w in RELIGION_WORDS) else ""
    upper = after.upper()
    edu = next((e for e in EDUCATION_WORDS if e in upper), "")
    row["pendidikan"] = edu
    match = re.search(r"(?:LAKI[- ]?LAKI|PEREMPUAN)\s+([A-Z .'-]{2,40}?)\s+\d{1,2}\s*[-/.]", upper)
    row["tempat_lahir"] = _place(match.group(1)) if match else ""
    if edu:
        job = _clean(upper.split(edu, 1)[1])
        job = re.sub(r"\b(A|B|AB|O|TIDAK TAHU)\s*$", "", job).strip()
        row["pekerjaan"] = _normalize("pekerjaan", job)
    else:
        row["pekerjaan"] = ""
    return row


def parse_kk(text: str) -> dict:
    """Cadangan bila struktur tabel tidak terbaca: pola teks per baris."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    data: dict = parse_head_lines(lines[:25])
    data["anggota"] = []
    niks = find_niks(text)
    if "no_kk" not in data and niks:
        data["no_kk"] = niks[0]
    member_niks = [n for n in niks if n != data.get("no_kk")]
    for nik in member_niks[:15]:
        line = next((ln for ln in lines if nik in _digits(ln)), "")
        if line:
            data["anggota"].append(_parse_member_row(line, nik))
    status_rows = []
    for line in lines:
        upper = line.upper()
        relation = next((v for w, v in RELATION_WORDS if w in upper), "")
        marital = next((v for w, v in MARITAL_WORDS if w in upper), "")
        if relation and marital and re.match(r"^\s*\d{1,2}\b", line):
            status_rows.append((marital, relation))
    for row, (marital, relation) in zip(data["anggota"], status_rows):
        row["status_perkawinan"] = marital
        row["hubungan"] = relation
    data["metode"] = "teks"
    return data


def finish_kk(data: dict) -> dict:
    """Rapikan hasil KK: pastikan ada satu Kepala Keluarga (dari kolom hubungan, atau nama di kepala KK)."""
    members = [m for m in data.get("anggota", []) if isinstance(m, dict)]
    heads = [m for m in members if m.get("hubungan") == "Kepala Keluarga"]
    if members and not heads:
        wanted = data.get("kepala_nama", "")
        best = max(members, key=lambda m: difflib.SequenceMatcher(None, m.get("nama", ""), wanted).ratio()) if wanted else None
        if best is not None and difflib.SequenceMatcher(None, best.get("nama", ""), wanted).ratio() >= 0.75:
            best["hubungan"] = "Kepala Keluarga"
    head = next((m for m in members if m.get("hubungan") == "Kepala Keluarga"), None)
    if head and head.get("nama"):
        data["kepala_nama"] = head["nama"]
    return data
