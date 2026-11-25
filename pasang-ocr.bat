@echo off
setlocal EnableExtensions
call "%~dp0scripts\bat-env.bat"
cd /d "%ROOT%"
title HANS Project - Pasang mesin pembaca KK/KTP
echo ==============================================================
echo   PASANG MESIN PEMBACA KK/KTP (Tesseract OCR) UNTUK SIM
echo   Berjalan di server sendiri; foto warga tidak dikirim ke mana pun.
echo ==============================================================

set "TESS=C:\Program Files\Tesseract-OCR\tesseract.exe"
set "DATA=%ROOT%\tools\tessdata"
set "IND_URL=https://github.com/tesseract-ocr/tessdata_best/raw/4.1.0/ind.traineddata"
set "IND_SHA256=1f6596041ffb4cd5094e5f98764db43cfde04edb8f02b988f90ebc1353ac73b8"

echo.
if exist "%TESS%" (
  echo [1/3] Tesseract sudah terpasang.
) else (
  echo [1/3] Memasang Tesseract OCR lewat winget ^(setujui jendela izin administrator bila muncul^)...
  winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements || goto :fail
)
if not exist "%TESS%" (
  echo [GAGAL] tesseract.exe tidak ditemukan di "%TESS%".
  echo         Bila dipasang di tempat lain, isi TESSERACT_CMD di file .env.
  goto :fail
)

echo.
echo [2/3] Menyiapkan data bahasa di tools\tessdata ...
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
echo [3/3] Memeriksa...
"%TESS%" --tessdata-dir "%DATA%" --list-langs || goto :fail
echo.
echo SELESAI. Menu Data warga ^> Scan KK/KTP langsung bisa membaca foto (tidak perlu menjalankan ulang website).
pause
exit /b 0

:fail
echo.
echo Pemasangan belum berhasil. Baca pesan di atas, lalu jalankan file ini lagi.
pause
exit /b 1
