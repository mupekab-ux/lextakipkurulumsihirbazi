@echo off
echo ============================================
echo TakibiEsasi - Nuitka Build
echo ============================================
echo.

REM Nuitka kurulu mu kontrol et
pip show nuitka >nul 2>&1
if errorlevel 1 (
    echo Nuitka kuruluyor...
    pip install nuitka ordered-set zstandard
)

echo.
echo Build basliyor...
echo Bu islem 10-30 dakika surebilir.
echo.

python -m nuitka ^
    --standalone ^
    --onefile ^
    --output-dir=dist_nuitka ^
    --output-filename=TakibiEsasi.exe ^
    --windows-console-mode=disable ^
    --windows-company-name=TakibiEsasi ^
    --windows-product-name=TakibiEsasi ^
    --windows-file-version=1.0.0.0 ^
    --windows-product-version=1.0.0.0 ^
    --windows-file-description="Hukuk Burolari Icin Dava Takip Sistemi" ^
    --enable-plugin=pyqt6 ^
    --include-module=openpyxl ^
    --include-module=bcrypt ^
    --include-module=docx ^
    --include-module=pandas ^
    --include-module=requests ^
    --include-module=sqlite3 ^
    --include-data-dir=app/themes=app/themes ^
    --lto=yes ^
    app/main.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo BUILD BASARISIZ!
    echo ============================================
) else (
    echo.
    echo ============================================
    echo BUILD BASARILI!
    echo Cikti: dist_nuitka\TakibiEsasi.exe
    echo ============================================
)

pause
