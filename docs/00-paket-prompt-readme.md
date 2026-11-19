# Paket Prompt — Website HANS Project

Folder ini berisi brief lengkap untuk Claude Code supaya bisa membangun website landing page + pricelist HANS Project (Python + MariaDB, produksi di server Windows).

## Isi

```
hansproject-prompt/
├── README.md                        ← file ini (cara pakai)
├── PROMPT.md                        ← brief utama untuk Claude Code
├── docs/
│   ├── 01-bisnis-dan-harga.md       ← harga, paket, kebijakan (fakta final)
│   ├── 02-brand-dan-desain.md       ← logo, warna, gaya bahasa, target pembaca
│   ├── 03-ide-struktur-halaman.md   ← usulan halaman publik + panel admin (bebas diubah)
│   ├── 04-teknis-dan-instalasi.md   ← Python, venv, MariaDB 3307, .env, batch Windows
│   └── 05-keamanan.md               ← standar keamanan (wajib)
└── assets/
    └── logo-h.png                   ← logo "H" (transparan)
```

## Cara pakai

1. Pastikan MariaDB sudah berjalan di port **3307** di komputer ini, dan Python sudah terpasang.
2. Buat folder kosong untuk proyek website, misalnya `hansproject-web`.
3. Ekstrak isi zip ini ke dalam folder tersebut.
4. Buka terminal di folder itu, lalu jalankan `claude`.
5. Ketik:

   ```
   Baca PROMPT.md dan semua file di folder docs/, lalu kerjakan website-nya.
   ```

6. Claude Code mungkin akan menanyakan user dan password MariaDB. Siapkan datanya.
7. Setelah selesai, baca ringkasan dari Claude Code, terutama:
   - daftar **placeholder** yang perlu diisi (rekening, QRIS, dll.)
   - **langkah keamanan** yang sudah diterapkan
   - **panduan pindah ke server Windows** di README proyek

## Sebelum website dipublikasikan

- Isi rekening dan QRIS lewat panel admin. Kontak cukup username Instagram (@hansproject.app).
- Baca ulang halaman Syarat & Ketentuan dan Kebijakan Privasi. Isinya masih draf.
- Aktifkan verifikasi dua langkah (2FA) untuk akun admin.
- Ikuti panduan pengamanan server Windows (firewall, akun service, izin folder).
