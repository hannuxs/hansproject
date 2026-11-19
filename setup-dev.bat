@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Setup pengembangan
echo ==============================================================
echo   SETUP KOMPUTER PENGEMBANGAN (bukan untuk server produksi)
echo ==============================================================
call "%ROOT%\scripts\find-python.bat" || goto :fail

if not exist "%PY%" (
  echo Membuat .venv ...
  %BASEPY% -m venv "%VENV%" || goto :fail
)
"%PY%" -m pip install --quiet --disable-pip-version-check --upgrade pip || goto :fail
"%PY%" -m pip install --quiet --disable-pip-version-check --require-hashes --only-binary=:all: -r "%ROOT%\requirements\dev.txt" || goto :fail
echo [OK] Dependensi pengembangan terpasang

if exist "%ROOT%\.env" goto :env_ready
set "DBPORT=3307"
set /p "DBPORT=Port MariaDB di komputer ini [3307]: "
"%PY%" "%ROOT%\scripts\envtool.py" init --mode development --db-port %DBPORT% || goto :fail
:env_ready
"%PY%" "%ROOT%\scripts\envtool.py" init --mode development || goto :fail

"%PY%" "%ROOT%\scripts\envtool.py" has DB_PASSWORD && "%PY%" manage.py cek_db && goto :db_ok
echo.
echo Membuat database + user khusus (juga izin database tes)...
"%PY%" "%ROOT%\scripts\db_setup.py" --dev || goto :fail
"%PY%" manage.py cek_db || goto :fail
:db_ok

"%PY%" manage.py migrate --noinput || goto :fail
"%PY%" manage.py seed_konten || goto :fail
"%PY%" manage.py buat_admin --jika-belum-ada || goto :fail
echo.
echo [SELESAI] Jalankan run-dev.bat lalu buka http://127.0.0.1:8432/
"%PY%" "%ROOT%\scripts\envtool.py" summary
pause
exit /b 0

:fail
echo.
echo [GAGAL] Setup berhenti. Baca pesan di atas.
pause
exit /b 1
