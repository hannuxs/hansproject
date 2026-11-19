@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Reset verifikasi dua langkah
echo Pakai ini bila HP berisi aplikasi Authenticator hilang atau diganti.
set /p "ADMIN_USER=Nama pengguna admin: "
if not defined ADMIN_USER goto :end
"%PY%" manage.py reset_2fa "%ADMIN_USER%"
:end
pause
