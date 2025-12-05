# TakibiEsasi

1) Python 3.12 kurun
2) Gerekli paketleri yükleyin:
   pip install -r requirements.txt  # PyQt6, openpyxl, bcrypt, python-docx ve pandas içerir
3) TakibiEsasi uygulamasını çalıştırmak için:
   python app/main.py
4) Tek .exe (TakibiEsasi.exe) üretmek için:
   build.bat dosyasını çalıştırın

Notlar:
- İlk çalıştırmada `data.db` otomatik oluşturulur.
- İlk giriş için varsayılan kullanıcı adı/parola `admin / admin`.
- Dosyalar arşivlenerek ana listeden ayrılabilir ve Arşiv sekmesinden geri alınabilir.

Geliştirici: Musa İpek

tüm meslektaşlara başarılar

## Değişiklik Özeti

- Finans kayıtlarını güncelleyen sorgulardaki biçimlendirme hatası giderildi ve işlemler için kapsamlı loglama eklendi.
- Finans sözleşmesi formu güncelleme sonrasında kayıt bulunamadığında uyarı gösteriyor ve sonuç uygulama tablolarına yansıyor.
- ``tests/test_finance_update.py`` ile güncelleme senaryolarını doğrulayan birim testleri ve ``scripts/smoke_update_finance.py`` smoke testi eklendi.
