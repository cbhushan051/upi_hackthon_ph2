"""
Payee PSP–scoped SQLite database: User and ValAddProfile.
ValAddProfile holds RespValAdd/Merchant data keyed by VPA (Payee.addr from ReqValAdd).
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

# In payee_psp, users are always payee_psp; no multi-role enum needed.
ROLE = "payee_psp"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vpa = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    bank_code = Column(String(64), nullable=True)
    psp_code = Column(String(64), nullable=True)
    role = Column(String(32), nullable=False)  # "payee_psp" in this service


class ValAddProfile(Base):
    """
    RespValAdd data for a Payee VPA. Maps to Resp (attributes) and Merchant (Identifier, Name, Ownership).
    Lookup by vpa = Payee.addr from ReqValAdd.
    """
    __tablename__ = "valadd_profiles"
    vpa = Column(String(255), primary_key=True)
    # Head override
    org_id = Column(String(64), nullable=True)
    # Resp attributes
    mask_name = Column(String(255), nullable=True)
    code = Column(String(64), nullable=True)
    type = Column(String(64), nullable=True)
    ifsc = Column(String(32), nullable=True)
    acc_type = Column(String(32), nullable=True)
    iin = Column(String(32), nullable=True)
    p_type = Column(String(32), nullable=True)
    feature_supported = Column(String(255), nullable=True)
    # Merchant.Identifier
    mid = Column(String(64), nullable=True)
    sid = Column(String(64), nullable=True)
    tid = Column(String(64), nullable=True)
    merchant_type = Column(String(64), nullable=True)
    merchant_genre = Column(String(64), nullable=True)
    pin_code = Column(String(16), nullable=True)
    reg_id_no = Column(String(64), nullable=True)
    tier = Column(String(32), nullable=True)
    on_boarding_type = Column(String(32), nullable=True)
    # Merchant.Name
    brand_name = Column(String(255), nullable=True)
    legal_name = Column(String(255), nullable=True)
    franchise_name = Column(String(255), nullable=True)
    # Merchant.Ownership
    ownership_type = Column(String(32), nullable=True)


def get_engine(db_url: Optional[str] = None):
    url = (
        db_url
        or os.getenv("DATABASE_URL")
        or f"sqlite:///{os.path.abspath('payee_psp.sqlite')}"
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
        return existing
    user = User(vpa=vpa, name=name, role=role, bank_code=bank_code, psp_code=psp_code)
    session.add(user)
    return user


def get_valadd_profile(session: Session, vpa: str) -> Optional[ValAddProfile]:
    """Look up RespValAdd profile by Payee VPA (Payee.addr from ReqValAdd)."""
    return session.query(ValAddProfile).filter_by(vpa=vpa).one_or_none()


def seed_sample_valadd_profiles(session: Session) -> None:
    """Insert sample ValAddProfiles for payee@psp and merchant@payeepsp if missing. Idempotent."""
    to_add = []

    if not session.query(ValAddProfile).filter_by(vpa="payee@psp").one_or_none():
        to_add.append(ValAddProfile(
            vpa="payee@psp",
            org_id="PAYEE_PSP",
            mask_name="Payee Name",
            feature_supported="UPI",
            mid="MID001",
            sid="SID001",
            tid="TID001",
            merchant_type="RETAIL",
            merchant_genre="RETAIL",
            brand_name="Payee Brand",
            legal_name="Payee Legal",
            ownership_type="SOLE",
        ))

    if not session.query(ValAddProfile).filter_by(vpa="merchant@payeepsp").one_or_none():
        to_add.append(ValAddProfile(
            vpa="merchant@payeepsp",
            org_id="PAYEE_PSP",
            mask_name="Merchant Store",
            feature_supported="UPI",
            mid="MID002",
            sid="SID002",
            tid="TID002",
            merchant_type="ECOM",
            merchant_genre="E-COMMERCE",
            pin_code="110001",
            brand_name="Merchant Store",
            legal_name="Merchant Store Pvt Ltd",
            franchise_name="Merchant Franchise",
            ownership_type="PRIVATE",
        ))

    for p in to_add:
        session.add(p)
    if to_add:
        session.commit()


def seed_sample_users(session: Session) -> None:
    """Insert sample users Chandra, Gaurang, Hrithik if missing. Idempotent."""
    for vpa, name in [
        ("Chandra@phonepe", "Chandra"),
        ("Gaurang@phonepe", "Gaurang"),
        ("Hrithik@phonepe", "Hrithik"),
    ]:
        upsert_user(session, vpa=vpa, name=name, psp_code="PAYEE_PSP")
    session.commit()
