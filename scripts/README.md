# Scripts

## Testing ReqValAdd (Payer PSP → NPCI → Payee PSP)

### 1. Start services

```bash
docker compose up -d npci payee_psp payer_psp
```

If you use custom ports in `.env` (e.g. `PAYER_PSP_PORT=5060`), see the host port:

```bash
docker compose port payer_psp 5004
# e.g. 0.0.0.0:5060
```

### 2. Run the test script

```bash
python scripts/test_reqvaladd.py
```

If your Payer PSP is on 5060:

```bash
# Windows PowerShell
$env:PAYER_PSP_URL="http://localhost:5060"; python scripts/test_reqvaladd.py

# Linux/macOS
PAYER_PSP_URL=http://localhost:5060 python scripts/test_reqvaladd.py
```

**Expected:** `OK: ReqValAdd -> 200 RespValAdd (Payer PSP -> NPCI -> Payee PSP)` and RespValAdd XML.

### 3. Or test with curl

```bash
# Replace :5060 with your payer_psp host port (see docker compose port payer_psp 5004)
curl -X POST http://localhost:5060/api/reqvaladd \
  -H "Content-Type: application/xml" \
  -d @scripts/sample_reqvaladd.xml
```

Expected: HTTP 200 and RespValAdd XML (per `common/schemas/upi_resp_valadd.xsd`) with `result="SUCCESS"` in `<Resp>`.

**Payee VPAs in samples (User seed @phonepe):**

| Payee.addr (VPA)       | Sample file                        |
|------------------------|------------------------------------|
| `Chandra@phonepe`     | `scripts/sample_reqvaladd.xml`     |
| `Gaurang@phonepe`         | `scripts/sample_reqvaladd_merchant.xml` |

To test the second address:

```bash
curl -X POST http://localhost:5060/api/reqvaladd \
  -H "Content-Type: application/xml" \
  -d @scripts/sample_reqvaladd_merchant.xml
```

### 4. Rebuild after code changes

```bash
docker compose build npci payee_psp payer_psp
docker compose up -d npci payee_psp payer_psp
```

### 5. Validate XSD (invalid XML → 400)

```bash
# Missing required Payee
curl -X POST http://localhost:5060/api/reqvaladd \
  -H "Content-Type: application/xml" \
  -d '<ReqValAdd xmlns="http://npci.org/upi/schema/"><Head ver="1" ts="x" orgId="x" msgId="x" prodType="UPI"/><Txn id="x" type="VALADD"/></ReqValAdd>'
```

Expected: HTTP 400 from NPCI (schema requires `Payee`).

---

## Testing ReqPay (Payer PSP → NPCI → rem_bank)

NPCI validates ReqPay, sets `Txn.type=DEBIT`, forwards to remitter bank (rem_bank) to debit the payer, then returns 202.

### 1. Start services

```bash
docker compose up -d npci payer_psp rem_bank
```

### 2. Run the test script

```bash
python scripts/test_reqpay.py
```

Override port: `PAYER_PSP_URL=http://localhost:5060 python scripts/test_reqpay.py`

**Expected:** `OK: ReqPay -> 202 Accepted (Payer PSP -> NPCI -> rem_bank)` and `{"status":"accepted"}`.

### 3. Or test with curl

```bash
curl -X POST http://localhost:5060/api/reqpay \
  -H "Content-Type: application/xml" \
  -d @scripts/sample_reqpay.xml
```

Expected: HTTP 202 and `{"status":"accepted"}`. NPCI forwards ReqPay with `Txn.type=DEBIT` to rem_bank. Schema: `common/schemas/upi_pay_request.xsd`.

---

## Debugging: viewing logs from APIs

Service output goes to stderr and is captured by Docker. Use:

```bash
# From the project root (where docker-compose.yml lives)
docker compose logs -f npci rem_bank
```

Or after a test: `docker compose logs --tail=100 npci rem_bank`.

**If you see no logs:**

1. **Run from the project root** so `docker compose` finds `docker-compose.yml`.
2. **Rebuild npci** (it has no volume; code is in the image):
   ```bash
   docker compose build npci
   docker compose up -d npci
   ```
3. **Restart rem_bank** after editing `rem_bank/` (volume mount; restart loads new code):
   ```bash
   docker compose up -d --force-recreate rem_bank
   ```
4. **Check that containers are up:** `docker compose ps`. For `npci` and `rem_bank` you should see "Up".
5. **Startup line:** After restart you should see e.g. `[rem_bank] Starting on 0.0.0.0:5005 (logs go to stderr -> docker compose logs)`. If that appears, logging works; run a test to see request logs.
