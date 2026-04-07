@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title ImageCompare - Builder

echo ============================================================
echo  ImageCompare - Automatyczny builder portable EXE
echo ============================================================
echo.

REM ── 1. Sprawdz / zainstaluj Python 3.11 ─────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Python nie znaleziony - instalowanie przez winget...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [BLAD] Instalacja Pythona nie powiodla sie.
        pause
        exit /b 1
    )
    echo [OK] Python zainstalowany.
    REM Odswiez PATH
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
) else (
    echo [OK] Python juz zainstalowany.
)

REM ── 2. Zainstaluj zaleznosci Python ─────────────────────────
echo.
echo [INFO] Instalowanie bibliotek Python...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pillow pytesseract tkinterdnd2 pyinstaller
if errorlevel 1 (
    echo [BLAD] Instalacja bibliotek nie powiodla sie.
    pause
    exit /b 1
)
echo [OK] Biblioteki zainstalowane.

REM ── 3. Pobierz Tesseract 5.x portable ───────────────────────
echo.
echo [INFO] Pobieranie Tesseract OCR 5.3.3 (UB-Mannheim)...
set "TESS_URL=https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
set "TESS_INSTALLER=%TEMP%\tesseract-setup.exe"
set "TESS_DIR=%~dp0tesseract"

if not exist "%TESS_INSTALLER%" (
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%TESS_URL%' -OutFile '%TESS_INSTALLER%' -UseBasicParsing"
    if errorlevel 1 (
        echo [BLAD] Pobieranie Tesseract nie powiodlo sie.
        pause
        exit /b 1
    )
)
echo [OK] Tesseract pobrany.

echo [INFO] Instalowanie Tesseract do: %TESS_DIR%
if not exist "%TESS_DIR%" mkdir "%TESS_DIR%"
"%TESS_INSTALLER%" /S /D=%TESS_DIR%
if errorlevel 1 (
    echo [BLAD] Instalacja Tesseract nie powiodla sie.
    pause
    exit /b 1
)
echo [OK] Tesseract zainstalowany.

REM ── 4. Przygotuj folder tessdata ─────────────────────────────
echo.
echo [INFO] Pobieranie danych jezykowych (pol+eng)...
set "TESSDATA_DIR=%~dp0tessdata"
if not exist "%TESSDATA_DIR%" mkdir "%TESSDATA_DIR%"

REM pol.traineddata
set "POL_URL=https://github.com/naptha/tessdata/raw/gh-pages/4.0.0_fast/pol.traineddata.gz"
set "POL_GZ=%TEMP%\pol.traineddata.gz"
set "POL_OUT=%TESSDATA_DIR%\pol.traineddata"

if not exist "%POL_OUT%" (
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%POL_URL%' -OutFile '%POL_GZ%' -UseBasicParsing"
    powershell -NoProfile -Command ^
        "$in  = [System.IO.File]::OpenRead('%POL_GZ%');" ^
        "$out = [System.IO.File]::Create('%POL_OUT%');" ^
        "$gz  = New-Object System.IO.Compression.GZipStream($in,[System.IO.Compression.CompressionMode]::Decompress);" ^
        "$gz.CopyTo($out); $gz.Close(); $out.Close(); $in.Close()"
    echo [OK] pol.traineddata
) else (
    echo [SKIP] pol.traineddata juz istnieje
)

REM eng.traineddata
set "ENG_URL=https://github.com/naptha/tessdata/raw/gh-pages/4.0.0_fast/eng.traineddata.gz"
set "ENG_GZ=%TEMP%\eng.traineddata.gz"
set "ENG_OUT=%TESSDATA_DIR%\eng.traineddata"

if not exist "%ENG_OUT%" (
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%ENG_URL%' -OutFile '%ENG_GZ%' -UseBasicParsing"
    powershell -NoProfile -Command ^
        "$in  = [System.IO.File]::OpenRead('%ENG_GZ%');" ^
        "$out = [System.IO.File]::Create('%ENG_OUT%');" ^
        "$gz  = New-Object System.IO.Compression.GZipStream($in,[System.IO.Compression.CompressionMode]::Decompress);" ^
        "$gz.CopyTo($out); $gz.Close(); $out.Close(); $in.Close()"
    echo [OK] eng.traineddata
) else (
    echo [SKIP] eng.traineddata juz istnieje
)

REM ── 5. Kompiluj EXE przez PyInstaller ───────────────────────
echo.
echo [INFO] Kompilowanie EXE (PyInstaller)...
cd /d "%~dp0"

pyinstaller --onefile --windowed ^
    --add-data "tesseract;tesseract" ^
    --add-data "tessdata;tessdata" ^
    --name ImageCompare ^
    image_compare.py

if errorlevel 1 (
    echo [BLAD] PyInstaller nie powiodl sie.
    pause
    exit /b 1
)
echo [OK] EXE skompilowany: dist\ImageCompare.exe

REM ── 6. Przygotuj folder portable ────────────────────────────
echo.
echo [INFO] Tworzenie folderu portable...
set "PORTABLE_DIR=%~dp0dist\ImageCompare"
if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"

copy /Y "%~dp0dist\ImageCompare.exe" "%PORTABLE_DIR%\" >nul
xcopy /E /I /Y "%TESS_DIR%" "%PORTABLE_DIR%\tesseract\" >nul
xcopy /E /I /Y "%TESSDATA_DIR%" "%PORTABLE_DIR%\tessdata\" >nul
echo [OK] Folder portable: %PORTABLE_DIR%

REM ── 7. Spakuj do ZIP ─────────────────────────────────────────
echo.
echo [INFO] Pakowanie do ImageCompare_portable.zip...
set "ZIP_OUT=%~dp0ImageCompare_portable.zip"

if exist "%ZIP_OUT%" del /F /Q "%ZIP_OUT%"

powershell -NoProfile -Command ^
    "Compress-Archive -Path '%PORTABLE_DIR%' -DestinationPath '%ZIP_OUT%' -Force"

if errorlevel 1 (
    echo [BLAD] Tworzenie ZIP nie powiodlo sie.
    pause
    exit /b 1
)

REM ── 8. Podsumowanie ──────────────────────────────────────────
echo.
echo ============================================================
echo  GOTOWE!
echo ============================================================

for %%F in ("%ZIP_OUT%") do (
    set "ZIP_SIZE=%%~zF"
    set "ZIP_PATH=%%~fF"
)

set /a ZIP_KB=!ZIP_SIZE! / 1024
set /a ZIP_MB=!ZIP_KB! / 1024

echo  Plik ZIP : !ZIP_PATH!
if !ZIP_MB! GTR 0 (
    echo  Rozmiar  : !ZIP_MB! MB  (!ZIP_KB! KB)
) else (
    echo  Rozmiar  : !ZIP_KB! KB
)
echo ============================================================
echo.
pause
endlocal
