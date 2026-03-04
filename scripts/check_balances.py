import sqlite3
import sys
import os

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

def main():
    rem_db = "rem_bank/rem_bank.sqlite"
    bene_db = "bene_bank/bene_bank.sqlite"
    
    payer_vpa = "Chandra@paytm"
    payee_vpa = "Chandra@phonepe"
    
    print(f"Checking balances for {payer_vpa} and {payee_vpa}...")
    
    payer_bal = get_balance(rem_db, payer_vpa)
    payee_bal = get_balance(bene_db, payee_vpa)
    
    print(f"Payer Balance (RemBank): {payer_bal}")
    print(f"Payee Balance (BeneBank): {payee_bal}")

if __name__ == "__main__":
    main()
