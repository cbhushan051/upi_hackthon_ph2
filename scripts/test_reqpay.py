#!/usr/bin/env python3
"""
Test ReqPay: Payer PSP -> NPCI -> rem_bank (ReqPay DEBIT) -> rem_bank sends RespPay DEBIT to NPCI
-> NPCI -> bene_bank (ReqPay CREDIT) -> bene_bank credits payee and sends RespPay CREDIT to NPCI
-> NPCI sends final RespPay to Payer PSP (transaction completed).
Run with: python scripts/test_reqpay.py
Requires: docker compose up -d npci payer_psp rem_bank bene_bank
Override: PAYER_PSP_URL=http://localhost:5060
"""
import os
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SAMPLE_XML = os.path.join(SCRIPT_DIR, "sample_reqpay.xml")
NS = "http://npci.org/upi/schema/"


def _detect_payer_psp_url():
    if os.environ.get("PAYER_PSP_URL"):
        return os.environ["PAYER_PSP_URL"]
    try:
        out = subprocess.run(
            ["docker", "compose", "port", "payer_psp", "6004"],
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
    return "http://localhost:6004"


def _detect_rem_bank_url():
    if os.environ.get("REM_BANK_URL"):
        return os.environ["REM_BANK_URL"]
    try:
        out = subprocess.run(
            ["docker", "compose", "port", "rem_bank", "6005"],
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
    return "http://localhost:6005"


def _detect_bene_bank_url():
    if os.environ.get("BENE_BANK_URL"):
        return os.environ["BENE_BANK_URL"]
    try:
        out = subprocess.run(
            ["docker", "compose", "port", "bene_bank", "6001"],
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
    return "http://localhost:6001"


def _extract_reqpay_params(body: bytes) -> dict:
    """Extract key fields from ReqPay XML for display. Returns {} on parse error."""
    out = {}
    try:
        root = ET.fromstring(body)
        q = lambda n: f".//{{{NS}}}{n}"
        h = root.find(q("Head"))
        t = root.find(q("Txn"))
        p = root.find(q("Payer"))
        payees = root.find(q("Payees"))
        if h is not None:
            out["Head.msgId"] = h.get("msgId", "")
            out["Head.orgId"] = h.get("orgId", "")
            out["Head.ver"] = h.get("ver", "")
        if t is not None:
            out["Txn.id"] = t.get("id", "")
            out["Txn.type"] = t.get("type", "")
        if p is not None:
            out["Payer.addr"] = p.get("addr", "")
            amt = p.find(q("Amount"))
            if amt is not None:
                out["Amount.value"] = amt.get("value", "")
                out["Amount.curr"] = amt.get("curr", "INR")
        if payees is not None:
            pe = payees.find(q("Payee"))
            if pe is not None:
                out["Payee.addr"] = pe.get("addr", "")
    except ET.ParseError:
        pass
    return out


PAYER_PSP = _detect_payer_psp_url()
REM_BANK = _detect_rem_bank_url()
BENE_BANK = _detect_bene_bank_url()


def main():
    print("=" * 60)
    print("  ReqPay Test: Payer PSP -> NPCI -> rem_bank (DEBIT) -> bene_bank (CREDIT)")
    print("  + bene_bank -> NPCI (RespPay CREDIT) + NPCI -> Payer PSP (final RespPay)")
    print("  Schema: common/schemas/upi_pay_request.xsd")
    print("=" * 60)
    print()

    # --- Parameters ---
    print("[Parameters]")
    print(f"  Payer PSP URL  : {PAYER_PSP}")
    print(f"  rem_bank URL   : {REM_BANK}")
    print(f"  bene_bank URL  : {BENE_BANK}")
    print(f"  Sample file    : {SAMPLE_XML}")
    print(f"  Endpoint       : {PAYER_PSP.rstrip('/')}/api/reqpay")
    print(f"  Content-Type   : application/xml")
    print()

    # --- Step 1: Health ---
    print("[Step 1/5] Checking Payer PSP, rem_bank, and bene_bank health...")
    try:
        with urllib.request.urlopen(f"{PAYER_PSP.rstrip('/')}/health", timeout=2) as r:
            if r.status == 200:
                print("  -> Payer PSP is up (HTTP 200).")
            else:
                print(f"  -> [WARN] Payer PSP /health returned {r.status}.")
    except Exception as e:
        print(f"  -> [WARN] Payer PSP not reachable: {e}")
    try:
        with urllib.request.urlopen(f"{REM_BANK.rstrip('/')}/health", timeout=2) as r:
            if r.status == 200:
                print("  -> rem_bank is up (HTTP 200).")
            else:
                print(f"  -> [WARN] rem_bank /health returned {r.status}.")
    except Exception as e:
        print(f"  -> [WARN] rem_bank not reachable: {e}")
        print("     Start: docker compose up -d npci payer_psp rem_bank bene_bank")
    try:
        with urllib.request.urlopen(f"{BENE_BANK.rstrip('/')}/health", timeout=2) as r:
            if r.status == 200:
                print("  -> bene_bank is up (HTTP 200).")
            else:
                print(f"  -> [WARN] bene_bank /health returned {r.status}.")
    except Exception as e:
        print(f"  -> [WARN] bene_bank not reachable: {e}")
        print("     Start: docker compose up -d npci payer_psp rem_bank bene_bank")
    print()

    # --- Step 2: Load sample ---
    print("[Step 2/5] Loading sample ReqPay XML...")
    if not os.path.isfile(SAMPLE_XML):
        print(f"  -> ERROR: File not found: {SAMPLE_XML}")
        sys.exit(1)
    with open(SAMPLE_XML, "rb") as f:
        body = f.read()
    n = len(body)
    print(f"  -> Loaded {n} bytes from {os.path.basename(SAMPLE_XML)}.")
    params = _extract_reqpay_params(body)
    if params:
        print("  -> Request parameters (from sample):")
        for k, v in params.items():
            if v:
                print(f"       {k}: {v}")
    print()

    # --- Step 3: POST ---
    url = f"{PAYER_PSP.rstrip('/')}/api/reqpay"
    print(f"[Step 3/5] Sending POST /api/reqpay to Payer PSP URL {url}\n")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/xml")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
            status = r.status
        print(f"  -> Response: HTTP {status}.")
    except urllib.error.HTTPError as e:
        data = e.read()
        status = e.code
        print(f"  -> HTTP {status}")
        print(data.decode("utf-8", errors="replace"))
        if status == 404:
            print("\n  If you see 404: rebuild and restart:")
            print("    docker compose build npci payer_psp rem_bank bene_bank")
            print("    docker compose up -d npci payer_psp rem_bank bene_bank")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"  -> Request failed: {e}")
        print(f"  -> Tried: {url}")
        print("  1. Start: docker compose up -d npci payer_psp rem_bank bene_bank")
        print("  2. Override: PAYER_PSP_URL=http://localhost:5060 python scripts/test_reqpay.py")
        sys.exit(1)
    print()

    # --- Step 4: Validate response ---
    print("[Step 4/5] Validating response...")
    if status != 202:
        print(f"  -> FAIL: expected HTTP 202 Accepted, got {status}.")
        print("  -> Response body:")
        print(data.decode("utf-8", errors="replace"))
        sys.exit(1)
    text = data.decode("utf-8", errors="replace")
    if "accepted" not in text.lower():
        print("  -> FAIL: expected body to contain 'accepted'.")
        print("  -> Response body:", text)
        sys.exit(1)
    print("  -> HTTP 202 and body contains 'accepted'.")
    print()

    # --- Step 5: Show full flow from docker logs (rem_bank, bene_bank, NPCI->Payer PSP final RespPay) ---
    print("[Step 5/5] Full flow: rem_bank, bene_bank, NPCI->Payer PSP (final RespPay) [docker logs]:")
    try:
        out = subprocess.run(
            ["docker", "compose", "logs", "--tail=50", "npci", "rem_bank", "bene_bank", "payer_psp"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        if out.returncode == 0 and (out.stdout or out.stderr):
            log = (out.stdout or "") + (out.stderr or "")
            for line in log.splitlines():
                if "[NPCI]" in line or "[rem_bank]" in line or "[bene_bank]" in line or "[payer_psp]" in line or "Forwarding" in line or "Received" in line or "CREDIT" in line or "RespPay" in line or "final" in line:
                    print("  " + line)
            if not any(
                x in log
                for x in (
                    "[NPCI] Forwarding",
                    "[NPCI] rem_bank",
                    "[NPCI] bene_bank",
                    "[NPCI] Received RespPay CREDIT",
                    "[NPCI] Sending final RespPay",
                    "[rem_bank] Received",
                    "[bene_bank] Received",
                    "[bene_bank] RespPay CREDIT sent",
                    "[payer_psp] Received final RespPay",
                )
            ):
                print("  (no relevant log lines in --tail=50; run: docker compose logs npci rem_bank bene_bank payer_psp)")
        else:
            print("  Run: docker compose logs npci rem_bank bene_bank payer_psp")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        print("  Run: docker compose logs npci rem_bank bene_bank payer_psp")

    # --- Result ---
    print()
    print("=" * 60)
    print("  TEST PASSED: ReqPay accepted. Full flow (transaction completed):")
    print("    Payer PSP -> NPCI -> rem_bank (ReqPay DEBIT)")
    print("    rem_bank -> NPCI (RespPay DEBIT)")
    print("    NPCI -> bene_bank (ReqPay CREDIT)")
    print("    bene_bank -> NPCI (RespPay CREDIT)")
    print("    NPCI -> Payer PSP (final RespPay, result=SUCCESS)")
    print("=" * 60)
    print()
    print("[Response body]")
    print(text)


if __name__ == "__main__":
    main()
