@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Pembaruan
echo ==============================================================
echo   PEMBARUAN WEBSITE HANS PROJECT
echo   Pastikan file proyek versi baru sudah disalin ke folder ini
echo   (file .env, .venv, media, backups, logs JANGAN ditimpa).
echo ==============================================================
if not exist "%PY%" (
  echo [GAGAL] Belum diinstal. Jalankan install.bat dulu.
  goto :fail
)

echo.
echo [1/6] Backup database (wajib sebelum pembaruan)...
"%PY%" manage.py backup_db --label sebelum-update || goto :fail

echo.
echo [2/6] Menghentikan website...
set "WAS_SERVICE="
sc query "%SERVICE_WEB%" | find "RUNNING" >nul 2>&1 && set "WAS_SERVICE=1"
if defined WAS_SERVICE (
  net stop "%SERVICE_WEB%" || goto :need_admin
) else (
  call "%ROOT%\stop.bat" /auto
)

echo.
echo [3/6] Memasang dependensi baru...
"%PY%" -m pip install --quiet --disable-pip-version-check --require-hashes --only-binary=:all: -r "%ROOT%\requirements\base.txt" || goto :fail

echo.
echo [4/6] Memperbarui struktur tabel (migrasi)...
"%PY%" manage.py migrate --noinput || goto :fail

echo.
echo [5/6] Menyiapkan ulang file statis...
rem File statis versi lama sengaja TIDAK dihapus: pengunjung yang masih membuka
rem halaman versi lama tetap mendapat tampilan lengkap.
"%PY%" manage.py collectstatic --noinput --verbosity 0 || goto :fail

echo.
echo [6/6] Pemeriksaan keamanan...
"%PY%" manage.py check --deploy --fail-level ERROR || goto :fail

if defined WAS_SERVICE (
  net start "%SERVICE_WEB%" && echo [OK] Website berjalan lagi.
) else (
  echo [INFO] Jalankan start.bat untuk menyalakan website.
)
echo.
echo [SELESAI] Pembaruan berhasil.
pause
exit /b 0

:need_admin
echo [GAGAL] Tidak bisa menghentikan service. Klik kanan update.bat lalu "Run as administrator".
:fail
echo.
echo [GAGAL] Pembaruan berhenti. Data aman: backup sudah dibuat di folder backups.
echo         Bila website bermasalah, kembalikan dengan restore.bat.
pause
exit /b 1
