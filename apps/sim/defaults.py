"""Format surat bawaan untuk wilayah baru.

Disusun dari jenis surat yang umum dilayani RT/RW dan kelurahan (surat pengantar,
domisili, berkelakuan baik untuk SKCK/pendaftaran TNI-Polri, SKTM, usaha, belum menikah,
kematian, kelahiran, pindah, kehilangan, izin keramaian, penghasilan, ahli waris).
Syarat dan bentuk surat berbeda di tiap daerah, jadi SEMUA format ini bisa diubah
pengurus (isi, judul, kolom isian), dihapus, atau ditambah sendiri.

Isian standar yang selalu ada di formulir: {nama} {nik} {jenis_kelamin} {tempat_lahir}
{tanggal_lahir} {agama} {pekerjaan} {status_perkawinan} {kewarganegaraan} {alamat} {keperluan}.
Isian otomatis: {nama_wilayah} {jabatan} {penanda_tangan} {tanggal_surat} {tempat_surat}.

Baris berbentuk "Label : {isian}" dirapikan otomatis menjadi tabel saat dicetak.
"""
from __future__ import annotations

from .models import LEVEL_KECAMATAN, LEVEL_KELURAHAN

DATA_DIRI = """Nama : {nama}
NIK : {nik}
Jenis Kelamin : {jenis_kelamin}
Tempat/Tgl. Lahir : {tempat_lahir}, {tanggal_lahir}
Agama : {agama}
Status Perkawinan : {status_perkawinan}
Pekerjaan : {pekerjaan}
Kewarganegaraan : {kewarganegaraan}
Alamat : {alamat}"""

PEMBUKA = "Yang bertanda tangan di bawah ini, {jabatan} {nama_wilayah}, dengan ini menerangkan bahwa:"
PENUTUP = "Demikian surat ini dibuat dengan sebenarnya untuk dapat dipergunakan sebagaimana mestinya."


def _body(middle: str, extra: str = "") -> str:
    parts = [PEMBUKA, DATA_DIRI, middle]
    if extra:
        parts.append(extra)
    parts.append(PENUTUP)
    return "\n\n".join(parts)


def _f(key: str, label: str, kind: str = "teks", required: bool = True) -> dict:
    return {"key": key, "label": label, "type": kind, "required": required}


TEMPLATES = [
    {
        "kode": "pengantar",
        "nama": "Surat Pengantar",
        "judul": "SURAT PENGANTAR",
        "kode_surat": "SP",
        "keterangan": "Pengantar ke kelurahan/instansi untuk mengurus KTP, KK, SKCK, nikah, dan keperluan lain.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Orang tersebut di atas adalah benar warga kami yang berdomisili di wilayah {nama_wilayah}. "
            "Surat pengantar ini diberikan untuk keperluan: {keperluan}."
        ),
        "kolom": [],
    },
    {
        "kode": "domisili",
        "nama": "Surat Keterangan Domisili",
        "judul": "SURAT KETERANGAN DOMISILI",
        "kode_surat": "SKD",
        "keterangan": "Menerangkan tempat tinggal (misalnya bagi warga yang KTP-nya dari daerah lain).",
        "butuh_mengetahui": False,
        "isi": _body(
            "Orang tersebut di atas benar berdomisili di {alamat_domisili} wilayah {nama_wilayah} sejak {sejak}. "
            "Surat keterangan ini dibuat untuk keperluan: {keperluan}."
        ),
        "kolom": [_f("alamat_domisili", "Alamat tempat tinggal sekarang"), _f("sejak", "Tinggal di sini sejak (bulan/tahun)")],
    },
    {
        "kode": "kelakuan-baik",
        "nama": "Surat Keterangan Berkelakuan Baik",
        "judul": "SURAT KETERANGAN BERKELAKUAN BAIK",
        "kode_surat": "SKBB",
        "keterangan": "Untuk pengantar SKCK, melamar kerja, atau pendaftaran calon siswa TNI/Polri.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Sepanjang pengetahuan kami, orang tersebut di atas adalah warga kami yang berkelakuan baik, "
            "tidak pernah terlibat tindak pidana, dan tidak sedang dalam proses hukum. "
            "Surat keterangan ini diberikan untuk keperluan: {keperluan}."
        ),
        "kolom": [],
    },
    {
        "kode": "tidak-mampu",
        "nama": "Surat Keterangan Tidak Mampu (SKTM)",
        "judul": "SURAT KETERANGAN TIDAK MAMPU",
        "kode_surat": "SKTM",
        "keterangan": "Untuk keringanan biaya sekolah, berobat, atau bantuan sosial.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Orang tersebut di atas adalah benar warga kami yang termasuk keluarga kurang mampu "
            "dengan penghasilan keluarga kurang lebih {penghasilan} per bulan dan tanggungan {tanggungan} orang. "
            "Surat keterangan ini diberikan untuk keperluan: {keperluan}."
        ),
        "kolom": [_f("penghasilan", "Perkiraan penghasilan keluarga per bulan (Rp)"), _f("tanggungan", "Jumlah tanggungan keluarga")],
    },
    {
        "kode": "usaha",
        "nama": "Surat Keterangan Usaha",
        "judul": "SURAT KETERANGAN USAHA",
        "kode_surat": "SKU",
        "keterangan": "Untuk pengajuan pinjaman/KUR, izin usaha mikro, atau keperluan usaha lain.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Orang tersebut di atas benar memiliki usaha dengan keterangan sebagai berikut:\n\n"
            "Nama Usaha : {nama_usaha}\nJenis Usaha : {jenis_usaha}\nAlamat Usaha : {alamat_usaha}\nBerdiri Sejak : {mulai_usaha}\n\n"
            "Surat keterangan ini diberikan untuk keperluan: {keperluan}."
        ),
        "kolom": [
            _f("nama_usaha", "Nama usaha"),
            _f("jenis_usaha", "Jenis usaha"),
            _f("alamat_usaha", "Alamat usaha"),
            _f("mulai_usaha", "Usaha berdiri sejak (tahun)"),
        ],
    },
    {
        "kode": "belum-menikah",
        "nama": "Surat Keterangan Belum Menikah",
        "judul": "SURAT KETERANGAN BELUM PERNAH MENIKAH",
        "kode_surat": "SKBM",
        "keterangan": "Untuk melamar kerja, pendaftaran TNI/Polri, atau persyaratan nikah.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Sepanjang pengetahuan kami, orang tersebut di atas sampai saat ini belum pernah menikah. "
            "Surat keterangan ini diberikan untuk keperluan: {keperluan}."
        ),
        "kolom": [],
    },
    {
        "kode": "kematian",
        "nama": "Surat Keterangan Kematian",
        "judul": "SURAT KETERANGAN KEMATIAN",
        "kode_surat": "SKK",
        "keterangan": "Dibuat oleh keluarga/pelapor untuk mengurus akta kematian, ahli waris, atau asuransi.",
        "butuh_mengetahui": True,
        "isi": (
            "Yang bertanda tangan di bawah ini, {jabatan} {nama_wilayah}, menerangkan bahwa telah meninggal dunia:\n\n"
            "Nama : {nama_almarhum}\nNIK : {nik_almarhum}\nHari/Tanggal : {tanggal_meninggal}\nTempat : {tempat_meninggal}\n"
            "Sebab : {sebab_meninggal}\n\nKeterangan ini dibuat berdasarkan laporan dari:\n\n" + DATA_DIRI + "\n"
            "Hubungan dengan Almarhum/ah : {hubungan_pelapor}\n\n" + PENUTUP
        ),
        "kolom": [
            _f("nama_almarhum", "Nama almarhum/almarhumah"),
            _f("nik_almarhum", "NIK almarhum/almarhumah", required=False),
            _f("tanggal_meninggal", "Hari & tanggal meninggal"),
            _f("tempat_meninggal", "Tempat meninggal"),
            _f("sebab_meninggal", "Sebab meninggal", required=False),
            _f("hubungan_pelapor", "Hubungan pelapor dengan almarhum/ah"),
        ],
    },
    {
        "kode": "kelahiran",
        "nama": "Surat Keterangan Kelahiran",
        "judul": "SURAT KETERANGAN KELAHIRAN",
        "kode_surat": "SKL",
        "keterangan": "Untuk mengurus akta kelahiran dan penambahan anggota KK.",
        "butuh_mengetahui": False,
        "isi": (
            "Yang bertanda tangan di bawah ini, {jabatan} {nama_wilayah}, menerangkan bahwa telah lahir seorang anak:\n\n"
            "Nama Anak : {nama_anak}\nJenis Kelamin : {jk_anak}\nTempat/Tgl. Lahir : {tempat_lahir_anak}, {tanggal_lahir_anak}\n"
            "Nama Ayah : {nama_ayah}\nNama Ibu : {nama_ibu}\n\nKeterangan ini dibuat berdasarkan laporan dari:\n\n"
            + DATA_DIRI + "\n\n" + PENUTUP
        ),
        "kolom": [
            _f("nama_anak", "Nama anak"),
            _f("jk_anak", "Jenis kelamin anak"),
            _f("tempat_lahir_anak", "Tempat lahir anak"),
            _f("tanggal_lahir_anak", "Tanggal lahir anak"),
            _f("nama_ayah", "Nama ayah"),
            _f("nama_ibu", "Nama ibu"),
        ],
    },
    {
        "kode": "pindah",
        "nama": "Surat Pengantar Pindah",
        "judul": "SURAT PENGANTAR PINDAH",
        "kode_surat": "SPP",
        "keterangan": "Pengantar bagi warga yang akan pindah tempat tinggal.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Orang tersebut di atas bermaksud pindah tempat tinggal dengan keterangan sebagai berikut:\n\n"
            "Alamat Tujuan : {alamat_tujuan}\nAlasan Pindah : {alasan_pindah}\nJumlah Anggota Keluarga yang Ikut : {jumlah_ikut}"
        ),
        "kolom": [
            _f("alamat_tujuan", "Alamat tujuan pindah", "paragraf"),
            _f("alasan_pindah", "Alasan pindah"),
            _f("jumlah_ikut", "Jumlah anggota keluarga yang ikut pindah"),
        ],
    },
    {
        "kode": "kehilangan",
        "nama": "Surat Keterangan Kehilangan",
        "judul": "SURAT KETERANGAN KEHILANGAN",
        "kode_surat": "SKH",
        "keterangan": "Pengantar laporan kehilangan barang/dokumen ke kepolisian atau instansi.",
        "butuh_mengetahui": False,
        "isi": _body(
            "Orang tersebut di atas telah melaporkan kehilangan dengan keterangan sebagai berikut:\n\n"
            "Barang/Dokumen yang Hilang : {barang_hilang}\nWaktu Kehilangan : {waktu_hilang}\nTempat Kehilangan : {tempat_hilang}"
        ),
        "kolom": [
            _f("barang_hilang", "Barang/dokumen yang hilang"),
            _f("waktu_hilang", "Waktu kehilangan"),
            _f("tempat_hilang", "Perkiraan tempat kehilangan"),
        ],
    },
    {
        "kode": "izin-keramaian",
        "nama": "Surat Pemberitahuan/Izin Keramaian",
        "judul": "SURAT KETERANGAN IZIN KERAMAIAN",
        "kode_surat": "SIK",
        "keterangan": "Untuk hajatan, pernikahan, syukuran, atau acara yang mengundang keramaian.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Orang tersebut di atas akan menyelenggarakan acara dengan keterangan sebagai berikut:\n\n"
            "Nama Acara : {nama_acara}\nHari/Tanggal : {tanggal_acara}\nTempat : {tempat_acara}\nHiburan : {hiburan}\n\n"
            "Pada prinsipnya kami tidak keberatan, dengan ketentuan penyelenggara menjaga ketertiban dan kebersihan lingkungan."
        ),
        "kolom": [
            _f("nama_acara", "Nama acara"),
            _f("tanggal_acara", "Hari, tanggal & jam acara"),
            _f("tempat_acara", "Tempat acara"),
            _f("hiburan", "Hiburan (bila ada)", required=False),
        ],
    },
    {
        "kode": "penghasilan",
        "nama": "Surat Keterangan Penghasilan",
        "judul": "SURAT KETERANGAN PENGHASILAN",
        "kode_surat": "SKP",
        "keterangan": "Untuk beasiswa, keringanan biaya, atau persyaratan administrasi lain.",
        "butuh_mengetahui": True,
        "isi": _body(
            "Orang tersebut di atas benar memiliki penghasilan kurang lebih {penghasilan} per bulan dari pekerjaan sebagai {pekerjaan}. "
            "Surat keterangan ini diberikan untuk keperluan: {keperluan}."
        ),
        "kolom": [_f("penghasilan", "Perkiraan penghasilan per bulan (Rp)")],
    },
]

# Hanya ditambahkan untuk kelurahan/desa & kecamatan.
UPPER_TEMPLATES = [
    {
        "kode": "ahli-waris",
        "nama": "Surat Keterangan Ahli Waris",
        "judul": "SURAT KETERANGAN AHLI WARIS",
        "kode_surat": "SKAW",
        "keterangan": "Penandatanganan/pengesahan keterangan ahli waris (syarat & kewenangan mengikuti aturan daerah).",
        "butuh_mengetahui": False,
        "isi": (
            "Yang bertanda tangan di bawah ini, {jabatan} {nama_wilayah}, menerangkan bahwa almarhum/almarhumah "
            "{nama_almarhum} yang meninggal dunia pada {tanggal_meninggal} meninggalkan ahli waris sebagai berikut:\n\n"
            "{daftar_ahli_waris}\n\nKeterangan ini dibuat berdasarkan permohonan dari:\n\n" + DATA_DIRI + "\n\n" + PENUTUP
        ),
        "kolom": [
            _f("nama_almarhum", "Nama pewaris (almarhum/ah)"),
            _f("tanggal_meninggal", "Tanggal meninggal"),
            _f("daftar_ahli_waris", "Daftar ahli waris (nama, hubungan, satu per baris)", "paragraf"),
        ],
    },
]


def templates_for(level: str) -> list[dict]:
    items = list(TEMPLATES)
    if level in (LEVEL_KELURAHAN, LEVEL_KECAMATAN):
        items += UPPER_TEMPLATES
    return items
