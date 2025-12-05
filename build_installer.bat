@echo off
REM TakibiEsasi Tam Build Script
REM Bu script, TakibiEsasi uygulamasini derler ve kurulum paketi olusturur

echo ========================================
echo TakibiEsasi Tam Build Script
echo ========================================
echo.

REM Python kontrolu
python --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi!
    echo Lutfen Python 3.9+ yukleyin.
    pause
    exit /b 1
)

REM Inno Setup kontrolu
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo UYARI: Inno Setup bulunamadi!
    echo Kurulum paketi olusturulamayacak.
    echo Inno Setup 6'yi yukleyin: https://jrsoftware.org/isdl.php
    set INNO_FOUND=0
) else (
    set INNO_FOUND=1
)

REM Sanal ortam kontrolu
if exist "venv\Scripts\activate.bat" (
    echo Sanal ortam aktif ediliyor...
    call venv\Scripts\activate.bat
)

REM Bagimliklar
echo.
echo [1/4] Bagimliliklar kontrol ediliyor...
pip install -r requirements.txt --quiet

REM Build dizinlerini temizle
echo.
echo [2/4] Onceki build dosyalari temizleniyor...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM PyInstaller ile derle
echo.
echo [3/4] Uygulama derleniyor...
echo Bu islem birkaç dakika surebilir...
pyinstaller TakibiEsasi.spec --noconfirm --clean

if not exist "dist\TakibiEsasi.exe" (
    echo.
    echo HATA: PyInstaller derlemesi basarisiz!
    pause
    exit /b 1
)

echo.
echo PyInstaller derlemesi basarili!
for %%A in (dist\TakibiEsasi.exe) do echo EXE boyutu: %%~zA bytes

REM Inno Setup ile kurulum paketi
if "%INNO_FOUND%"=="1" (
    echo.
    echo [4/4] Kurulum paketi olusturuluyor...
    if not exist "dist\installer" mkdir dist\installer
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /Q installer\setup.iss

    if exist "dist\installer\TakibiEsasi_Setup_*.exe" (
        echo.
        echo ========================================
        echo KURULUM PAKETI OLUSTURULDU!
        echo ========================================
        echo.
        dir /b dist\installer\*.exe
        echo.
    ) else (
        echo.
        echo UYARI: Kurulum paketi olusturulamadi!
    )
) else (
    echo.
    echo [4/4] Kurulum paketi atlandi (Inno Setup bulunamadi)
)

echo.
echo ========================================
echo BUILD TAMAMLANDI!
echo ========================================
echo.
echo Cikti dosyalari:
echo   - dist\TakibiEsasi.exe (Bagimsiz calistirilabilir)
if "%INNO_FOUND%"=="1" (
    echo   - dist\installer\TakibiEsasi_Setup_*.exe (Kurulum paketi)
)
echo.

pause
