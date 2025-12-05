@echo off
REM TakibiEsasi Build Script
REM Bu script, TakibiEsasi uygulamasini Windows icin derler

echo ========================================
echo TakibiEsasi Build Script
echo ========================================
echo.

REM Sanal ortam kontrolu
if exist "venv\Scripts\activate.bat" (
    echo Sanal ortam aktif ediliyor...
    call venv\Scripts\activate.bat
)

REM Gerekli paketlerin kurulumu
echo Bagimliliklar kontrol ediliyor...
pip install -r requirements.txt --quiet

REM Onceki build dosyalarini temizle
echo Onceki build dosyalari temizleniyor...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM PyInstaller ile derle
echo.
echo Uygulama derleniyor...
echo Bu islem birkaç dakika surebilir...
echo.

pyinstaller TakibiEsasi.spec --noconfirm --clean

REM Sonuc kontrolu
if exist "dist\TakibiEsasi.exe" (
    echo.
    echo ========================================
    echo BUILD BASARILI!
    echo ========================================
    echo.
    echo Cikti dosyasi: dist\TakibiEsasi.exe
    echo.

    REM Dosya boyutunu goster
    for %%A in (dist\TakibiEsasi.exe) do (
        set SIZE=%%~zA
        echo Dosya boyutu: %%~zA bytes
    )
    echo.
) else (
    echo.
    echo ========================================
    echo BUILD BASARISIZ!
    echo ========================================
    echo Lutfen hatalari kontrol edin.
    echo.
    exit /b 1
)

pause
