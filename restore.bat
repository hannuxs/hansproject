@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Kembalikan database dari backup
echo ==============================================================
echo   KEMBALIKAN DATABASE DARI BACKUP
echo   Hanya tabel website (hp_*) yang ditimpa. Tabel lain aman.
echo   Sebelum menimpa, kondisi sekarang otomatis di-backup dulu.
echo ==============================================================
echo.
set "BACKUP_FILE=%~1"
if defined BACKUP_FILE goto :have_file
"%PY%" manage.py restore_db
echo.
set /p "BACKUP_FILE=Ketik nama file backup yang ingin dikembalikan (atau kosongkan untuk batal): "
if not defined BACKUP_FILE goto :end

:have_file
set "WAS_SERVICE="
sc query "%SERVICE_WEB%" | find "RUNNING" >nul 2>&1 && set "WAS_SERVICE=1"
if defined WAS_SERVICE net stop "%SERVICE_WEB%"
"%PY%" manage.py restore_db "%BACKUP_FILE%"
if defined WAS_SERVICE net start "%SERVICE_WEB%"

:end
echo.
pause
