@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Buat akun admin / ganti password
"%PY%" manage.py buat_admin
pause
