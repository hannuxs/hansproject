@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Hentikan website

sc query "%SERVICE_WEB%" >nul 2>&1
if errorlevel 1 goto :by_pid
net stop "%SERVICE_WEB%" && echo [OK] Service website dihentikan.
if errorlevel 1 echo [INFO] Gagal menghentikan service. Klik kanan stop.bat lalu "Run as administrator".
goto :end

:by_pid
set "PIDFILE=%ROOT%\run\server.pid"
if not exist "%PIDFILE%" (
  echo [INFO] Website tidak sedang berjalan.
  goto :end
)
set /p SERVER_PID=<"%PIDFILE%"
rem Pastikan PID itu memang proses Python (bukan program lain yang kebetulan memakai nomor yang sama).
tasklist /FI "PID eq %SERVER_PID%" /FO CSV /NH | find /I "python" >nul
if errorlevel 1 (
  echo [INFO] Proses website sudah tidak berjalan.
  del "%PIDFILE%" >nul 2>&1
  goto :end
)
taskkill /PID %SERVER_PID% /T /F >nul && echo [OK] Website dihentikan.
del "%PIDFILE%" >nul 2>&1

:end
if /I not "%~1"=="/auto" pause
