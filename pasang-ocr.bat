@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Pasang mesin pembaca KK/KTP
echo ==============================================================
echo   PASANG MESIN PEMBACA KK/KTP UNTUK SIM
echo   1) PaddleOCR (PP-OCRv4 lewat ONNX Runtime) + OpenCV: mesin utama, kuat untuk foto HP
echo      Ada kartu NVIDIA? Otomatis memakai GPU (CUDA 12); bila gagal, kembali ke CPU.
echo   2) Tesseract: cadangan + pemeriksa spasi antarkata
echo   Semua berjalan di server sendiri; foto warga tidak dikirim ke mana pun.
echo ==============================================================
if not exist "%PY%" (
  echo [GAGAL] Website belum diinstal. Jalankan install.bat dulu.
  goto :fail
)

set "TESS=C:\Program Files\Tesseract-OCR\tesseract.exe"
set "DATA=%ROOT%\tools\tessdata"
set "IND_URL=https://github.com/tesseract-ocr/tessdata_best/raw/4.1.0/ind.traineddata"
set "IND_SHA256=1f6596041ffb4cd5094e5f98764db43cfde04edb8f02b988f90ebc1353ac73b8"

echo.
echo [1/4] Memasang PaddleOCR + OpenCV (paket Python, setiap file diperiksa sidik SHA-256)...
set "PIPQ=--quiet --disable-pip-version-check --require-hashes --only-binary=:all:"
set "HAS_NVIDIA="
nvidia-smi -L >nul 2>&1 && set "HAS_NVIDIA=1"
if /i "%OCR_FORCE_CPU%"=="1" set "HAS_NVIDIA="
if defined HAS_NVIDIA (
  echo       Kartu NVIDIA terdeteksi: memasang varian GPU ^(CUDA 12 + cuDNN, unduhan sekitar 1,5 GB^)...
  "%PY%" -m pip uninstall -y --quiet onnxruntime >nul 2>&1
  "%PY%" -m pip install %PIPQ% --no-deps -r "%ROOT%\requirements\ocr-gpu.txt" || goto :fail
  "%PY%" "%ROOT%\scripts\ocr_check.py" --gpu
  if errorlevel 1 (
    echo       GPU belum bisa dipakai ^(mis. driver NVIDIA terlalu lama, butuh versi 528 ke atas^). Memakai CPU.
    "%PY%" -m pip uninstall -y --quiet onnxruntime-gpu >nul 2>&1
    "%PY%" -m pip install %PIPQ% -r "%ROOT%\requirements\ocr.txt" || goto :fail
    "%PY%" "%ROOT%\scripts\ocr_check.py" || goto :fail
  )
) else (
  "%PY%" -m pip uninstall -y --quiet onnxruntime-gpu >nul 2>&1
  "%PY%" -m pip install %PIPQ% -r "%ROOT%\requirements\ocr.txt" || goto :fail
  "%PY%" "%ROOT%\scripts\ocr_check.py" || goto :fail
)

echo.
if exist "%TESS%" (
  echo [2/4] Tesseract sudah terpasang.
) else (
  echo [2/4] Memasang Tesseract OCR lewat winget ^(setujui jendela izin administrator bila muncul^)...
  winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements || goto :fail
)
if not exist "%TESS%" (
  echo [GAGAL] tesseract.exe tidak ditemukan di "%TESS%".
  echo         Bila dipasang di tempat lain, isi TESSERACT_CMD di file .env.
  goto :fail
)

echo.
echo [3/4] Menyiapkan data bahasa Tesseract di tools\tessdata ...
if not exist "%DATA%" mkdir "%DATA%" || goto :fail
copy /y "C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata" "%DATA%\" >nul || goto :fail
copy /y "C:\Program Files\Tesseract-OCR\tessdata\osd.traineddata" "%DATA%\" >nul || goto :fail
if exist "%DATA%\ind.traineddata" (
  echo       Data bahasa Indonesia sudah ada.
) else (
  echo       Mengunduh data bahasa Indonesia...
  curl -fsSL -o "%DATA%\ind.traineddata.partial" "%IND_URL%" || goto :fail
  certutil -hashfile "%DATA%\ind.traineddata.partial" SHA256 | find /i "%IND_SHA256%" >nul
  if errorlevel 1 (
    del "%DATA%\ind.traineddata.partial" >nul 2>&1
    echo [GAGAL] File data bahasa tidak cocok dengan sidik ^(SHA-256^) yang diharapkan. Tidak dipasang.
    goto :fail
  )
  move /y "%DATA%\ind.traineddata.partial" "%DATA%\ind.traineddata" >nul || goto :fail
)

echo.
echo [4/4] Memeriksa...
"%TESS%" --tessdata-dir "%DATA%" --list-langs || goto :fail
echo.
echo SELESAI. Jalankan ulang website (start.bat atau layanan Windows) supaya mesin PaddleOCR dimuat,
echo lalu buka menu Data warga ^> Scan KK/KTP.
pause
exit /b 0

:fail
echo.
echo Pemasangan belum berhasil. Baca pesan di atas, lalu jalankan file ini lagi.
pause
exit /b 1
