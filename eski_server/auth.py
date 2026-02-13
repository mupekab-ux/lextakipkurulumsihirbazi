# -*- coding: utf-8 -*-
"""
Kimlik doğrulama ve JWT token yönetimi
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User, Firm
from schemas import TokenData

# Parola hash'leme
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token şeması
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Parolayı doğrula."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Parolayı hash'le."""
    return pwd_context.hash(password)


def create_access_token(
    user_uuid: str,
    firm_id: str,
    username: str,
    role: str,
    device_id: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """JWT access token oluştur."""

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": user_uuid,
        "firm_id": firm_id,
        "username": username,
        "role": role,
        "device_id": device_id,
        "exp": expire,
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """Token'ı çöz ve doğrula."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_uuid: str = payload.get("sub")
        firm_id: str = payload.get("firm_id")
        username: str = payload.get("username")
        role: str = payload.get("role")
        device_id: str = payload.get("device_id")
        exp = payload.get("exp")

        if user_uuid is None or firm_id is None:
            return None

        return TokenData(
            user_uuid=user_uuid,
            firm_id=firm_id,
            username=username,
            role=role,
            device_id=device_id,
            exp=datetime.fromtimestamp(exp) if isinstance(exp, (int, float)) else exp,
        )
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> TokenData:
    """Mevcut kullanıcıyı token'dan al."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception

    # Token süresi kontrolü
    if token_data.exp < datetime.utcnow():
        raise credentials_exception

    # Kullanıcının hala aktif olduğunu kontrol et
    user = db.query(User).filter(
        User.uuid == token_data.user_uuid,
        User.firm_id == token_data.firm_id,
        User.is_deleted == False,
        User.is_active == True
    ).first()

    if user is None:
        raise credentials_exception

    return token_data


def authenticate_user(db: Session, username: str, password: str, firm_id: str) -> Optional[User]:
    """Kullanıcıyı doğrula."""

    user = db.query(User).filter(
        User.username == username,
        User.firm_id == firm_id,
        User.is_deleted == False,
        User.is_active == True
    ).first()

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def get_firm_by_code(db: Session, code: str) -> Optional[Firm]:
    """Firma kodundan firma bul."""
    return db.query(Firm).filter(
        Firm.code == code,
        Firm.is_active == True
    ).first()
