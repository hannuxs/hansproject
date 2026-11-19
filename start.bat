@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Website
if not exist "%PY%" (
  echo [GAGAL] Belum diinstal. Jalankan install.bat dulu.
  goto :end
)

sc query "%SERVICE_WEB%" >nul 2>&1
if not errorlevel 1 goto :as_service

echo Memeriksa konfigurasi...
"%PY%" manage.py check --deploy --fail-level ERROR || goto :end
"%PY%" manage.py cek_konten
echo.
echo Menjalankan website. JANGAN tutup jendela ini selama website dipakai.
echo Untuk berhenti: tekan Ctrl+C, atau jalankan stop.bat
echo.
"%PY%" manage.py serve
goto :end

:as_service
echo Website terpasang sebagai Windows Service "%SERVICE_WEB%".
net start "%SERVICE_WEB%" 2>nul && echo [OK] Service dijalankan.
sc query "%SERVICE_WEB%" | find "RUNNING" >nul && echo [OK] Website sedang berjalan. || echo [INFO] Bila gagal, klik kanan start.bat lalu "Run as administrator".

:end
echo.
pause
