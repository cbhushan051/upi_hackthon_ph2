"""
Remitter bank–scoped SQLite database: Account table only.
Separate from common/db so rem_bank owns its own data.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import Column, Float, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String(64), primary_key=True)
    vpa = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    bank_code = Column(String(64), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)


def _default_db_path() -> str:
    """Path to rem_bank.sqlite in the app root (parent of db/). Works in Docker and locally."""
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(app_root, "rem_bank.sqlite").replace("\\", "/")


def get_engine(db_url: Optional[str] = None):
    url = (
        db_url
        or os.getenv("DATABASE_URL")
        or f"sqlite:///{_default_db_path()}"
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


def get_account_by_vpa(session: Session, vpa: str) -> Optional[Account]:
    return session.query(Account).filter_by(vpa=vpa.strip()).one_or_none()


def upsert_account(
    session: Session,
    *,
    id: str,
    vpa: str,
    name: str,
    bank_code: str,
    balance: float = 0.0,
):
    existing = session.query(Account).filter_by(vpa=vpa).one_or_none()
    if existing:
        existing.name = name
        existing.bank_code = bank_code
        existing.balance = balance
        return existing
    account = Account(id=id, vpa=vpa, name=name, bank_code=bank_code, balance=balance)
    session.add(account)
    return account


def seed_sample_accounts(session: Session) -> None:
    """Insert accounts for Chandra, Gaurang, Hrithik (payer VPAs @paytm) at SBI. Idempotent."""
    for account_id, vpa, name in [
        ("SBI-Chandra", "Chandra@paytm", "Chandra"),
        ("SBI-Gaurang", "Gaurang@paytm", "Gaurang"),
        ("SBI-Hrithik", "Hrithik@paytm", "Hrithik"),
    ]:
        upsert_account(session, id=account_id, vpa=vpa, name=name, bank_code="SBI", balance=1000.0)
    session.commit()
