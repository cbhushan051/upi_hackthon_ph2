#!/usr/bin/env python3
"""
Check account information in bank databases (bene_bank, rem_bank).
Run from project root: python scripts/check_account.py [options]

Examples:
  python scripts/check_account.py --vpa Chandra@phonepe
  python scripts/check_account.py --vpa Chandra@paytm --db rem_bank
  python scripts/check_account.py --id HDFC-Chandra --db bene_bank
  python scripts/check_account.py --db all
  python scripts/check_account.py
"""
from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from bene_bank.db import Account as BeneAccount, get_account_by_vpa as bene_get_by_vpa, get_engine as bene_get_engine, make_session_factory as bene_make_session
from rem_bank.db import Account as RemAccount, get_account_by_vpa as rem_get_by_vpa, get_engine as rem_get_engine, make_session_factory as rem_make_session


def _db_path(service: str, filename: str) -> str:
    path = os.path.join(PROJECT_ROOT, service, filename)
    return os.path.abspath(path).replace("\\", "/")


def _engine_and_session(service: str):
    if service == "bene_bank":
        url = f"sqlite:///{_db_path('bene_bank', 'bene_bank.sqlite')}"
        engine = bene_get_engine(db_url=url)
        Session = bene_make_session(engine)
        Account = BeneAccount
        get_by_vpa = bene_get_by_vpa
    else:
        url = f"sqlite:///{_db_path('rem_bank', 'rem_bank.sqlite')}"
        engine = rem_get_engine(db_url=url)
        Session = rem_make_session(engine)
        Account = RemAccount
        get_by_vpa = rem_get_by_vpa
    return Session, Account, get_by_vpa


def _format_account(acc, db_name: str) -> str:
    return (
        f"  id        : {acc.id}\n"
        f"  vpa       : {acc.vpa}\n"
        f"  name      : {acc.name}\n"
        f"  bank_code : {acc.bank_code}\n"
        f"  balance   : {acc.balance}\n"
        f"  database  : {db_name}"
    )


def _query(session, Account, get_by_vpa, *, vpa: str | None = None, account_id: str | None = None):
    if vpa:
        return get_by_vpa(session, vpa)
    if account_id:
        return session.query(Account).filter(Account.id == account_id).one_or_none()
    return session.query(Account).all()


def _run_db(service: str, vpa: str | None, id: str | None, list_all: bool) -> int:
    Session, Account, get_by_vpa = _engine_and_session(service)
    with Session() as session:
        if list_all or (not vpa and not id):
            rows = _query(session, Account, get_by_vpa)
            if not rows:
                print(f"[{service}] No accounts found.\n")
                return 0
            print(f"[{service}] {len(rows)} account(s):\n")
            for acc in rows:
                print(_format_account(acc, service))
                print()
            return len(rows)
        acc = _query(session, Account, get_by_vpa, vpa=vpa, account_id=id)
        if not acc:
            print(f"[{service}] No account found for vpa={vpa!r} id={id!r}.\n")
            return 0
        print(f"[{service}]\n{_format_account(acc, service)}\n")
        return 1


def main():
    ap = argparse.ArgumentParser(
        description="Check account information in bene_bank and/or rem_bank databases."
    )
    ap.add_argument(
        "--db",
        choices=["bene_bank", "rem_bank", "all"],
        default="all",
        help="Database to query (default: all)",
    )
    ap.add_argument("--vpa", type=str, help="Look up by VPA (e.g. Chandra@phonepe, Chandra@paytm)")
    ap.add_argument("--id", type=str, help="Look up by account id (e.g. HDFC-Chandra, SBI-Gaurang)")
    ap.add_argument("--list", action="store_true", help="List all accounts (default if neither --vpa nor --id)")
    args = ap.parse_args()

    dbs = ["bene_bank", "rem_bank"] if args.db == "all" else [args.db]
    list_all = args.list or (not args.vpa and not args.id)
    count = 0
    for db in dbs:
        count += _run_db(db, args.vpa, args.id, list_all)
    if count == 0 and (args.vpa or args.id):
        sys.exit(1)


if __name__ == "__main__":
    main()
