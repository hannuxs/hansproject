@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Pemeriksaan keamanan
echo === 1. Celah keamanan dependensi (pip-audit) ===
"%PY%" -m pip_audit -r "%ROOT%\requirements\base.txt" --require-hashes
echo.
echo === 2. Analisis kode (bandit) ===
"%PY%" -m bandit -q -r apps config scripts -x "apps/accounts/migrations,apps/content/migrations,apps/members/migrations,apps/pos/migrations,tests"
echo.
echo === 3. Pemeriksaan setelan Django (check --deploy) ===
"%PY%" manage.py check --deploy
echo.
echo Selesai. Butuh dependensi pengembangan (setup-dev.bat) untuk pip-audit dan bandit.
pause
