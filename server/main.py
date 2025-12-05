# -*- coding: utf-8 -*-
"""
TakibiEsasi License & Admin API
FastAPI backend for license management and admin panel
"""

from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import secrets
import hashlib
import json
import os
import jwt

app = FastAPI(title="TakibiEsasi API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "takibiesasi_db",
    "user": "takibiesasi_user",
    "password": "TakibiEsasi2024!"
}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "TakibiAdmin2024!"
JWT_SECRET = "takibiesasi-secret-key-2024"
DOWNLOAD_DIR = "/var/www/takibiesasi/download"
RELEASES_FILE = "/var/www/takibiesasi/releases/latest.json"
RELEASES_HISTORY_FILE = "/var/www/takibiesasi/releases/history.json"

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(RELEASES_FILE), exist_ok=True)

# ============ DATABASE ============

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id SERIAL PRIMARY KEY,
            license_key VARCHAR(50) UNIQUE NOT NULL,
            machine_id VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            transfer_count INTEGER DEFAULT 0,
            customer_name VARCHAR(200),
            email VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            last_check TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

# Initialize on startup
@app.on_event("startup")
async def startup():
    init_db()

# ============ MODELS ============

class ActivateRequest(BaseModel):
    license_key: str
    machine_id: str

class VerifyRequest(BaseModel):
    license_key: str
    machine_id: str

class TransferRequest(BaseModel):
    license_key: str
    old_machine_id: str
    new_machine_id: str

class UpdateCheckRequest(BaseModel):
    current_version: str
    machine_id: Optional[str] = None

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class CreateLicenseRequest(BaseModel):
    customer_name: Optional[str] = None
    email: Optional[str] = None

class LicenseActionRequest(BaseModel):
    license_key: str

class SetTransferRequest(BaseModel):
    license_key: str
    transfer_count: int

class ReleaseRequest(BaseModel):
    version: str
    download_url: str
    release_notes: str
    min_version: Optional[str] = None
    is_critical: bool = False

class SetCurrentReleaseRequest(BaseModel):
    version: str

class DeleteFileRequest(BaseModel):
    filename: str

# ============ HELPERS ============

def generate_license_key():
    """Generate a unique license key"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    parts = []
    for _ in range(4):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return '-'.join(parts)

def verify_admin_token(authorization: str = Header(None)):
    """Verify JWT token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace('Bearer ', '')
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_release():
    """Get current release info"""
    try:
        with open(RELEASES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "version": "1.0.0",
            "download_url": "",
            "release_notes": "İlk sürüm",
            "release_date": datetime.now().strftime("%Y-%m-%d"),
            "is_critical": False,
            "min_version": "1.0.0"
        }

def get_releases_history():
    """Get all releases history"""
    try:
        with open(RELEASES_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_release(release_data):
    """Save release to latest.json and history"""
    # Save as current
    with open(RELEASES_FILE, 'w') as f:
        json.dump(release_data, f, indent=2)

    # Add to history
    history = get_releases_history()
    history.insert(0, release_data)
    with open(RELEASES_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

# ============ PUBLIC API ============

@app.get("/")
async def root():
    return {"status": "ok", "service": "TakibiEsasi License API"}

@app.post("/api/activate")
async def activate_license(req: ActivateRequest):
    """Activate a license with machine ID"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses WHERE license_key = %s", (req.license_key,))
    license = cur.fetchone()

    if not license:
        cur.close()
        conn.close()
        return {"success": False, "error": "Geçersiz lisans anahtarı"}

    if not license['is_active']:
        cur.close()
        conn.close()
        return {"success": False, "error": "Bu lisans devre dışı bırakılmış"}

    if license['machine_id'] and license['machine_id'] != req.machine_id:
        cur.close()
        conn.close()
        return {"success": False, "error": "Bu lisans başka bir cihazda aktif"}

    # Activate
    cur.execute("""
        UPDATE licenses
        SET machine_id = %s, activated_at = CURRENT_TIMESTAMP, last_check = CURRENT_TIMESTAMP
        WHERE license_key = %s
    """, (req.machine_id, req.license_key))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True, "message": "Lisans aktive edildi"}

@app.post("/api/verify")
async def verify_license(req: VerifyRequest):
    """Verify an active license"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses WHERE license_key = %s", (req.license_key,))
    license = cur.fetchone()

    if not license:
        cur.close()
        conn.close()
        return {"valid": False, "error": "Geçersiz lisans"}

    if not license['is_active']:
        cur.close()
        conn.close()
        return {"valid": False, "error": "Lisans devre dışı"}

    if license['machine_id'] != req.machine_id:
        cur.close()
        conn.close()
        return {"valid": False, "error": "Makine ID eşleşmiyor"}

    # Update last check
    cur.execute("UPDATE licenses SET last_check = CURRENT_TIMESTAMP WHERE license_key = %s", (req.license_key,))
    conn.commit()
    cur.close()
    conn.close()

    return {"valid": True}

@app.post("/api/transfer")
async def transfer_license(req: TransferRequest):
    """Transfer license to a new machine"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses WHERE license_key = %s", (req.license_key,))
    license = cur.fetchone()

    if not license:
        cur.close()
        conn.close()
        return {"success": False, "error": "Geçersiz lisans"}

    if not license['is_active']:
        cur.close()
        conn.close()
        return {"success": False, "error": "Lisans devre dışı"}

    if license['machine_id'] != req.old_machine_id:
        cur.close()
        conn.close()
        return {"success": False, "error": "Mevcut makine ID eşleşmiyor"}

    if license['transfer_count'] >= 2:
        cur.close()
        conn.close()
        return {"success": False, "error": "Transfer hakkı doldu (max 2)"}

    # Transfer
    cur.execute("""
        UPDATE licenses
        SET machine_id = %s, transfer_count = transfer_count + 1, last_check = CURRENT_TIMESTAMP
        WHERE license_key = %s
    """, (req.new_machine_id, req.license_key))

    conn.commit()
    remaining = 2 - (license['transfer_count'] + 1)
    cur.close()
    conn.close()

    return {"success": True, "remaining_transfers": remaining}

@app.post("/api/check-update")
async def check_update(req: UpdateCheckRequest):
    """Check for updates"""
    release = get_current_release()

    def parse_version(v):
        return tuple(map(int, v.split('.')))

    try:
        current = parse_version(req.current_version)
        latest = parse_version(release['version'])
        has_update = latest > current
    except:
        has_update = False

    return {
        "has_update": has_update,
        "latest_version": release['version'],
        "download_url": release['download_url'],
        "release_notes": release['release_notes'],
        "is_critical": release.get('is_critical', False)
    }

# ============ ADMIN API ============

@app.post("/api/admin/login")
async def admin_login(req: AdminLoginRequest):
    """Admin login"""
    if req.username == ADMIN_USERNAME and req.password == ADMIN_PASSWORD:
        token = jwt.encode(
            {"user": req.username, "exp": datetime.utcnow() + timedelta(hours=24)},
            JWT_SECRET,
            algorithm="HS256"
        )
        return {"success": True, "token": token}
    return {"success": False, "error": "Geçersiz kullanıcı adı veya şifre"}

@app.get("/api/admin/stats")
async def admin_stats(authorization: str = Header(None)):
    """Get dashboard statistics"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Total licenses
    cur.execute("SELECT COUNT(*) as count FROM licenses")
    total = cur.fetchone()['count']

    # Active licenses
    cur.execute("SELECT COUNT(*) as count FROM licenses WHERE is_active = TRUE AND machine_id IS NOT NULL")
    active = cur.fetchone()['count']

    # Today activations
    cur.execute("SELECT COUNT(*) as count FROM licenses WHERE DATE(activated_at) = CURRENT_DATE")
    today = cur.fetchone()['count']

    # Recent activations
    cur.execute("""
        SELECT license_key, machine_id, activated_at, is_active
        FROM licenses
        WHERE activated_at IS NOT NULL
        ORDER BY activated_at DESC LIMIT 10
    """)
    recent = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    release = get_current_release()

    return {
        "total_licenses": total,
        "active_licenses": active,
        "today_activations": today,
        "current_version": release['version'],
        "recent_activations": recent
    }

@app.get("/api/admin/licenses")
async def admin_licenses(authorization: str = Header(None)):
    """Get all licenses"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM licenses ORDER BY created_at DESC")
    licenses = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return {"licenses": licenses}

@app.post("/api/admin/license/create")
async def admin_create_license(req: CreateLicenseRequest, authorization: str = Header(None)):
    """Create a new license"""
    verify_admin_token(authorization)

    license_key = generate_license_key()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO licenses (license_key, customer_name, email)
        VALUES (%s, %s, %s)
    """, (license_key, req.customer_name, req.email))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True, "license_key": license_key}

@app.post("/api/admin/license/toggle")
async def admin_toggle_license(req: LicenseActionRequest, authorization: str = Header(None)):
    """Toggle license active status"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET is_active = NOT is_active WHERE license_key = %s", (req.license_key,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/license/reset-transfer")
async def admin_reset_transfer(req: LicenseActionRequest, authorization: str = Header(None)):
    """Reset transfer count"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET transfer_count = 0, machine_id = NULL WHERE license_key = %s", (req.license_key,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/license/set-transfer")
async def admin_set_transfer(req: SetTransferRequest, authorization: str = Header(None)):
    """Set transfer count to a specific value"""
    verify_admin_token(authorization)

    if req.transfer_count < 0:
        return {"success": False, "error": "Transfer sayısı negatif olamaz"}

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET transfer_count = %s WHERE license_key = %s", (req.transfer_count, req.license_key))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.get("/api/admin/releases")
async def admin_releases(authorization: str = Header(None)):
    """Get all releases"""
    verify_admin_token(authorization)

    return {
        "current": get_current_release(),
        "releases": get_releases_history()
    }

@app.post("/api/admin/release/publish")
async def admin_publish_release(req: ReleaseRequest, authorization: str = Header(None)):
    """Publish a new release"""
    verify_admin_token(authorization)

    release_data = {
        "version": req.version,
        "download_url": req.download_url,
        "release_notes": req.release_notes,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "is_critical": req.is_critical,
        "min_version": req.min_version or req.version
    }

    save_release(release_data)

    return {"success": True}

@app.post("/api/admin/release/set-current")
async def admin_set_current_release(req: SetCurrentReleaseRequest, authorization: str = Header(None)):
    """Set a release as current"""
    verify_admin_token(authorization)

    history = get_releases_history()
    for release in history:
        if release['version'] == req.version:
            with open(RELEASES_FILE, 'w') as f:
                json.dump(release, f, indent=2)
            return {"success": True}

    return {"success": False, "error": "Sürüm bulunamadı"}

@app.get("/api/admin/files")
async def admin_files(authorization: str = Header(None)):
    """List uploaded files"""
    verify_admin_token(authorization)

    files = []
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    "name": filename,
                    "size": stat.st_size,
                    "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "url": f"https://takibiesasi.com/download/{filename}"
                })

    files.sort(key=lambda x: x['date'], reverse=True)
    return {"files": files}

@app.post("/api/admin/upload")
async def admin_upload(file: UploadFile = File(...), authorization: str = Header(None)):
    """Upload a file"""
    verify_admin_token(authorization)

    if not file.filename.endswith('.exe'):
        raise HTTPException(status_code=400, detail="Sadece .exe dosyaları yüklenebilir")

    filepath = os.path.join(DOWNLOAD_DIR, file.filename)

    with open(filepath, 'wb') as f:
        content = await file.read()
        f.write(content)

    return {"success": True, "filename": file.filename}

@app.post("/api/admin/file/delete")
async def admin_delete_file(req: DeleteFileRequest, authorization: str = Header(None)):
    """Delete a file"""
    verify_admin_token(authorization)

    filepath = os.path.join(DOWNLOAD_DIR, req.filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return {"success": True}

    return {"success": False, "error": "Dosya bulunamadı"}

# ============ ADMIN PANEL ============

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve admin panel"""
    html_path = "/var/www/takibiesasi/admin.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Admin panel not found</h1>"

# ============ STATIC FILES ============

# Mount download directory for static file serving
if os.path.exists(DOWNLOAD_DIR):
    app.mount("/download", StaticFiles(directory=DOWNLOAD_DIR), name="download")
