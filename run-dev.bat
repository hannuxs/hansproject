@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Server pengembangan
echo Server pengembangan: http://127.0.0.1:8432/   (Ctrl+C untuk berhenti)
"%PY%" manage.py runserver 127.0.0.1:8432
pause
