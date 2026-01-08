@echo off
REM TakibiEsasi - Nuitka + Inno Setup Build Script
REM Bu script Nuitka ile derler ve installer olusturur (PyInstaller KULLANMAZ)

echo ============================================
echo TakibiEsasi - Release Build
echo ============================================
echo.
echo UYARI: PyInstaller KULLANILMIYOR
echo        Nuitka + Inno Setup ile derleniyor
echo.

REM Python kontrolu
python --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi!
    pause
    exit /b 1
)

REM Inno Setup kontrolu
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo HATA: Inno Setup 6 bulunamadi!
    echo Yukleyin: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo.
echo [1/3] Nuitka ile derleniyor...
echo       Bu islem 15-30 dakika surebilir.
echo.

python build_windows_protected.py
if errorlevel 1 (
    echo.
    echo HATA: Nuitka build basarisiz!
    pause
    exit /b 1
)

REM Nuitka ciktisi kontrol
if not exist "dist\TakibiEsasi.exe" (
    echo HATA: dist\TakibiEsasi.exe bulunamadi!
    pause
    exit /b 1
)

echo.
echo [2/3] Nuitka build dogrulaniyor...
findstr /C:"PyInstaller" dist\TakibiEsasi.exe >nul 2>&1
if not errorlevel 1 (
    echo HATA: Bu PyInstaller build'i! Nuitka bekleniyor.
    pause
    exit /b 1
)
echo       OK - Nuitka build onaylandi

echo.
echo [3/3] Inno Setup ile installer olusturuluyor...
if not exist "dist\installer" mkdir dist\installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /Q installer\setup.iss

if exist "dist\installer\TakibiEsasi_Setup_*.exe" (
    echo.
    echo ============================================
    echo BUILD BASARILI!
    echo ============================================
    echo.
    echo Cikti dosyalari:
    echo   - dist\TakibiEsasi.exe (Nuitka)
    dir /b dist\installer\*.exe
    echo.
    echo ONEMLI: Bu build tersine muhendislige karsi korumali.
    echo.
) else (
    echo.
    echo UYARI: Installer olusturulamadi!
)

pause
