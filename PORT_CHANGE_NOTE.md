# ⚠️ Port Change Notice

## Issue Encountered

Port **8088** was already in use by a HuggingFace text-embeddings container (`minilm-embed`).

## Solution

Payment UI now uses port **9992**.

## Current Configuration

### Payment UI
- **Port**: **9992** ✅
- **URL**: http://localhost:9992

### Other Services
- Orchestrator UI: http://localhost:9991
- NPCI: http://localhost:5050
- Payer PSP: http://localhost:5060
- Payee PSP: http://localhost:5070
- Remitter Bank: http://localhost:5080
- Beneficiary Bank: http://localhost:5090

### Conflicting Service
- HuggingFace Embeddings: http://localhost:8088 (minilm-embed container)

## Quick Start

```bash
# Start all services
docker-compose up -d

# Access Payment UI
open http://localhost:9992
```

## Verification

```bash
# Check health
curl http://localhost:9992/health
# Expected: {"status":"ok"}

# Check users
curl http://localhost:9992/api/users

# Check contacts
curl http://localhost:9992/api/contacts
```

## If Port 9992 Conflicts

Edit `payment_ui/app.py` (default port), `docker-compose.yml` (payment_ui ports), and `.env` (PAYMENT_UI_PORT) to use another port, then rebuild:
```bash
docker-compose up -d --build payment_ui
```

---

**Last Updated**: 2026-02-25
**Status**: ✅ Payment UI on port 9992

