@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Instalasi
echo ==============================================================
echo   INSTALASI WEBSITE HANS PROJECT (server produksi)
echo   Aman dijalankan ulang: data yang sudah ada tidak dihapus.
echo ==============================================================
echo.

rem --- 1. Python -------------------------------------------------------
echo [1/9] Memeriksa Python...
call "%ROOT%\scripts\find-python.bat" || goto :fail
%BASEPY% "%ROOT%\scripts\envtool.py" check-python || call :warn_userpy

rem --- 2. Virtual environment -----------------------------------------
echo.
echo [2/9] Menyiapkan virtual environment (.venv)...
if exist "%PY%" (
  "%PY%" -c "import sys" >nul 2>&1 || (
    echo [INFO] .venv rusak, dibuat ulang...
    rmdir /s /q "%VENV%"
  )
)
if not exist "%PY%" (
  %BASEPY% -m venv "%VENV%" || goto :fail
)
echo [OK] .venv siap

rem --- 3. Dependensi --------------------------------------------------
echo.
echo [3/9] Memasang dependensi (versi terkunci + cek hash)...
"%PY%" -m pip install --quiet --disable-pip-version-check --upgrade pip || goto :fail
"%PY%" -m pip install --quiet --disable-pip-version-check --require-hashes --only-binary=:all: -r "%ROOT%\requirements\base.txt" || goto :fail
echo [OK] Dependensi terpasang

rem --- 4. File .env ---------------------------------------------------
echo.
echo [4/9] Menyiapkan file konfigurasi .env...
"%PY%" "%ROOT%\scripts\envtool.py" init --mode production || goto :fail
icacls "%ROOT%\.env" /inheritance:r /grant:r "%USERNAME%:F" "%SID_ADMINS%:F" "%SID_SYSTEM%:F" >nul 2>&1 && echo [OK] Akses file .env dibatasi

rem --- 5. Database ----------------------------------------------------
echo.
echo [5/9] Memeriksa database MariaDB...
"%PY%" "%ROOT%\scripts\envtool.py" has DB_PASSWORD || goto :db_menu
"%PY%" manage.py cek_db && goto :db_ok
:db_menu
echo.
echo   Database belum siap. Pilih:
echo   [1] Buat database + user khusus OTOMATIS (perlu password root MariaDB)
echo   [2] Saya isi sendiri DB_USER / DB_PASSWORD di file .env (Notepad dibuka)
echo   [3] Batal
choice /c 123 /n /m "  Pilihan Anda (1/2/3): "
if errorlevel 3 goto :fail
if errorlevel 2 goto :db_manual
"%PY%" "%ROOT%\scripts\db_setup.py" || goto :fail
goto :db_check
:db_manual
start /wait notepad "%ROOT%\.env"
:db_check
"%PY%" manage.py cek_db || goto :db_menu
:db_ok

rem --- 6. Struktur tabel (migrasi) ------------------------------------
echo.
echo [6/9] Membuat/memperbarui tabel (migrasi)...
"%PY%" manage.py migrate --noinput || goto :fail

rem --- 7. Data awal ---------------------------------------------------
echo.
echo [7/9] Mengisi data awal (paket, harga, FAQ)...
"%PY%" manage.py seed_konten || goto :fail

rem --- 8. File statis & folder kerja ----------------------------------
echo.
echo [8/9] Menyiapkan file statis dan folder kerja...
"%PY%" manage.py collectstatic --noinput --verbosity 0 || goto :fail
for %%D in (logs backups media private run) do if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D"
echo [OK] File statis siap

rem --- 9. Akun admin --------------------------------------------------
echo.
echo [9/9] Akun admin panel...
"%PY%" manage.py buat_admin --jika-belum-ada || goto :fail

echo.
echo Pemeriksaan keamanan Django:
"%PY%" manage.py check --deploy
"%PY%" manage.py cek_konten

echo.
echo ==============================================================
echo   INSTALASI SELESAI
echo.
"%PY%" "%ROOT%\scripts\envtool.py" summary
echo.
echo   Langkah berikutnya:
echo     - Coba jalankan     : start.bat
echo     - Jalan otomatis    : service-install.bat (klik kanan, Run as administrator)
echo     - Backup harian     : backup-jadwal.bat   (Run as administrator)
echo ==============================================================
pause
exit /b 0

:warn_userpy
echo [PERINGATAN] Python terpasang di folder pengguna (C:\Users\...).
echo              Windows Service mungkin tidak bisa membacanya.
echo              Disarankan pasang ulang Python dengan "Install for all users".
exit /b 0

:fail
echo.
echo ==============================================================
echo   [GAGAL] Instalasi berhenti. Baca pesan di atas, perbaiki,
echo   lalu jalankan install.bat lagi (aman diulang).
echo ==============================================================
pause
exit /b 1
