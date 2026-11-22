"""Baca teks dari foto KK/KTP dengan Tesseract OCR (lokal, data tidak keluar server).

Tesseract dipanggil sebagai program terpisah (tanpa shell), dengan batas waktu dan
maksimal SATU proses OCR pada satu waktu, supaya server tetap ringan.

Pemasangan (server Windows): pasang Tesseract (mis. build UB Mannheim) beserta data
bahasa ``ind`` (Indonesia), lalu isi ``TESSERACT_CMD`` di .env bila tidak di lokasi bawaan.
Bila Tesseract belum terpasang, gambar tetap tersimpan dan data diisi manual.

Hasil OCR dari fotokopi KK/KTP tidak pernah sempurna. Parser di bawah hanya membuat
DRAF; pengurus wajib memeriksa & membetulkannya sebelum disimpan sebagai data warga.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess  # nosec B404 - memanggil tesseract dengan argumen list, tanpa shell
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import date

from django.conf import settings
from PIL import Image, ImageFilter, ImageOps

log = logging.getLogger("hans")

_LOCK = threading.BoundedSemaphore(1)
_LANGS: list[str] | None = None
TIMEOUT_SECONDS = 90
MAX_OCR_PIXELS = 30_000_000


@dataclass
class OcrResult:
    ok: bool
    text: str = ""
    message: str = ""
    available: bool = True
    data: dict = field(default_factory=dict)


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


def _languages(cmd: str) -> list[str]:
    global _LANGS
    if _LANGS is None:
        try:
            out = subprocess.run(  # nosec B603 - program & argumen tetap
                [cmd, "--list-langs"], capture_output=True, text=True, timeout=20, check=False
            )
            _LANGS = [line.strip() for line in (out.stdout or "").splitlines()[1:] if line.strip()]
        except (OSError, subprocess.SubprocessError):
            _LANGS = []
    return _LANGS


def _lang_arg(cmd: str) -> str:
    wanted = getattr(settings, "TESSERACT_LANG", "") or "ind+eng"
    have = set(_languages(cmd))
    chosen = [lang for lang in wanted.split("+") if lang in have]
    return "+".join(chosen) or "eng"


def _prepare(path: str, out_dir: str) -> str:
    """Abu-abu, perbesar bila kecil, kontras & tajamkan: membantu Tesseract membaca fotokopi."""
    with Image.open(path) as probe:
        width, height = probe.size
    if width * height > MAX_OCR_PIXELS:
        raise ValueError("Gambar terlalu besar untuk dibaca.")
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        if img.width < 1800:
            scale = 1800 / img.width
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=1).filter(ImageFilter.SHARPEN)
        target = os.path.join(out_dir, "input.png")
        img.save(target, "PNG")
    return target


def read_text(field_file, *, kind: str = "kk") -> OcrResult:
    """OCR sebuah gambar di penyimpanan pribadi. Tidak pernah melempar error ke view."""
    cmd = tesseract_cmd()
    if not cmd:
        return OcrResult(False, message="Mesin OCR (Tesseract) belum terpasang di server.", available=False)
    if not _LOCK.acquire(timeout=20):
        return OcrResult(False, message="Mesin OCR sedang dipakai. Coba tekan 'Baca ulang' sebentar lagi.")
    try:
        with tempfile.TemporaryDirectory(prefix="hp-ocr-") as tmp:
            source = os.path.join(tmp, "source")
            with field_file.storage.open(field_file.name, "rb") as src, open(source, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            prepared = _prepare(source, tmp)
            psm = "4" if kind == "ktp" else "6"
            proc = subprocess.run(  # nosec B603 - argumen list, path file buatan sendiri
                [cmd, prepared, "stdout", "-l", _lang_arg(cmd), "--psm", psm],
                capture_output=True, timeout=TIMEOUT_SECONDS, check=False,
            )
            text = proc.stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0 or not text:
                log.warning("OCR gagal (kode %s).", proc.returncode)
                return OcrResult(False, message="Teks tidak terbaca. Coba foto ulang lebih terang, lurus, dan tidak buram.")
    except subprocess.TimeoutExpired:
        return OcrResult(False, message="Pembacaan terlalu lama dan dihentikan. Coba foto dengan ukuran lebih kecil.")
    except (OSError, ValueError) as exc:
        log.warning("OCR error: %s", type(exc).__name__)
        return OcrResult(False, message="Gambar tidak bisa dibaca.")
    finally:
        _LOCK.release()
    data = parse_ktp(text) if kind == "ktp" else parse_kk(text) if kind == "kk" else {}
    return OcrResult(True, text=text[:20000], data=data)


# ---------------------------------------------------------------------------
# Parser draf (heuristik). Semua hasil harus diperiksa manusia.
# ---------------------------------------------------------------------------
_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1", "|": "1", "!": "1", "S": "5", "B": "8", "Z": "2"})
_NIK = re.compile(r"(?<![0-9A-Za-z])([0-9OoDQIl|!SBZ]{16})(?![0-9A-Za-z])")
_DATE = re.compile(r"(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})")
RELIGION_WORDS = {
    "ISLAM": "Islam", "KRISTEN": "Kristen", "PROTESTAN": "Kristen", "KATOLIK": "Katolik", "KATHOLIK": "Katolik",
    "HINDU": "Hindu", "BUDHA": "Buddha", "BUDDHA": "Buddha", "KONGHUCU": "Konghucu", "KHONGHUCU": "Konghucu",
}
MARITAL_WORDS = [("BELUM KAWIN", "Belum Kawin"), ("CERAI HIDUP", "Cerai Hidup"), ("CERAI MATI", "Cerai Mati"), ("KAWIN", "Kawin")]
RELATION_WORDS = [
    ("KEPALA KELUARGA", "Kepala Keluarga"), ("SUAMI", "Suami"), ("ISTRI", "Istri"), ("ANAK", "Anak"), ("MENANTU", "Menantu"),
    ("CUCU", "Cucu"), ("ORANG TUA", "Orang Tua"), ("MERTUA", "Mertua"), ("FAMILI LAIN", "Famili Lain"), ("PEMBANTU", "Pembantu"),
]
EDUCATION_WORDS = [
    "TIDAK/BELUM SEKOLAH", "BELUM TAMAT SD/SEDERAJAT", "TAMAT SD/SEDERAJAT", "SLTP/SEDERAJAT", "SLTA/SEDERAJAT",
    "DIPLOMA I/II", "AKADEMI/DIPLOMA III/S. MUDA", "DIPLOMA IV/STRATA I", "STRATA II", "STRATA III",
]


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
    match = _DATE.search(_digits(value or "").replace("O", "0"))
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
    value = re.sub(r"\s+", " ", value or "").strip(" :;.,-_|")
    return value


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


def _gender(text: str) -> str:
    upper = text.upper()
    if "PEREMPUAN" in upper or "WANITA" in upper:
        return "P"
    if "LAKI" in upper or "PRIA" in upper:
        return "L"
    return ""


def _first_word(text: str, mapping) -> str:
    upper = text.upper()
    items = mapping.items() if isinstance(mapping, dict) else mapping
    for word, value in items:
        if word in upper:
            return value
    return ""


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
    ]
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        upper = line.upper()
        if "jenis_kelamin" not in data and ("KELAMIN" in upper or "LAKI" in upper or "PEREMPUAN" in upper):
            gender = _gender(line)
            if gender:
                data["jenis_kelamin"] = gender
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
        data["tempat_lahir"] = _clean(re.sub(r"[\d/.-]+", " ", ttl.split(",")[0])).upper()
    if "agama" in data:
        data["agama"] = _first_word(data["agama"], RELIGION_WORDS) or data["agama"].title()
    if "status_perkawinan" in data:
        data["status_perkawinan"] = _first_word(data["status_perkawinan"], MARITAL_WORDS)
    if "rt_rw" in data:
        nums = re.findall(r"\d{1,3}", _digits(data.pop("rt_rw")))
        if len(nums) >= 2:
            data["rt"], data["rw"] = nums[0].zfill(3), nums[1].zfill(3)
    for key in ("nama", "pekerjaan", "alamat", "kelurahan", "kecamatan"):
        if key in data:
            data[key] = data[key].upper()
    return data


def _parse_member_row(line: str, nik: str) -> dict:
    """Satu baris tabel KK bagian atas: No | Nama | NIK | JK | Tempat lahir | Tgl lahir | Agama | Pendidikan | Pekerjaan."""
    raw = _digits(line)
    pos = raw.find(nik)
    before = line[:pos] if pos != -1 else ""
    after = line[pos + 16:] if pos != -1 else line
    name = _clean(re.sub(r"^\s*\d{1,2}[\s.)|]+", "", before))
    row = {"nik": nik, "nama": name.upper()}
    row["jenis_kelamin"] = _gender(after)
    row["tanggal_lahir"] = parse_date(after)
    row["agama"] = _first_word(after, RELIGION_WORDS)
    upper = after.upper()
    edu = next((e for e in EDUCATION_WORDS if e in upper), "")
    row["pendidikan"] = edu.title() if edu else ""
    # tempat lahir: kata setelah jenis kelamin dan sebelum tanggal
    match = re.search(r"(?:LAKI[- ]?LAKI|PEREMPUAN)\s+([A-Z .'-]{2,40}?)\s+\d{1,2}\s*[-/.]", upper)
    row["tempat_lahir"] = _clean(match.group(1)) if match else ""
    if edu:
        job = _clean(upper.split(edu, 1)[1])
        job = re.sub(r"\b(A|B|AB|O|TIDAK TAHU)\s*$", "", job).strip()
        row["pekerjaan"] = job[:60]
    else:
        row["pekerjaan"] = ""
    return row


def parse_kk(text: str) -> dict:
    data: dict = {"anggota": []}
    lines = [line for line in (text or "").splitlines() if line.strip()]
    niks = find_niks(text)
    head_fields = [
        ("kepala_nama", ("NAMA KEPALA KELUARGA", "KEPALA KELUARGA")),
        ("alamat", ("ALAMAT",)),
        ("rt_rw", ("RT/RW", "RT / RW")),
        ("kelurahan", ("DESA/KELURAHAN", "DESA / KELURAHAN", "KELURAHAN")),
        ("kecamatan", ("KECAMATAN",)),
        ("kota", ("KABUPATEN/KOTA", "KABUPATEN / KOTA", "KABUPATEN", "KOTA")),
        ("kode_pos", ("KODE POS",)),
        ("provinsi", ("PROVINSI",)),
    ]
    for line in lines[:25]:
        upper = line.upper()
        if "no_kk" not in data and ("NO" in upper or "KARTU KELUARGA" in upper):
            found = find_niks(line)
            if found:
                data["no_kk"] = found[0]
        for key, labels in head_fields:
            if key in data:
                continue
            value = _after_label(line, labels)
            if value and not find_niks(value):
                data[key] = value
                break
    if "no_kk" not in data and niks:
        data["no_kk"] = niks[0]
    if "rt_rw" in data:
        nums = re.findall(r"\d{1,3}", _digits(data.pop("rt_rw")))
        if len(nums) >= 2:
            data["rt"], data["rw"] = nums[0].zfill(3), nums[1].zfill(3)
    if "kode_pos" in data:
        digits = re.findall(r"\d{5}", _digits(data["kode_pos"]))
        data["kode_pos"] = digits[0] if digits else ""
    for key in ("kepala_nama", "alamat", "kelurahan", "kecamatan", "kota", "provinsi"):
        if key in data:
            data[key] = data[key].upper()[:100]

    member_niks = [n for n in niks if n != data.get("no_kk")]
    for nik in member_niks[:15]:
        line = next((ln for ln in lines if nik in _digits(ln)), "")
        if line:
            data["anggota"].append(_parse_member_row(line, nik))

    # Tabel KK bagian bawah: status perkawinan & hubungan, urut sesuai nomor baris.
    status_rows = []
    for line in lines:
        upper = line.upper()
        relation = _first_word(upper, RELATION_WORDS)
        marital = _first_word(upper, MARITAL_WORDS)
        if relation and marital and re.match(r"^\s*\d{1,2}\b", line):
            status_rows.append((marital, relation))
    for row, (marital, relation) in zip(data["anggota"], status_rows):
        row["status_perkawinan"] = marital
        row["hubungan"] = relation
    if data["anggota"] and not data.get("kepala_nama"):
        head = next((r for r in data["anggota"] if r.get("hubungan") == "Kepala Keluarga"), data["anggota"][0])
        data["kepala_nama"] = head["nama"]
    return data
