@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
title HANS Project - Jadwal backup harian
net session >nul 2>&1
if errorlevel 1 (
  echo [GAGAL] Perlu hak Administrator. Klik kanan file ini lalu "Run as administrator".
  pause
  exit /b 1
)
set "JAM=02:00"
set /p "JAM=Jam backup harian (format HH:MM) [02:00]: "
schtasks /create /f /tn "HANS Project - Backup Harian" /sc daily /st %JAM% /ru SYSTEM /rl HIGHEST /tr "\"%ROOT%\backup.bat\" /auto"
if errorlevel 1 (
  echo [GAGAL] Jadwal tidak bisa dibuat.
) else (
  echo [OK] Backup otomatis setiap hari jam %JAM%. File di folder backups, backup lama dihapus otomatis.
  echo      Cek di Task Scheduler: "HANS Project - Backup Harian".
)
pause
