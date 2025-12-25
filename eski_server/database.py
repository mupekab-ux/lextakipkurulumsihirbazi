# -*- coding: utf-8 -*-
"""
Veritabanı bağlantı yönetimi
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# PostgreSQL bağlantısı
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency injection için veritabanı session'ı."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
