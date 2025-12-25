# -*- coding: utf-8 -*-
"""
Authentication helpers
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import hashlib
import secrets

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User, Device, RefreshToken

security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Şifre doğrula"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Şifre hash'le"""
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(
    user_uuid: str,
    firm_id: str,
    device_id: str = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, int]:
    """
    Access token oluştur.

    Returns:
        (token, expires_in_seconds)
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    expires_in = int(expires_delta.total_seconds())

    to_encode = {
        "sub": user_uuid,
        "firm_id": firm_id,
        "device_id": device_id,
        "exp": expire,
        "type": "access"
    }

    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expires_in


def create_refresh_token(
    db: Session,
    user_uuid: str,
    device_id: str = None
) -> str:
    """
    Refresh token oluştur ve veritabanına kaydet.
    """
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Eski token'ları iptal et (aynı cihaz için)
    if device_id:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_uuid,
            RefreshToken.device_id == device_id,
            RefreshToken.revoked == False
        ).update({"revoked": True})

    refresh = RefreshToken(
        user_id=user_uuid,
        device_id=device_id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(refresh)
    db.flush()

    return token


def verify_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """
    Refresh token doğrula.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    refresh = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()

    return refresh


def decode_token(token: str) -> Optional[dict]:
    """Token decode et"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Geçerli kullanıcıyı al (token'dan).
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token gerekli"
        )

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token"
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token tipi"
        )

    user_uuid = payload.get("sub")
    if not user_uuid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token'da kullanıcı bilgisi yok"
        )

    user = db.query(User).filter(
        User.uuid == user_uuid,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı veya aktif değil"
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Geçerli kullanıcıyı al (opsiyonel - hata fırlatmaz).
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def get_device_id_from_header(
    x_device_id: Optional[str] = Header(None)
) -> Optional[str]:
    """Header'dan device ID al"""
    return x_device_id


def get_firm_id_from_header(
    x_firm_id: Optional[str] = Header(None)
) -> Optional[str]:
    """Header'dan firm ID al"""
    return x_firm_id
