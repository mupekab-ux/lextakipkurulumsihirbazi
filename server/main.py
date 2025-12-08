# -*- coding: utf-8 -*-
"""
TakibiEsasi License & Admin API
FastAPI backend for license management and admin panel
"""

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Request
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

    # Licenses table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id SERIAL PRIMARY KEY,
            license_key VARCHAR(50) UNIQUE NOT NULL,
            machine_id VARCHAR(100),
            user_name VARCHAR(200),
            is_active BOOLEAN DEFAULT TRUE,
            transfer_count INTEGER DEFAULT 0,
            customer_name VARCHAR(200),
            email VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            last_check TIMESTAMP
        )
    """)

    # Site settings table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS site_settings (
            id SERIAL PRIMARY KEY,
            setting_key VARCHAR(100) UNIQUE NOT NULL,
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pricing plans table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pricing_plans (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            period VARCHAR(50),
            features TEXT,
            is_popular BOOLEAN DEFAULT FALSE,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Testimonials table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS testimonials (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            title VARCHAR(200),
            content TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # FAQ table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS faq (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Announcements table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY,
            title VARCHAR(300) NOT NULL,
            content TEXT NOT NULL,
            announcement_type VARCHAR(50) DEFAULT 'info',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Features table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id SERIAL PRIMARY KEY,
            icon VARCHAR(100) NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Screenshots table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200),
            image_url VARCHAR(500) NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Media/Images table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER,
            mime_type VARCHAR(100),
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Contact messages table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            email VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Demo registrations table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_registrations (
            id SERIAL PRIMARY KEY,
            email VARCHAR(200) NOT NULL UNIQUE,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(50),
            user_agent TEXT,
            converted_to_license BOOLEAN DEFAULT FALSE,
            converted_at TIMESTAMP
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

class SetUserNameRequest(BaseModel):
    license_key: str
    user_name: str

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

class SiteSettingRequest(BaseModel):
    key: str
    value: str

class PricingPlanRequest(BaseModel):
    name: str
    price: float
    period: Optional[str] = None
    features: Optional[str] = None
    is_popular: bool = False
    sort_order: int = 0

class TestimonialRequest(BaseModel):
    name: str
    title: Optional[str] = None
    content: str
    rating: int = 5

class FAQRequest(BaseModel):
    question: str
    answer: str
    sort_order: int = 0

class AnnouncementRequest(BaseModel):
    title: str
    content: str
    announcement_type: str = "info"

class ContactMessageRequest(BaseModel):
    name: str
    email: str
    message: str

class FeatureRequest(BaseModel):
    icon: str
    title: str
    description: str
    sort_order: int = 0

class ScreenshotRequest(BaseModel):
    title: Optional[str] = None
    image_url: str
    sort_order: int = 0

class BulkSettingsRequest(BaseModel):
    settings: dict

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

@app.get("/api/releases/latest")
async def get_latest_release():
    """Get latest release info (public)"""
    return get_current_release()

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

@app.post("/api/admin/license/set-username")
async def admin_set_username(req: SetUserNameRequest, authorization: str = Header(None)):
    """Set user name for a license"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE licenses SET user_name = %s WHERE license_key = %s", (req.user_name, req.license_key))

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

# ============ SITE SETTINGS API ============

@app.get("/api/site/settings")
async def get_site_settings():
    """Get all site settings (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT setting_key, setting_value FROM site_settings")
    rows = cur.fetchall()

    settings = {row['setting_key']: row['setting_value'] for row in rows}

    cur.close()
    conn.close()

    return settings

@app.post("/api/admin/settings/update")
async def admin_update_setting(req: SiteSettingRequest, authorization: str = Header(None)):
    """Update a site setting"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO site_settings (setting_key, setting_value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (setting_key)
        DO UPDATE SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
    """, (req.key, req.value, req.value))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ PRICING API ============

@app.get("/api/site/pricing")
async def get_pricing():
    """Get active pricing plans (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM pricing_plans WHERE is_active = TRUE ORDER BY sort_order")
    plans = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return plans

@app.get("/api/admin/pricing")
async def admin_get_pricing(authorization: str = Header(None)):
    """Get all pricing plans"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM pricing_plans ORDER BY sort_order")
    plans = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return plans

@app.post("/api/admin/pricing/create")
async def admin_create_pricing(req: PricingPlanRequest, authorization: str = Header(None)):
    """Create a pricing plan"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO pricing_plans (name, price, period, features, is_popular, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (req.name, req.price, req.period, req.features, req.is_popular, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/pricing/update/{plan_id}")
async def admin_update_pricing(plan_id: int, req: PricingPlanRequest, authorization: str = Header(None)):
    """Update a pricing plan"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE pricing_plans
        SET name = %s, price = %s, period = %s, features = %s, is_popular = %s, sort_order = %s
        WHERE id = %s
    """, (req.name, req.price, req.period, req.features, req.is_popular, req.sort_order, plan_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/pricing/{plan_id}")
async def admin_delete_pricing(plan_id: int, authorization: str = Header(None)):
    """Delete a pricing plan"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM pricing_plans WHERE id = %s", (plan_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ TESTIMONIALS API ============

@app.get("/api/site/testimonials")
async def get_testimonials():
    """Get active testimonials (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM testimonials WHERE is_active = TRUE ORDER BY created_at DESC")
    testimonials = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return testimonials

@app.get("/api/admin/testimonials")
async def admin_get_testimonials(authorization: str = Header(None)):
    """Get all testimonials"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM testimonials ORDER BY created_at DESC")
    testimonials = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return testimonials

@app.post("/api/admin/testimonials/create")
async def admin_create_testimonial(req: TestimonialRequest, authorization: str = Header(None)):
    """Create a testimonial"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO testimonials (name, title, content, rating)
        VALUES (%s, %s, %s, %s)
    """, (req.name, req.title, req.content, req.rating))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/testimonials/{testimonial_id}")
async def admin_delete_testimonial(testimonial_id: int, authorization: str = Header(None)):
    """Delete a testimonial"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM testimonials WHERE id = %s", (testimonial_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ FAQ API ============

@app.get("/api/site/faq")
async def get_faq():
    """Get active FAQ items (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM faq WHERE is_active = TRUE ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/faq")
async def admin_get_faq(authorization: str = Header(None)):
    """Get all FAQ items"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM faq ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/faq/create")
async def admin_create_faq(req: FAQRequest, authorization: str = Header(None)):
    """Create a FAQ item"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO faq (question, answer, sort_order)
        VALUES (%s, %s, %s)
    """, (req.question, req.answer, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/faq/{faq_id}")
async def admin_delete_faq(faq_id: int, authorization: str = Header(None)):
    """Delete a FAQ item"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM faq WHERE id = %s", (faq_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ ANNOUNCEMENTS API ============

@app.get("/api/site/announcements")
async def get_announcements():
    """Get active announcements (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM announcements WHERE is_active = TRUE ORDER BY created_at DESC")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/announcements")
async def admin_get_announcements(authorization: str = Header(None)):
    """Get all announcements"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/announcements/create")
async def admin_create_announcement(req: AnnouncementRequest, authorization: str = Header(None)):
    """Create an announcement"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO announcements (title, content, announcement_type)
        VALUES (%s, %s, %s)
    """, (req.title, req.content, req.announcement_type))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/announcements/{announcement_id}")
async def admin_delete_announcement(announcement_id: int, authorization: str = Header(None)):
    """Delete an announcement"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ CONTACT MESSAGES API ============

@app.post("/api/contact")
async def submit_contact(req: ContactMessageRequest):
    """Submit a contact message (public)"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO contact_messages (name, email, message)
        VALUES (%s, %s, %s)
    """, (req.name, req.email, req.message))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.get("/api/admin/messages")
async def admin_get_messages(authorization: str = Header(None)):
    """Get all contact messages"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM contact_messages ORDER BY created_at DESC")
    messages = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return messages

@app.post("/api/admin/messages/read")
async def admin_mark_message_read(message_id: int, authorization: str = Header(None)):
    """Mark a message as read"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE contact_messages SET is_read = TRUE WHERE id = %s", (message_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/messages/{message_id}")
async def admin_delete_message(message_id: int, authorization: str = Header(None)):
    """Delete a message"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM contact_messages WHERE id = %s", (message_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ FEATURES API ============

@app.get("/api/site/features")
async def get_features():
    """Get active features (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM features WHERE is_active = TRUE ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/features")
async def admin_get_features(authorization: str = Header(None)):
    """Get all features"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM features ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/features/create")
async def admin_create_feature(req: FeatureRequest, authorization: str = Header(None)):
    """Create a feature"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO features (icon, title, description, sort_order)
        VALUES (%s, %s, %s, %s)
    """, (req.icon, req.title, req.description, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/features/update/{feature_id}")
async def admin_update_feature(feature_id: int, req: FeatureRequest, authorization: str = Header(None)):
    """Update a feature"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE features
        SET icon = %s, title = %s, description = %s, sort_order = %s
        WHERE id = %s
    """, (req.icon, req.title, req.description, req.sort_order, feature_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/features/{feature_id}")
async def admin_delete_feature(feature_id: int, authorization: str = Header(None)):
    """Delete a feature"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM features WHERE id = %s", (feature_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ SCREENSHOTS API ============

@app.get("/api/site/screenshots")
async def get_screenshots():
    """Get active screenshots (public)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM screenshots WHERE is_active = TRUE ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.get("/api/admin/screenshots")
async def admin_get_screenshots(authorization: str = Header(None)):
    """Get all screenshots"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM screenshots ORDER BY sort_order")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/screenshots/create")
async def admin_create_screenshot(req: ScreenshotRequest, authorization: str = Header(None)):
    """Create a screenshot"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO screenshots (title, image_url, sort_order)
        VALUES (%s, %s, %s)
    """, (req.title, req.image_url, req.sort_order))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.post("/api/admin/screenshots/update/{screenshot_id}")
async def admin_update_screenshot(screenshot_id: int, req: ScreenshotRequest, authorization: str = Header(None)):
    """Update a screenshot"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE screenshots
        SET title = %s, image_url = %s, sort_order = %s
        WHERE id = %s
    """, (req.title, req.image_url, req.sort_order, screenshot_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.delete("/api/admin/screenshots/{screenshot_id}")
async def admin_delete_screenshot(screenshot_id: int, authorization: str = Header(None)):
    """Delete a screenshot"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM screenshots WHERE id = %s", (screenshot_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

# ============ BULK SETTINGS API ============

@app.post("/api/admin/settings/bulk")
async def admin_bulk_settings(req: BulkSettingsRequest, authorization: str = Header(None)):
    """Update multiple settings at once"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor()

    for key, value in req.settings.items():
        cur.execute("""
            INSERT INTO site_settings (setting_key, setting_value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (setting_key)
            DO UPDATE SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
        """, (key, value, value))

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True}

@app.get("/api/admin/settings")
async def admin_get_settings(authorization: str = Header(None)):
    """Get all site settings (admin)"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT setting_key, setting_value FROM site_settings")
    rows = cur.fetchall()

    settings = {row['setting_key']: row['setting_value'] for row in rows}

    cur.close()
    conn.close()

    return settings

# ============ MEDIA UPLOAD API ============

MEDIA_DIR = "/var/www/takibiesasi/media"
os.makedirs(MEDIA_DIR, exist_ok=True)

@app.get("/api/admin/media")
async def admin_get_media(authorization: str = Header(None)):
    """Get all uploaded media"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM media ORDER BY uploaded_at DESC")
    items = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return items

@app.post("/api/admin/media/upload")
async def admin_upload_media(file: UploadFile = File(...), authorization: str = Header(None)):
    """Upload a media file (image)"""
    verify_admin_token(authorization)

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Sadece resim dosyaları yüklenebilir (jpg, png, gif, webp, svg)")

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{secrets.token_hex(16)}{ext}"
    filepath = os.path.join(MEDIA_DIR, unique_name)

    # Save file
    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    # Save to database
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO media (filename, original_name, file_path, file_size, mime_type)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (unique_name, file.filename, filepath, len(content), file.content_type))

    media_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {
        "success": True,
        "id": media_id,
        "filename": unique_name,
        "url": f"https://takibiesasi.com/media/{unique_name}"
    }

@app.delete("/api/admin/media/{media_id}")
async def admin_delete_media(media_id: int, authorization: str = Header(None)):
    """Delete a media file"""
    verify_admin_token(authorization)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Get file path
    cur.execute("SELECT file_path FROM media WHERE id = %s", (media_id,))
    row = cur.fetchone()

    if row:
        # Delete file
        if os.path.exists(row['file_path']):
            os.remove(row['file_path'])

        # Delete from database
        cur.execute("DELETE FROM media WHERE id = %s", (media_id,))
        conn.commit()

    cur.close()
    conn.close()

    return {"success": True}

# ============ ADMIN PANEL ============

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve admin panel"""
    html_path = "/var/www/takibiesasi/admin.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Admin panel not found</h1>"

@app.get("/favicon.svg")
async def favicon():
    """Serve favicon"""
    favicon_path = "/var/www/takibiesasi/favicon.svg"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/favicon.ico")
async def favicon_ico():
    """Serve favicon.ico (redirect to svg)"""
    favicon_path = "/var/www/takibiesasi/favicon.svg"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

# ============ PUBLIC PAGES ============

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Serve demo registration page"""
    html_path = "/var/www/takibiesasi/demo.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Demo page not found</h1>"

@app.get("/gizlilik", response_class=HTMLResponse)
async def privacy_page():
    """Serve privacy policy page"""
    html_path = "/var/www/takibiesasi/gizlilik.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Privacy page not found</h1>"

@app.get("/kvkk", response_class=HTMLResponse)
async def kvkk_page():
    """Serve KVKK (Turkish data protection) page"""
    html_path = "/var/www/takibiesasi/kvkk.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>KVKK page not found</h1>"

@app.get("/kullanim-sartlari", response_class=HTMLResponse)
async def terms_page():
    """Serve terms of use page"""
    html_path = "/var/www/takibiesasi/kullanim-sartlari.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Terms page not found</h1>"

@app.get("/indir", response_class=HTMLResponse)
async def download_page():
    """Serve download page"""
    html_path = "/var/www/takibiesasi/download.html"
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Download page not found</h1>"

# ============ DEMO REGISTRATION API ============

class DemoRegisterRequest(BaseModel):
    email: str

@app.post("/api/demo/register")
async def register_demo(req: DemoRegisterRequest, request: Request):
    """Register email for demo and return download link"""
    import re

    # Email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, req.email):
        raise HTTPException(status_code=400, detail="Geçersiz e-posta adresi")

    conn = get_db()
    cur = conn.cursor()

    try:
        # Get client IP
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        # Try to insert (will fail if email exists)
        cur.execute("""
            INSERT INTO demo_registrations (email, ip_address, user_agent)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                registered_at = CURRENT_TIMESTAMP,
                ip_address = EXCLUDED.ip_address
            RETURNING id, registered_at
        """, (req.email.lower().strip(), client_ip, user_agent[:500] if user_agent else None))

        result = cur.fetchone()
        conn.commit()

        return {
            "success": True,
            "message": "Demo kaydı başarılı! İndirme bağlantınız hazır.",
            "download_url": "/indir",
            "email": req.email.lower().strip(),
            "registered_at": result[1].isoformat() if result else None
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Kayıt hatası: {str(e)}")
    finally:
        cur.close()
        conn.close()

@app.get("/api/demo/stats")
async def demo_stats(authorization: str = Header(None)):
    """Get demo registration stats (admin only)"""
    if not verify_admin_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    cur = conn.cursor()

    try:
        # Total registrations
        cur.execute("SELECT COUNT(*) FROM demo_registrations")
        total = cur.fetchone()[0]

        # Today's registrations
        cur.execute("""
            SELECT COUNT(*) FROM demo_registrations
            WHERE DATE(registered_at) = CURRENT_DATE
        """)
        today = cur.fetchone()[0]

        # This week
        cur.execute("""
            SELECT COUNT(*) FROM demo_registrations
            WHERE registered_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        this_week = cur.fetchone()[0]

        # Converted to license
        cur.execute("""
            SELECT COUNT(*) FROM demo_registrations
            WHERE converted_to_license = TRUE
        """)
        converted = cur.fetchone()[0]

        return {
            "total": total,
            "today": today,
            "this_week": this_week,
            "converted": converted,
            "conversion_rate": round((converted / total * 100), 1) if total > 0 else 0
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/admin/demo-registrations")
async def list_demo_registrations(authorization: str = Header(None)):
    """List all demo registrations (admin only)"""
    if not verify_admin_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, email, ip_address, user_agent, registered_at,
                   download_count, converted_to_license
            FROM demo_registrations
            ORDER BY registered_at DESC
            LIMIT 100
        """)
        rows = cur.fetchall()

        registrations = []
        for row in rows:
            registrations.append({
                "id": row[0],
                "email": row[1],
                "ip_address": row[2],
                "user_agent": row[3][:50] + "..." if row[3] and len(row[3]) > 50 else row[3],
                "registered_at": row[4].isoformat() if row[4] else None,
                "download_count": row[5],
                "converted": row[6]
            })

        return registrations

    finally:
        cur.close()
        conn.close()


@app.post("/api/admin/demo-registrations/{reg_id}/convert")
async def mark_demo_converted(reg_id: int, authorization: str = Header(None)):
    """Mark a demo registration as converted to license"""
    if not verify_admin_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE demo_registrations
            SET converted_to_license = TRUE
            WHERE id = %s
        """, (reg_id,))
        conn.commit()

        return {"success": True, "message": "Demo kaydı lisansa dönüştürüldü olarak işaretlendi"}

    finally:
        cur.close()
        conn.close()


@app.delete("/api/admin/demo-registrations/{reg_id}")
async def delete_demo_registration(reg_id: int, authorization: str = Header(None)):
    """Delete a demo registration"""
    if not verify_admin_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM demo_registrations WHERE id = %s", (reg_id,))
        conn.commit()

        return {"success": True, "message": "Demo kaydı silindi"}

    finally:
        cur.close()
        conn.close()


# ============ STATIC FILES ============

# Mount download directory for static file serving
if os.path.exists(DOWNLOAD_DIR):
    app.mount("/download", StaticFiles(directory=DOWNLOAD_DIR), name="download")

# Mount media directory for image serving
if os.path.exists(MEDIA_DIR):
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
