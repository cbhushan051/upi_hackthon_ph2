#!/usr/bin/env python3
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.request
import urllib.error
import sqlite3
import time

# Configuration
NS = "http://npci.org/upi/schema/"
PAYER_PSP_URL = "http://localhost:5060"
REM_DB = "rem_bank/rem_bank.sqlite"
# bene_bank might write to root or subdirectory depending on env
BENE_DB = "bene_bank.sqlite" if os.path.exists("bene_bank.sqlite") else "bene_bank/bene_bank.sqlite"

PAYER_VPA = "Chandra@paytm"
PAYEE_VPA = "Chandra@phonepe"

def _qname(tag: str) -> str:
    return f"{{{NS}}}{tag}"

def get_balance(db_path, vpa):
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE vpa = ?", (vpa,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Error reading {db_path}: {e}")
        return None

def build_reqpay_xml(payer_vpa: str, payee_vpa: str, amount: float, pin: str = "1234") -> bytes:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    txn_id = f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    msg_id = f"MSG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    root = ET.Element(_qname("ReqPay"))
    head = ET.SubElement(root, _qname("Head"))
    head.set("ver", "2.0")
    head.set("ts", ts)
    head.set("orgId", "PAYER_PSP")
    head.set("msgId", msg_id)
    head.set("prodType", "UPI")
    
    txn = ET.SubElement(root, _qname("Txn"))
    txn.set("id", txn_id)
    txn.set("type", "PAY")
    
    payer = ET.SubElement(root, _qname("Payer"))
    payer.set("addr", payer_vpa)
    creds = ET.SubElement(payer, _qname("Creds"))
    cred = ET.SubElement(creds, _qname("Cred"))
    cred.set("type", "PIN")
    data = ET.SubElement(cred, _qname("Data"))
    data.text = pin
    
    amt_el = ET.SubElement(payer, _qname("Amount"))
    amt_el.set("value", f"{amount:.2f}")
    amt_el.set("curr", "INR")
    
    payees = ET.SubElement(root, _qname("Payees"))
    payee = ET.SubElement(payees, _qname("Payee"))
    payee.set("addr", payee_vpa)
    
    xml_str = ET.tostring(root, encoding="unicode", method="xml")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str).encode("utf-8")

def run_test(amount):
    print(f"\n--- Testing Transaction with Amount: ₹{amount:.2f} ---")
    
    # 1. Initial Balances
    p_initial = get_balance(REM_DB, PAYER_VPA)
    b_initial = get_balance(BENE_DB, PAYEE_VPA)
    print(f"Initial Balances: Payer={p_initial}, Payee={b_initial}")
    
    # 2. Send Transaction
    url = f"{PAYER_PSP_URL}/api/reqpay"
    xml_body = build_reqpay_xml(PAYER_VPA, PAYEE_VPA, amount)
    
    req = urllib.request.Request(url, data=xml_body, method="POST")
    req.add_header("Content-Type", "application/xml")
    
    try:
        print("Sending ReqPay to Payer PSP...")
        with urllib.request.urlopen(req, timeout=10) as r:
            status = r.status
            print(f"Payer PSP Response Code: {status}")
    except urllib.error.HTTPError as e:
        print(f"Payer PSP Error: {e.code}")
        print(e.read().decode())
        return
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    # 3. Wait for async processing
    print("Waiting 3 seconds for transaction to clear...")
    time.sleep(3)
    
    # 4. Final Balances
    p_final = get_balance(REM_DB, PAYER_VPA)
    b_final = get_balance(BENE_DB, PAYEE_VPA)
    print(f"Final Balances:   Payer={p_final}, Payee={b_final}")
    
    # 5. Result
    p_diff = p_initial - p_final
    b_diff = b_final - b_initial
    
    if p_diff == amount and b_diff == amount:
        print("RESULT: Transaction SUCCESS (Balance Updated)")
        if amount < 150:
            print("WARNING: Validation FAILURE! Amount < 150 was accepted.")
        else:
            print("OK: Validation PASSED! Amount >= 150 was accepted.")
    elif p_diff == 0 and b_diff == 0:
        print("RESULT: Transaction REJECTED (Balance Unchanged)")
        if amount < 150:
            print("OK: Validation PASSED! Amount < 150 was rejected.")
        else:
            print("FAILURE: Validation FAILURE! Amount >= 150 was rejected.")
    else:
        print(f"RESULT: UNKNOWN STATE. Payer Diff: {p_diff}, Payee Diff: {b_diff}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--amount", type=float, default=50.0)
    args = parser.parse_args()
    
    run_test(args.amount)
