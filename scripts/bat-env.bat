@echo off
rem ====================================================================
rem  Variabel bersama untuk semua file .bat (dipanggil dengan "call").
rem ====================================================================
chcp 65001 >nul
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SERVICE_WEB=hansproject-web"
set "SERVICE_CADDY=hansproject-caddy"
set "WINSW_URL=https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW.NET461.exe"
set "SID_ADMINS=*S-1-5-32-544"
set "SID_SYSTEM=*S-1-5-18"
exit /b 0
