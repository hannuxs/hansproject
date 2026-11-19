@echo off
rem =========================================================================
rem  HANS PROJECT - server aplikasi (Waitress) di 127.0.0.1:SERVER_PORT (8432)
rem  Dijalankan oleh Windows Service milik Panel HANS (http://127.0.0.1:7777).
rem  HTTPS, domain hansproject.app, dan *.hansproject.app (on-demand TLS)
rem  diurus Caddy milik panel (hp-caddy), BUKAN service-install.bat proyek ini.
rem  Jangan dijalankan bersamaan dengan service-nya (port bentrok).
rem =========================================================================
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
if not exist "%PY%" (
  echo [GAGAL] .venv belum ada. Jalankan install.bat dulu.
  exit /b 1
)
for %%D in (logs run media private) do if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D"
echo [%date% %time%] HANS Project: memeriksa konfigurasi...
"%PY%" manage.py check --deploy --fail-level ERROR || exit /b 1
echo [%date% %time%] HANS Project: Waitress mulai
"%PY%" manage.py serve
exit /b %errorlevel%
