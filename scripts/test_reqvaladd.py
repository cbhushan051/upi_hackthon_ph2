#!/usr/bin/env python3
"""
Test ReqValAdd: Payer PSP -> NPCI -> Payee PSP.
Run with: python scripts/test_reqvaladd.py
Requires: docker compose up -d npci payee_psp payer_psp
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
SAMPLE_XML = os.path.join(SCRIPT_DIR, "sample_reqvaladd.xml")
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


def _extract_reqvaladd_params(body: bytes) -> dict:
    """Extract key fields from ReqValAdd XML for display. Returns {} on parse error."""
    out = {}
    try:
        root = ET.fromstring(body)
        q = lambda n: f".//{{{NS}}}{n}"
        h = root.find(q("Head"))
        t = root.find(q("Txn"))
        payee = root.find(q("Payee"))
        if h is not None:
            out["Head.msgId"] = h.get("msgId", "")
            out["Head.orgId"] = h.get("orgId", "")
            out["Head.ver"] = h.get("ver", "")
        if t is not None:
            out["Txn.id"] = t.get("id", "")
            out["Txn.type"] = t.get("type", "")
        if payee is not None:
            out["Payee.addr"] = payee.get("addr", "")
            out["Payee.name"] = payee.get("name", "")
    except ET.ParseError:
        pass
    return out


PAYER_PSP = _detect_payer_psp_url()


def main():
    print("=" * 60)
    print("  ReqValAdd Test: Payer PSP -> NPCI -> Payee PSP")
    print("  Request schema : common/schemas/upi_req_valadd.xsd")
    print("  Response schema: common/schemas/upi_resp_valadd.xsd")
    print("=" * 60)
    print()

    # --- Parameters ---
    print("[Parameters]")
    print(f"  Payer PSP URL  : {PAYER_PSP}")
    print(f"  Sample file    : {SAMPLE_XML}")
    print(f"  Endpoint       : {PAYER_PSP.rstrip('/')}/api/reqvaladd")
    print(f"  Content-Type   : application/xml")
    print()

    # --- Step 1: Health ---
    print("[Step 1/4] Checking Payer PSP health...")
    try:
        with urllib.request.urlopen(f"{PAYER_PSP.rstrip('/')}/health", timeout=2) as r:
            if r.status == 200:
                print("  -> Payer PSP is up (HTTP 200).")
            else:
                print(f"  -> [WARN] /health returned {r.status}.")
    except Exception as e:
        print(f"  -> [WARN] Payer PSP not reachable: {e}")
    print()

    # --- Step 2: Load sample ---
    print("[Step 2/4] Loading sample ReqValAdd XML...")
    if not os.path.isfile(SAMPLE_XML):
        print(f"  -> ERROR: File not found: {SAMPLE_XML}")
        sys.exit(1)
    with open(SAMPLE_XML, "rb") as f:
        body = f.read()
    n = len(body)
    print(f"  -> Loaded {n} bytes from {os.path.basename(SAMPLE_XML)}.")
    params = _extract_reqvaladd_params(body)
    if params:
        print("  -> Request parameters (from sample):")
        for k, v in params.items():
            if v:
                print(f"       {k}: {v}")
    print()

    # --- Step 3: POST ---
    url = f"{PAYER_PSP.rstrip('/')}/api/reqvaladd"
    print("[Step 3/4] Sending POST /api/reqvaladd to Payer PSP...")
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
            print("    docker compose build npci payee_psp payer_psp")
            print("    docker compose up -d npci payee_psp payer_psp")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"  -> Request failed: {e}")
        print(f"  -> Tried: {url}")
        print("  1. Start: docker compose up -d npci payee_psp payer_psp")
        print("  2. Override: PAYER_PSP_URL=http://localhost:5060 python scripts/test_reqvaladd.py")
        sys.exit(1)
    print()

    # --- Step 4: Validate response ---
    print("[Step 4/4] Validating response (RespValAdd from Payee PSP)...")
    if status != 200:
        print(f"  -> FAIL: expected HTTP 200, got {status}.")
        print("  -> Response body:")
        print(data.decode("utf-8", errors="replace"))
        sys.exit(1)
    text = data.decode("utf-8", errors="replace")
    if "RespValAdd" not in text or "result=" not in text:
        print("  -> FAIL: expected RespValAdd XML with 'result' attribute.")
        print("  -> Response body:", text)
        sys.exit(1)
    print("  -> HTTP 200 and body is valid RespValAdd XML.")
    print()

    # --- Result ---
    print("=" * 60)
    print("  TEST PASSED: ReqValAdd -> RespValAdd flow succeeded.")
    print("  Flow: Payer PSP -> NPCI (validates ReqValAdd) -> Payee PSP")
    print("        -> Payee PSP returns RespValAdd -> NPCI (validates) -> Payer PSP.")
    print("=" * 60)
    print()
    print("[Response body (RespValAdd)]")
    print(text)


if __name__ == "__main__":
    main()
