# LexTakip Sunucu

Raspberry Pi üzerinde çalışacak senkronizasyon sunucusu.

## Kurulum (Raspberry Pi)

### 1. PostgreSQL Kurulumu

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# PostgreSQL servisini başlat
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Veritabanı ve kullanıcı oluştur
sudo -u postgres psql
```

PostgreSQL içinde:
```sql
CREATE USER lextakip WITH PASSWORD 'lextakip123';
CREATE DATABASE lextakip OWNER lextakip;
GRANT ALL PRIVILEGES ON DATABASE lextakip TO lextakip;
\q
```

### 2. Python Ortamı

```bash
# Python ve pip kurulumu
sudo apt install python3 python3-pip python3-venv

# Proje dizinine git
cd /home/pi/lextakip-server

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları kur
pip install -r requirements.txt
```

### 3. Ortam Değişkenleri

`.env` dosyası oluştur:
```bash
DATABASE_URL=postgresql://lextakip:lextakip123@localhost:5432/lextakip
SECRET_KEY=buraya-guclu-bir-anahtar-yaz-32-karakter-min
SERVER_HOST=0.0.0.0
SERVER_PORT=8787
DEBUG=false
```

### 4. Sunucuyu Başlat

```bash
# Manuel başlatma
source venv/bin/activate
python main.py

# Veya uvicorn ile
uvicorn main:app --host 0.0.0.0 --port 8787
```

### 5. Systemd Servisi (Otomatik Başlatma)

`/etc/systemd/system/lextakip.service` dosyası oluştur:

```ini
[Unit]
Description=LexTakip Sync Server
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/lextakip-server
Environment=PATH=/home/pi/lextakip-server/venv/bin
ExecStart=/home/pi/lextakip-server/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8787
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Servisi aktifleştir:
```bash
sudo systemctl daemon-reload
sudo systemctl enable lextakip
sudo systemctl start lextakip
sudo systemctl status lextakip
```

## İlk Kurulum

Sunucu başladıktan sonra, tarayıcıdan veya curl ile ilk kurulumu yap:

```bash
curl -X POST http://localhost:8787/api/setup \
  -H "Content-Type: application/json" \
  -d '{
    "firm_name": "Hukuk Bürosu",
    "firm_code": "HUKUK1",
    "admin_username": "admin",
    "admin_password": "admin123"
  }'
```

## API Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/health` | GET | Sunucu durumu |
| `/public/token` | GET | Basit erişim testi |
| `/api/setup` | POST | İlk kurulum |
| `/api/login` | POST | Kullanıcı girişi |
| `/api/sync` | POST | Senkronizasyon |
| `/api/sync/status` | GET | Sync durumu |
| `/api/users` | GET/POST | Kullanıcı yönetimi |

## Ağ Ayarları

Raspberry Pi'nin IP adresini sabit yapmak için `/etc/dhcpcd.conf`:

```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

## Güvenlik Notları

1. `SECRET_KEY` değerini mutlaka değiştirin
2. PostgreSQL parolasını güçlü yapın
3. Firewall ile sadece LAN erişimine izin verin:
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 8787
   sudo ufw enable
   ```
