from __future__ import annotations
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

Base = declarative_base()


class UserRoleEnum(str):
    PAYER_BANK = "payer_bank"
    PAYEE_BANK = "payee_bank"
    PAYER_PSP = "payer_psp"
    PAYEE_PSP = "payee_psp"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vpa = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    bank_code = Column(String(64), nullable=True)
    psp_code = Column(String(64), nullable=True)
    role = Column(String(32), nullable=False)  # values from UserRoleEnum


class NPCIMapper(Base):
    __tablename__ = "npci_mapper"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vpa = Column(String(255), nullable=False, unique=True)
    bank_code = Column(String(64), nullable=False)
    account_id = Column(String(255), nullable=False)
    psp_code = Column(String(64), nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rrn = Column(String(64), nullable=False, unique=True)
    payer_vpa = Column(String(255), nullable=False)
    payee_vpa = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(String(1024), nullable=True)
    utr_debit = Column(String(64), nullable=True)
    utr_credit = Column(String(64), nullable=True)
    status = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    failure_reason = Column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("rrn", name="uq_transactions_rrn"),
    )


def get_engine(db_url: Optional[str] = None):
    url = db_url or os.getenv("DATABASE_URL") or f"sqlite:///{os.path.abspath('upi_demo.sqlite')}"
    # check_same_thread False for use across threads in this demo
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, future=True, connect_args=connect_args)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def init_db(engine=None) -> sessionmaker:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def upsert_user(session: Session, *, vpa: str, name: str, role: str, bank_code: Optional[str] = None, psp_code: Optional[str] = None):
    # Look for an already-pending instance in this session (avoids duplicate inserts before flush/commit)
    existing = None
    for obj in session.new:
        if isinstance(obj, User) and obj.vpa == vpa:
            existing = obj
            break
    # If not pending, check the database
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


def upsert_mapper(session: Session, *, vpa: str, bank_code: str, account_id: str, psp_code: Optional[str] = None):
    existing = session.query(NPCIMapper).filter_by(vpa=vpa).one_or_none()
    if existing:
        existing.bank_code = bank_code
        existing.account_id = account_id
        existing.psp_code = psp_code
        return existing
    row = NPCIMapper(vpa=vpa, bank_code=bank_code, account_id=account_id, psp_code=psp_code)
    session.add(row)
    return row


def persist_transaction(session: Session, *, rrn: str, payer_vpa: str, payee_vpa: str, amount: float, note: str, utr_debit: Optional[str], utr_credit: Optional[str], status: str, created_at_iso: str, failure_reason: Optional[str] = None):
    # created_at stored as UTC datetime
    try:
        created_at_dt = datetime.fromisoformat(created_at_iso.replace("Z", ""))
    except Exception:
        created_at_dt = datetime.utcnow()
    tx = Transaction(
        rrn=rrn,
        payer_vpa=payer_vpa,
        payee_vpa=payee_vpa,
        amount=amount,
        note=note,
        utr_debit=utr_debit,
        utr_credit=utr_credit,
        status=status,
        created_at=created_at_dt,
        failure_reason=failure_reason,
    )
    session.add(tx)
    return tx


