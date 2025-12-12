# TakibiEsasi Build & Release Rehberi

## Gereksinimler

### Yazılım Gereksinimleri

1. **Python 3.9+**
   - İndirin: https://python.org/downloads

2. **Inno Setup 6**
   - İndirin: https://jrsoftware.org/isdl.php
   - Kurulum sırasında "Turkish" dil paketini seçin

3. **Git** (opsiyonel)
   - İndirin: https://git-scm.com/downloads

### Python Paketleri

```bash
pip install -r requirements.txt
```

## Build İşlemi

### 1. Sadece EXE Oluşturma

```bash
build.bat
```

Çıktı: `dist/TakibiEsasi.exe`

### 2. EXE + Kurulum Paketi Oluşturma

```bash
build_installer.bat
```

Çıktılar:
- `dist/TakibiEsasi.exe` - Bağımsız çalıştırılabilir
- `dist/installer/TakibiEsasi_Setup_X.X.X.exe` - Windows kurulum paketi

## Versiyon Güncelleme

Yeni sürüm yayınlarken aşağıdaki dosyaları güncelleyin:

1. **version.txt** - Ana versiyon numarası
2. **version_info.txt** - Windows dosya bilgileri
3. **installer/setup.iss** - `MyAppVersion` değişkeni
4. **app/updater.py** - `APP_VERSION` sabiti

### Sunucu Tarafı

Sunucuda `releases/latest.json` dosyasını güncelleyin:

```json
{
    "version": "1.1.0",
    "download_url": "https://takibiesasi.com/download/TakibiEsasi_Setup_1.1.0.exe",
    "release_notes": "Yeni özellikler...",
    "release_date": "2024-XX-XX",
    "is_critical": false,
    "min_version": "1.0.0"
}
```

## Uygulama İkonu

Uygulama ikonu eklemek için:

1. 256x256 piksel bir `.ico` dosyası hazırlayın
2. `assets/icon.ico` olarak kaydedin
3. `TakibiEsasi.spec` ve `installer/setup.iss` dosyalarındaki ikon satırlarını aktif edin

## Kod İmzalama (Opsiyonel)

Profesyonel dağıtım için kod imzalama sertifikası önerilir:

1. **EV Code Signing Certificate** satın alın
2. `signtool` ile imzalayın:

```bash
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n "Şirket Adı" dist/TakibiEsasi.exe
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n "Şirket Adı" dist/installer/TakibiEsasi_Setup_*.exe
```

## Dağıtım

1. Build işlemini tamamlayın
2. `TakibiEsasi_Setup_X.X.X.exe` dosyasını sunucuya yükleyin:
   - Yol: `https://takibiesasi.com/download/TakibiEsasi_Setup_X.X.X.exe`
3. `releases/latest.json` dosyasını güncelleyin
4. Admin panelinden duyuru yapın (opsiyonel)

## Sorun Giderme

### PyInstaller Hataları

- **ModuleNotFoundError**: `TakibiEsasi.spec` dosyasındaki `hiddenimports` listesine modülü ekleyin
- **Eksik dosya hatası**: `datas` listesine gerekli dosyaları ekleyin

### Inno Setup Hataları

- **Türkçe karakter sorunu**: Dosyayı UTF-8 BOM ile kaydedin
- **Dosya bulunamadı**: Önce `build.bat` ile EXE oluşturun

### Antivirüs Uyarıları

PyInstaller ile oluşturulan dosyalar bazı antivirüs yazılımlarında yanlış pozitif verebilir. Çözüm:
- Kod imzalama sertifikası kullanın
- VirusTotal'e yükleyip raporu paylaşın
