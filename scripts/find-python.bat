@echo off
rem Mencari Python 3.12 atau lebih baru. Hasil: variabel BASEPY.
set "BASEPY="
for %%V in (3.14 3.13 3.12) do (
  if not defined BASEPY (
    py -%%V -c "import sys" >nul 2>&1 && set "BASEPY=py -%%V"
  )
)
if not defined BASEPY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1 && set "BASEPY=python"
)
if not defined BASEPY (
  echo.
  echo [GAGAL] Python 3.12 atau lebih baru tidak ditemukan.
  echo         Unduh dari https://www.python.org/downloads/windows/
  echo         Saat instalasi centang "Add python.exe to PATH" dan pilih
  echo         "Install for all users" ^(penting untuk Windows Service^).
  exit /b 1
)
for /f "delims=" %%P in ('%BASEPY% -c "import sys; print(sys.version.split()[0])"') do echo [OK] Python %%P ditemukan ^(%BASEPY%^)
exit /b 0
