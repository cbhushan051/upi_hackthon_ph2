#!/usr/bin/env python3
"""
Interactive UPI Transaction Test Script

This script allows you to test UPI transactions with custom amounts and PINs
to verify that validation rules (like minimum transaction amount) are working correctly.

Usage:
    python scripts/interactive_test.py

Requirements:
    - Docker containers must be running: docker-compose up -d
"""

import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.request
import urllib.error
import subprocess

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
NS = "http://npci.org/upi/schema/"

# Default VPAs (matching seeded data in Docker)
DEFAULT_PAYER_VPA = "Chandra@paytm"
DEFAULT_PAYEE_VPA = "Chandra@phonepe"


def _qname(tag: str) -> str:
    """Generate qualified XML tag name with namespace."""
    return f"{{{NS}}}{tag}"


def _detect_payer_psp_url():
    """Auto-detect Payer PSP URL from docker-compose or environment."""
    if os.environ.get("PAYER_PSP_URL"):
        return os.environ["PAYER_PSP_URL"]
    try:
        out = subprocess.run(
            ["docker", "compose", "port", "payer_psp", "6004"],  # Internal port is 6004
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT,
        )
        if out.returncode == 0 and out.stdout.strip():
            port = out.stdout.strip().split(":")[-1]
            if port.isdigit():
                return f"http://localhost:{port}"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "http://localhost:5060"  # Default from .env PAYER_PSP_PORT


def build_reqpay_xml(payer_vpa: str, payee_vpa: str, amount: float, pin: str = "1234") -> bytes:
    """
    Build a ReqPay XML message for UPI payment.
    
    Args:
        payer_vpa: Payer's VPA (e.g., "alice@payer")
        payee_vpa: Payee's VPA (e.g., "bob@bene")
        amount: Transaction amount in INR
        pin: UPI PIN (default: "1234")
    
    Returns:
        XML bytes ready to send
    """
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    txn_id = f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    msg_id = f"MSG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    root = ET.Element(_qname("ReqPay"))
    
    # Head
    head = ET.SubElement(root, _qname("Head"))
    head.set("ver", "2.0")
    head.set("ts", ts)
    head.set("orgId", "PAYER_PSP")
    head.set("msgId", msg_id)
    head.set("prodType", "UPI")
    
    # Txn
    txn = ET.SubElement(root, _qname("Txn"))
    txn.set("id", txn_id)
    txn.set("type", "PAY")
    txn.set("custRef", f"Payment from {payer_vpa}")
    
    # Payer
    payer = ET.SubElement(root, _qname("Payer"))
    payer.set("addr", payer_vpa)
    payer.set("name", "Alice")
    payer.set("type", "PERSON")
    
    # Payer Creds (PIN)
    creds = ET.SubElement(payer, _qname("Creds"))
    cred = ET.SubElement(creds, _qname("Cred"))
    cred.set("type", "PIN")
    data = ET.SubElement(cred, _qname("Data"))
    data.text = pin
    
    # Payer Amount
    payer_amt = ET.SubElement(payer, _qname("Amount"))
    payer_amt.set("value", f"{amount:.2f}")
    payer_amt.set("curr", "INR")
    
    # Payees
    payees = ET.SubElement(root, _qname("Payees"))
    payee = ET.SubElement(payees, _qname("Payee"))
    payee.set("addr", payee_vpa)
    payee.set("name", "Bob")
    payee.set("type", "PERSON")
    
    xml_str = ET.tostring(root, encoding="unicode", method="xml")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str).encode("utf-8")


def send_transaction(payer_vpa: str, payee_vpa: str, amount: float, pin: str) -> dict:
    """
    Send a UPI transaction and return the result.
    
    Returns:
        dict with keys: success (bool), status_code (int), message (str), details (str)
    """
    payer_psp_url = _detect_payer_psp_url()
    url = f"{payer_psp_url.rstrip('/')}/api/reqpay"
    
    # Build XML
    xml_body = build_reqpay_xml(payer_vpa, payee_vpa, amount, pin)
    
    # Send request
    req = urllib.request.Request(url, data=xml_body, method="POST")
    req.add_header("Content-Type", "application/xml")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            response_data = r.read()
            status_code = r.status
            response_text = response_data.decode("utf-8", errors="replace")
        
        if status_code == 202:
            return {
                "success": True,
                "status_code": status_code,
                "message": "Transaction accepted and processed",
                "details": response_text
            }
        else:
            return {
                "success": False,
                "status_code": status_code,
                "message": f"Unexpected status code: {status_code}",
                "details": response_text
            }
    
    except urllib.error.HTTPError as e:
        response_data = e.read()
        response_text = response_data.decode("utf-8", errors="replace")
        return {
            "success": False,
            "status_code": e.code,
            "message": f"HTTP Error {e.code}",
            "details": response_text
        }
    
    except urllib.error.URLError as e:
        return {
            "success": False,
            "status_code": 0,
            "message": f"Connection failed: {e.reason}",
            "details": "Make sure Docker containers are running: docker-compose up -d"
        }
    
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "message": f"Error: {str(e)}",
            "details": ""
        }


def check_services():
    """Check if required services are running."""
    payer_psp_url = _detect_payer_psp_url()
    
    print("Checking services...")
    try:
        with urllib.request.urlopen(f"{payer_psp_url.rstrip('/')}/health", timeout=2) as r:
            if r.status == 200:
                print(f"✓ Payer PSP is running at {payer_psp_url}")
                return True
            else:
                print(f"✗ Payer PSP health check failed (HTTP {r.status})")
                return False
    except Exception as e:
        print(f"✗ Cannot reach Payer PSP at {payer_psp_url}")
        print(f"  Error: {e}")
        print("\nPlease start Docker containers:")
        print("  docker-compose up -d")
        return False


def main():
    """Main interactive loop."""
    print("=" * 70)
    print("  UPI Transaction Test Script")
    print("  Test validation rules by sending transactions with different amounts")
    print("=" * 70)
    print()
    
    # Check services
    if not check_services():
        sys.exit(1)
    
    print()
    print("Default accounts:")
    print(f"  Payer:  {DEFAULT_PAYER_VPA} (Alice)")
    print(f"  Payee:  {DEFAULT_PAYEE_VPA} (Bob)")
    print()
    
    while True:
        print("-" * 70)
        print("Enter transaction details (or 'q' to quit):")
        print()
        
        # Get amount
        amount_input = input(f"Amount (INR) [default: 10.00]: ").strip()
        if amount_input.lower() == 'q':
            print("\nExiting...")
            break
        
        if not amount_input:
            amount = 10.0
        else:
            try:
                amount = float(amount_input)
                if amount < 0:
                    print("Error: Amount cannot be negative")
                    continue
            except ValueError:
                print("Error: Invalid amount. Please enter a number.")
                continue
        
        # Get PIN
        pin_input = input(f"UPI PIN [default: 1234]: ").strip()
        if pin_input.lower() == 'q':
            print("\nExiting...")
            break
        pin = pin_input if pin_input else "1234"
        
        # Optional: custom VPAs
        payer_vpa = DEFAULT_PAYER_VPA
        payee_vpa = DEFAULT_PAYEE_VPA
        
        print()
        print(f"Sending transaction:")
        print(f"  From:   {payer_vpa}")
        print(f"  To:     {payee_vpa}")
        print(f"  Amount: ₹{amount:.2f}")
        print(f"  PIN:    {'*' * len(pin)}")
        print()
        
        # Send transaction
        result = send_transaction(payer_vpa, payee_vpa, amount, pin)
        
        # Display result
        print("=" * 70)
        if result["success"]:
            print("✓ SUCCESS")
        else:
            print("✗ FAILED")
        
        print(f"Status: {result['message']}")
        if result["status_code"]:
            print(f"HTTP Status: {result['status_code']}")
        
        if result["details"]:
            print(f"\nResponse:")
            print(result["details"])
        
        print("=" * 70)
        print()
        
        # Check logs hint
        if result["success"]:
            print("💡 Tip: Check Docker logs to see the full transaction flow:")
            print("   docker logs upi-ai-main-rem_bank-1 --tail 20")
            print("   docker logs upi-ai-main-bene_bank-1 --tail 20")
            print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(0)
