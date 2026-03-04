"""
Payer PSP–scoped SQLite database: User table only.
Separate from common/db so payer_psp owns its own data.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

# In payer_psp, users are always payer_psp; no multi-role enum needed.
ROLE = "payer_psp"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vpa = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    bank_code = Column(String(64), nullable=True)
    psp_code = Column(String(64), nullable=True)
    role = Column(String(32), nullable=False)  # "payer_psp" in this service
    pin = Column(String(10), nullable=False, default="1234")


def get_engine(db_url: Optional[str] = None):
    url = (
        db_url
        or os.getenv("DATABASE_URL")
        or f"sqlite:///{os.path.abspath('payer_psp.sqlite')}"
    )
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, future=True, connect_args=connect_args)


def make_session_factory(engine):
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
    )


def init_db(engine=None) -> sessionmaker:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def upsert_user(
    session: Session,
    *,
    vpa: str,
    name: str,
    bank_code: Optional[str] = None,
    psp_code: Optional[str] = None,
    role: str = ROLE,
    pin: str = "1234",
):
    # Avoid duplicate inserts when object is already pending in session
    existing = None
    for obj in session.new:
        if isinstance(obj, User) and obj.vpa == vpa:
            existing = obj
            break
    if existing is None:
        existing = session.query(User).filter_by(vpa=vpa).one_or_none()
    if existing:
        existing.name = name
        existing.role = role
        existing.bank_code = bank_code
        existing.psp_code = psp_code
        existing.pin = pin
        return existing
    user = User(vpa=vpa, name=name, role=role, bank_code=bank_code, psp_code=psp_code, pin=pin)
    session.add(user)
    return user


def seed_sample_users(session: Session) -> None:
    """Insert sample users Chandra, Gaurang, Hrithik if missing. Idempotent."""
    for vpa, name, pin in [
        ("Chandra@paytm", "Chandra", "1111"),
        ("Gaurang@paytm", "Gaurang", "1111"),
        ("Hrithik@paytm", "Hrithik", "1111"),
    ]:
        upsert_user(session, vpa=vpa, name=name, psp_code="PAYER_PSP", pin=pin)
    session.commit()
