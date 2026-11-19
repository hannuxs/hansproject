@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Tes otomatis
set "APP_ENV=test"
"%PY%" manage.py test --noinput %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (echo [OK] Semua tes lulus.) else (echo [GAGAL] Ada tes yang gagal.)
pause
exit /b %RC%
