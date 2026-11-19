@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Pasang Windows Service
echo ==============================================================
echo   PASANG WEBSITE SEBAGAI WINDOWS SERVICE
echo   Website otomatis jalan saat server dinyalakan ulang, memakai
echo   akun Windows khusus berhak terbatas (NT SERVICE\%SERVICE_WEB%).
echo ==============================================================

net session >nul 2>&1
if errorlevel 1 (
  echo [GAGAL] Perlu hak Administrator. Klik kanan file ini lalu "Run as administrator".
  goto :fail
)
if not exist "%PY%" (
  echo [GAGAL] Belum diinstal. Jalankan install.bat dulu.
  goto :fail
)
"%PY%" manage.py check --deploy --fail-level ERROR || goto :fail

rem --- WinSW (pembungkus service) --------------------------------------
set "WSDIR=%ROOT%\tools\winsw"
if not exist "%WSDIR%" mkdir "%WSDIR%"
if exist "%WSDIR%\WinSW.exe" goto :have_winsw
echo.
echo Mengunduh WinSW v2.12.0 dari GitHub resmi...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing -Uri '%WINSW_URL%' -OutFile '%WSDIR%\WinSW.exe'"
if not exist "%WSDIR%\WinSW.exe" (
  echo [GAGAL] Unduhan gagal. Unduh manual: %WINSW_URL%
  echo         lalu simpan sebagai: %WSDIR%\WinSW.exe
  goto :fail
)
:have_winsw

rem --- Folder kerja ---------------------------------------------------
for %%D in (logs logs\service backups media private run staticfiles) do if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D"

rem --- Service website ------------------------------------------------
call :install_service "%SERVICE_WEB%" web || goto :fail

rem --- Hak akses folder untuk akun service --------------------------------
set "ACCT=NT SERVICE\%SERVICE_WEB%"
echo.
echo Mengatur hak akses folder untuk %ACCT% ...
icacls "%ROOT%" /grant "%ACCT%:(OI)(CI)RX" /T /C /Q >nul
for %%D in (logs run media staticfiles) do icacls "%ROOT%\%%D" /grant "%ACCT%:(OI)(CI)M" /T /C /Q >nul
rem File .env, folder backup & log: hanya akun service, Administrator, SYSTEM.
icacls "%ROOT%\.env" /inheritance:r /grant:r "%ACCT%:R" "%SID_ADMINS%:F" "%SID_SYSTEM%:F" /C /Q >nul
icacls "%ROOT%\backups" /inheritance:r /grant:r "%SID_ADMINS%:(OI)(CI)F" "%SID_SYSTEM%:(OI)(CI)F" /C /Q >nul
icacls "%ROOT%\logs" /inheritance:r /grant:r "%ACCT%:(OI)(CI)M" "%SID_ADMINS%:(OI)(CI)F" "%SID_SYSTEM%:(OI)(CI)F" /C /Q >nul
rem Folder upload: boleh tulis, tapi TIDAK boleh menjalankan program.
icacls "%ROOT%\media" /deny "%ACCT%:(OI)(IO)(X)" /C /Q >nul
rem Bukti bayar pelanggan: hanya service, Administrators, dan SYSTEM yang boleh membuka.
icacls "%ROOT%\private" /inheritance:r /grant:r "%ACCT%:(OI)(CI)M" "%SID_ADMINS%:(OI)(CI)F" "%SID_SYSTEM%:(OI)(CI)F" /C /Q >nul
icacls "%ROOT%\private" /deny "%ACCT%:(OI)(IO)(X)" /C /Q >nul
echo [OK] Hak akses diatur

rem --- Service Caddy (HTTPS), bila tersedia ------------------------------
if not exist "%ROOT%\tools\caddy\caddy.exe" (
  echo.
  echo [INFO] tools\caddy\caddy.exe belum ada: service HTTPS Caddy dilewati.
  echo        Lihat README bagian "HTTPS dengan Caddy".
  goto :start
)
if not exist "%ROOT%\deploy\caddy\Caddyfile" copy "%ROOT%\deploy\caddy\Caddyfile.example" "%ROOT%\deploy\caddy\Caddyfile" >nul
for %%D in (data config) do if not exist "%ROOT%\tools\caddy\%%D" mkdir "%ROOT%\tools\caddy\%%D"
call :install_service "%SERVICE_CADDY%" caddy || goto :fail
icacls "%ROOT%\tools\caddy" /grant "NT SERVICE\%SERVICE_CADDY%:(OI)(CI)M" /T /C /Q >nul
icacls "%ROOT%\logs\service" /grant "NT SERVICE\%SERVICE_CADDY%:(OI)(CI)M" /T /C /Q >nul
icacls "%ROOT%\deploy\caddy" /grant "NT SERVICE\%SERVICE_CADDY%:(OI)(CI)RX" /T /C /Q >nul

:start
echo.
net start "%SERVICE_WEB%" || goto :fail
sc query "%SERVICE_CADDY%" >nul 2>&1 && net start "%SERVICE_CADDY%"
echo.
echo [SELESAI] Service terpasang dan berjalan. Cek: services.msc
echo           Log service: logs\service\
pause
exit /b 0

rem ====================================================================
:install_service
rem %1 = nama service, %2 = jenis (web / caddy)
set "SVC=%~1"
set "SVCEXE=%WSDIR%\%SVC%.exe"
sc query "%SVC%" >nul 2>&1
if not errorlevel 1 (
  echo [INFO] Service %SVC% sudah ada, dipasang ulang dengan konfigurasi terbaru...
  net stop "%SVC%" >nul 2>&1
  "%SVCEXE%" uninstall >nul 2>&1
)
copy /y "%WSDIR%\WinSW.exe" "%SVCEXE%" >nul || exit /b 1
set "DEPENDS="
if /I "%~2"=="web" sc query MariaDB >nul 2>&1 && set "DEPENDS=MariaDB"
"%PY%" "%ROOT%\scripts\make_service_xml.py" %~2 "%WSDIR%\%SVC%.xml" %DEPENDS% || exit /b 1
"%SVCEXE%" install || exit /b 1
rem Akun virtual Windows khusus service ini (tanpa password, hak terbatas).
sc config "%SVC%" obj= "NT SERVICE\%SVC%" >nul || exit /b 1
echo [OK] Service %SVC% terpasang (akun: NT SERVICE\%SVC%)
exit /b 0

:fail
echo.
echo [GAGAL] Pemasangan service berhenti. Baca pesan di atas.
pause
exit /b 1
