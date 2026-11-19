@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Backup database
rem Pakai "backup.bat /auto" untuk jadwal otomatis (tanpa jeda di akhir).
echo Backup tabel website (awalan hp_) ke folder backups...
"%PY%" manage.py backup_db
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [GAGAL] Backup tidak berhasil. Baca pesan di atas.
rem Setelah backup berhasil: hapus permanen data yang lewat masa simpannya sesuai
rem Kebijakan Privasi (toko tidak diperpanjang lebih dari 30 hari, pesanan lebih dari
rem 10 tahun, sesi kedaluwarsa). Bila backup gagal, tidak ada yang dihapus.
if "%RC%"=="0" (
  echo Membersihkan data yang sudah lewat masa simpannya...
  "%PY%" manage.py bersihkan_data
)
if /I not "%~1"=="/auto" pause
exit /b %RC%
