@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Lepas Windows Service
net session >nul 2>&1
if errorlevel 1 (
  echo [GAGAL] Perlu hak Administrator. Klik kanan file ini lalu "Run as administrator".
  pause
  exit /b 1
)
for %%S in ("%SERVICE_CADDY%" "%SERVICE_WEB%") do call :remove %%S
echo.
echo [SELESAI] Data, file .env, dan backup TIDAK dihapus.
pause
exit /b 0

:remove
sc query "%~1" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Service %~1 tidak terpasang.
  exit /b 0
)
net stop "%~1" >nul 2>&1
if exist "%ROOT%\tools\winsw\%~1.exe" ("%ROOT%\tools\winsw\%~1.exe" uninstall) else (sc delete "%~1")
echo [OK] Service %~1 dilepas.
exit /b 0
