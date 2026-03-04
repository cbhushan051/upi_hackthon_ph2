# UPI-AI: Comprehensive Product & Knowledge Base Document

**Audience:** Business team, product team, sales, operations, and new team members  
**Purpose:** Understand the full product -- what it is, what was built, how it works, every component in detail

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Is This Product?](#2-what-is-this-product)
3. [Business Value & Use Cases](#3-business-value--use-cases)
4. [Architecture Overview](#4-architecture-overview)
5. [Service-by-Service Deep Dive](#5-service-by-service-deep-dive)
6. [UPI Payment Flow -- Step by Step](#6-upi-payment-flow----step-by-step)
7. [UPI Message Schemas (XSD) -- Complete Reference](#7-upi-message-schemas-xsd----complete-reference)
8. [AI Change Management -- Complete Reference](#8-ai-change-management----complete-reference)
9. [Database & Data Model](#9-database--data-model)
10. [API Endpoint Catalogue](#10-api-endpoint-catalogue)
11. [Configuration & Environment Variables](#11-configuration--environment-variables)
12. [Docker & Deployment](#12-docker--deployment)
13. [Test Data & Sample Payloads](#13-test-data--sample-payloads)
14. [Error Handling & Failure Modes](#14-error-handling--failure-modes)
15. [Technology Stack](#15-technology-stack)
16. [Repository Map -- File by File](#16-repository-map----file-by-file)
17. [Glossary of Terms](#17-glossary-of-terms)
18. [Important Disclaimers](#18-important-disclaimers)
19. [FAQ](#19-faq)

---

## 1. Executive Summary

**UPI-AI** is a simulation and demonstration platform with two core capabilities:

| Capability | What It Does |
|---|---|
| **UPI Payment Simulation** | Lets you run end-to-end UPI-like payments through a GPay-style UI. The payment flows through Payer PSP, NPCI Switch, Remitter Bank (debit), Beneficiary Bank (credit) -- exactly like real UPI. |
| **AI-Powered Change Management** | When someone describes a specification/policy change in plain English (e.g. "Add minimum transaction amount of Rs 50,000"), AI agents automatically interpret it, create a structured change manifest, update the relevant code in the bank services, and report status on a dashboard. |

**One-sentence pitch:** We built a working UPI payments simulator AND an AI-driven pipeline that turns plain-language policy changes into actual code updates across the ecosystem -- with full visibility via dashboards.

---

## 2. What Is This Product?

### 2.1 Two Products in One

**Product A -- Payment Simulation:**
- A Google Pay-inspired UI where you select a payer, a payee, enter an amount and PIN, and click "Pay".
- Behind the scenes, it generates XML messages (ReqPay, RespPay) that flow through 5 backend services just like real UPI.
- You can see every step of the payment -- from PIN validation to debit to credit -- displayed as an interactive step-by-step flow.

**Product B -- AI Change Management:**
- An Orchestrator dashboard where you type a specification change (e.g. "Support purpose code 44 for utility payments").
- An AI agent at NPCI creates a formal "Change Manifest" and dispatches it to bank agents.
- Each bank agent (Remitter Bank, Beneficiary Bank) uses an LLM to interpret the manifest, identifies which files need changes, edits the code, optionally restarts the Docker service, and reports status back.
- The dashboard tracks every agent's progress: RECEIVED -> APPLIED -> TESTED -> READY (or ERROR).

### 2.2 What This Is NOT

- Not production banking software. No real money moves.
- Not certified by NPCI or any regulator.
- Not secure (PINs stored in plaintext, no encryption, no auth).
- Intended for demos, learning, training, proof-of-concepts, and internal understanding.

---

## 3. Business Value & Use Cases

### 3.1 For Sales & Pre-sales

- **Live payment demo:** Run a payment in front of a prospect. They see the GPay-like UI, type an amount, and watch it succeed (or fail) in real time.
- **Live AI demo:** Submit a change like "Add validation for max transaction Rs 1 lakh" and watch agents propagate it across services in seconds.

### 3.2 For Product & Business

- **Understand UPI flows:** See exactly how a payment traverses Payer PSP -> NPCI -> Remitter Bank -> Beneficiary Bank, what XML is exchanged, and where validations happen.
- **Prototype new rules:** Describe a policy change in English; see how the AI agent would implement it across services.

### 3.3 For Training & Onboarding

- **New hires:** This is the best way to learn the UPI flow end-to-end with a running system.
- **Business analysts:** View the exact message formats (ReqPay, RespPay, etc.) and validation logic.

### 3.4 For Engineering & Architecture

- **Reference implementation:** Shows how microservices communicate in a UPI-like ecosystem.
- **AI code update pattern:** Demonstrates agent-to-agent communication, LLM-powered code generation, and structured change propagation.

---

## 4. Architecture Overview

### 4.1 System Diagram

```
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                             UPI-AI  ECOSYSTEM                                │
 │                                                                              │
 │  ┌─────────────────────┐                       ┌──────────────────────┐     │
 │  │   PAYMENT UI         │                       │   ORCHESTRATOR UI     │     │
 │  │   (Port 9992)   │                       │   (Port 9991)         │     │
 │  │   GPay-like screen   │                       │   Agent dashboard     │     │
 │  │   Builds ReqPay XML  │                       │   Deploy changes      │     │
 │  └─────────┬────────────┘                       └──────────┬────────────┘     │
 │            │                                               │                  │
 │            │ POST /api/reqpay                               │ POST /api/ui/    │
 │            │ (XML)                                         │  deploy (JSON)   │
 │            ▼                                               ▼                  │
 │  ┌─────────────────────┐                       ┌──────────────────────┐     │
 │  │   PAYER PSP          │                       │   ORCHESTRATOR        │     │
 │  │   (Port 5060)        │                       │   (backend)           │     │
 │  │   PIN validation     │                       │   Tracks agent status │     │
 │  │   Forward to NPCI    │                       │   Persists state      │     │
 │  └─────────┬────────────┘                       └──────────┬────────────┘     │
 │            │                                               │                  │
 │            │ POST /api/reqpay (XML)                        │ Proxies to NPCI  │
 │            ▼                                               ▼                  │
 │  ┌─────────────────────────────────────────────────────────────────────┐     │
 │  │                     NPCI  SWITCH  (Port 5050)                       │     │
 │  │   - XSD validates every message (ReqPay, RespPay, ValAdd)           │     │
 │  │   - Routes ReqPay -> DEBIT to Remitter Bank                        │     │
 │  │   - On DEBIT success -> CREDIT to Beneficiary Bank                 │     │
 │  │   - On CREDIT success -> final RespPay to Payer PSP                │     │
 │  │   - Hosts NPCI Agent (create manifests, dispatch to banks)          │     │
 │  └──────┬──────────────┬───────────────┬──────────────────┬────────────┘     │
 │         │              │               │                  │                  │
 │     DEBIT          CREDIT         ValAdd route        Manifests              │
 │         │              │               │                  │                  │
 │         ▼              ▼               ▼                  ▼                  │
 │  ┌────────────┐ ┌────────────┐ ┌────────────┐  ┌─────────────────────┐     │
 │  │ REMITTER   │ │ BENEFICIARY│ │ PAYEE PSP  │  │ Bank Agents          │     │
 │  │ BANK       │ │ BANK       │ │ (Port 5070)│  │ (inside Rem & Bene)  │     │
 │  │ (Port 5080)│ │ (Port 5090)│ │ VPA lookup │  │ LLM -> Code Updater  │     │
 │  │ Debit      │ │ Credit     │ │ Merchant   │  │ -> Docker restart    │     │
 │  │ account    │ │ account    │ │ profile    │  │ -> status report     │     │
 │  └────────────┘ └────────────┘ └────────────┘  └─────────────────────┘     │
 │                                                                              │
 └──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Communication Patterns

| From | To | Protocol | Content |
|---|---|---|---|
| Payment UI | Payer PSP | HTTP POST | ReqPay XML (with PIN in Creds) |
| Payer PSP | NPCI | HTTP POST | ReqPay XML (forwarded) |
| NPCI | Remitter Bank | HTTP POST | ReqPay XML (Txn.type=DEBIT) |
| Remitter Bank | NPCI | HTTP POST | RespPay XML (DEBIT result) |
| NPCI | Beneficiary Bank | HTTP POST | ReqPay XML (Txn.type=CREDIT) |
| Beneficiary Bank | NPCI | HTTP POST | RespPay XML (CREDIT result) |
| NPCI | Payer PSP | HTTP POST | Final RespPay XML (SUCCESS/FAILURE) |
| Payer PSP | NPCI (ValAdd) | HTTP POST | ReqValAdd XML |
| NPCI | Payee PSP (ValAdd) | HTTP POST | ReqValAdd XML |
| Payee PSP | NPCI (ValAdd) | HTTP Response | RespValAdd XML |
| Orchestrator UI | Orchestrator | HTTP POST JSON | Deploy request |
| Orchestrator | NPCI Agent | HTTP POST JSON | Create + dispatch manifest |
| NPCI Agent | Bank Agents | HTTP POST JSON (A2A) | Manifest delivery |
| Bank Agents | Orchestrator | HTTP POST JSON | Status updates |

---

## 5. Service-by-Service Deep Dive

### 5.1 Payment UI (Port 9992)

**What it does:** The user-facing payment screen. Looks like Google Pay.

**Key features:**
- User selection (payer accounts), contact grid (payee), amount input, PIN entry.
- Quick amount buttons (Rs 500, 1000, 2000, 5000).
- Builds a standards-compliant ReqPay XML with namespace `http://npci.org/upi/schema/`, including Head, Txn (type=PAY, optional purpose), Payer (addr, name, Creds/PIN, Amount), Payees/Payee.
- Sends the XML to Payer PSP; shows step-by-step flow on success.
- Also supports "edit mode" -- you can preview and manually edit the raw XML before sending (advanced/demo use).
- Transaction history stored in browser localStorage.

**Files:** `payment_ui/app.py` (Flask), `payment_ui/static/index.html`, `payment_ui/static/style.css`, `payment_ui/static/app.js`

**Key functions in app.py:**
- `build_reqpay_xml()` -- Builds the primary ReqPay XML including PIN Creds.
- `build_reqpay_debit_xml()` / `build_reqpay_credit_xml()` -- Builds display-only versions for the step flow.
- `create_transaction()` -- POST /api/transaction endpoint; validates, builds XML, sends to Payer PSP.
- `send_edited_reqpay()` -- POST /api/send-edited-reqpay; accepts user-edited XML.

---

### 5.2 Payer PSP (Port 5060)

**What it does:** Represents the Payment Service Provider of the person sending money.

**Key responsibilities:**
1. **PIN validation** -- Extracts Payer.addr (VPA) and Creds/PIN from ReqPay XML. Looks up the user in its own SQLite database and checks PIN matches.
2. **Forward to NPCI** -- If PIN is valid, forwards the ORIGINAL XML (byte-for-byte) to NPCI `/api/reqpay`.
3. **ReqValAdd proxy** -- Also supports `/api/reqvaladd` (VPA validation flow) by forwarding to NPCI.
4. **Receive final RespPay** -- Receives final RespPay from NPCI at `/api/resppay` (best-effort endpoint).

**Database:** `payer_psp/payer_psp.sqlite` -- User table (vpa, name, bank_code, psp_code, role, pin).

**Seed data:**

| VPA | Name | PIN | PSP Code |
|---|---|---|---|
| Chandra@paytm | Chandra | 1234 | PAYER_PSP |
| Gaurang@paytm | Gaurang | 1111 | PAYER_PSP |
| Hrithik@paytm | Hrithik | 1234 | PAYER_PSP |

**Error responses:**
- `MISSING_PIN` -- No PIN provided in Creds.
- `PAYER_NOT_FOUND` -- VPA not in database.
- `INVALID_PIN` -- PIN mismatch.

---

### 5.3 NPCI Switch (Port 5050)

**What it does:** The central switch/router -- the heart of UPI. Routes messages between PSPs and banks.

**Key responsibilities:**

1. **ReqPay routing (Pay flow):**
   - Receives ReqPay from Payer PSP.
   - Validates against `upi_pay_request.xsd`.
   - Converts Txn.type to DEBIT, stores context (payer, payee, amount, codes, names).
   - Forwards ReqPay DEBIT to Remitter Bank.
   - On error from Rem Bank: propagates error back to Payer PSP.

2. **RespPay routing:**
   - Receives RespPay DEBIT from Remitter Bank:
     - If SUCCESS: builds ReqPay CREDIT (preserving all original attributes -- payer_code, payee_code, names, seqNum, type) and sends to Beneficiary Bank.
     - If FAILURE: builds final RespPay FAILURE and sends to Payer PSP.
   - Receives RespPay CREDIT from Beneficiary Bank:
     - If SUCCESS: builds final RespPay SUCCESS and sends to Payer PSP.

3. **ReqValAdd routing (VPA validation flow):**
   - Receives ReqValAdd from Payer PSP.
   - Validates against `upi_req_valadd.xsd`.
   - Forwards to Payee PSP.
   - Receives RespValAdd, validates against `upi_resp_valadd.xsd`.
   - Optionally initiates a ReqPay DEBIT to Remitter Bank.

4. **Hosts NPCI Agent (Phase 2):**
   - `/api/agent/create-manifest` -- Creates and dispatches change manifests.
   - Uses LLM to interpret change description.

**XSD validation:** Every incoming and outgoing message is validated against the appropriate XSD in `common/schemas/`.

**State:** In-memory dictionary `_pending_debits` keyed by msgId -- stores context between DEBIT and CREDIT legs.

---

### 5.4 Remitter Bank (Port 5080)

**What it does:** The bank of the payer (sender). Debits the account.

**Key responsibilities:**
1. Parse ReqPay DEBIT -- extract payer VPA, amount, purpose code, payer code.
2. **Validations:**
   - Minimum transaction amount: currently Rs 65 (`MIN_TXN_AMOUNT = 65`).
   - Purpose code validation: only known codes accepted (e.g. "44" = Utility Payments).
   - Payer code "1111" blocked (demo rule).
   - Account existence check.
   - Sufficient balance check.
3. If all pass: debit the payer's account (reduce balance in SQLite).
4. Build RespPay (DEBIT) with result SUCCESS or FAILURE (with error code like `INSUFFICIENT_BALANCE`, `PAYER_NOT_FOUND`, `MIN_AMOUNT_VIOLATION`).
5. Send RespPay to NPCI `/api/resppay`.
6. **Hosts Remitter Bank Agent** -- receives manifests, applies code changes.

**Database:** `rem_bank/rem_bank.sqlite` -- Account table (id, vpa, name, bank_code, balance).

**Seed data:**

| Account ID | VPA | Name | Bank | Initial Balance |
|---|---|---|---|---|
| SBI-Chandra | Chandra@paytm | Chandra | SBI | Rs 1,000 |
| SBI-Gaurang | Gaurang@paytm | Gaurang | SBI | Rs 1,000 |
| SBI-Hrithik | Hrithik@paytm | Hrithik | SBI | Rs 1,000 |

---

### 5.5 Beneficiary Bank (Port 5090)

**What it does:** The bank of the payee (receiver). Credits the account.

**Key responsibilities:**
1. Parse ReqPay CREDIT -- extract payee VPA, amount, payer/payee codes, names.
2. **Validations:**
   - Minimum transaction amount: Rs 65 (`MIN_TRANSACTION_AMOUNT = 65.0`).
   - Payee code "1111" blocked (demo rule).
   - Account existence check.
3. If all pass: credit the payee's account (increase balance in SQLite).
4. Build RespPay (CREDIT) with result SUCCESS or FAILURE.
5. Send RespPay to NPCI `/api/resppay`.
6. **Hosts Beneficiary Bank Agent** -- receives manifests, applies code changes.

**Database:** `bene_bank/bene_bank.sqlite` -- Account table (id, vpa, name, bank_code, balance).

**Seed data:**

| Account ID | VPA | Name | Bank | Initial Balance |
|---|---|---|---|---|
| HDFC-Chandra | Chandra@phonepe | Chandra | HDFC | Rs 0 |
| HDFC-Gaurang | Gaurang@phonepe | Gaurang | HDFC | Rs 0 |
| HDFC-Hrithik | Hrithik@phonepe | Hrithik | HDFC | Rs 0 |

Note: Beneficiary bank accounts start at Rs 0 because they receive credits.

---

### 5.6 Payee PSP (Port 5070)

**What it does:** Represents the Payment Service Provider of the person receiving money.

**Key responsibilities:**
1. Receives ReqValAdd from NPCI.
2. Extracts Payee VPA (Payee.addr).
3. Looks up VPA in `ValAddProfile` table (merchant data).
4. Builds RespValAdd with profile data (mask name, merchant identifiers, ownership, etc.).
5. Returns RespValAdd to NPCI.

**Database:** `payee_psp/payee_psp.sqlite` -- User table + ValAddProfile table.

**ValAddProfile fields:** vpa, org_id, mask_name, code, type, ifsc, acc_type, iin, p_type, feature_supported, mid, sid, tid, merchant_type, merchant_genre, pin_code, reg_id_no, tier, on_boarding_type, brand_name, legal_name, franchise_name, ownership_type.

**Seed profiles:**

| VPA | Brand Name | Merchant Type | Ownership |
|---|---|---|---|
| payee@psp | Payee Brand | RETAIL | SOLE |
| merchant@payeepsp | Merchant Store | ECOM | PRIVATE |

---

### 5.7 Orchestrator (Port 9991)

**What it does:** Central coordination hub for the AI change management system.

**Key responsibilities:**
1. **Dashboard UI** -- Serves static HTML/JS/CSS from `orchestrator/static/`. Users can:
   - Enter a change description.
   - Toggle "Validation Rule" type.
   - Click "Deploy" to trigger AI agents.
   - View all tracked changes with per-agent status.
   - See detailed logs per agent (timestamps, messages, diffs).
2. **Change registration** -- `POST /api/orchestrator/register` receives manifest + receiver list.
3. **Status tracking** -- `POST /api/orchestrator/status` receives updates from agents (RECEIVED, APPLIED, TESTED, READY, ERROR).
4. **Deploy proxy** -- `POST /api/ui/deploy` proxies deploy requests to NPCI agent's `/api/agent/create-manifest`.
5. **Persistence** -- Saves state to `orchestrator_state.json` so changes survive restarts.

---

## 6. UPI Payment Flow -- Step by Step

### 6.1 Happy Path (Success)

```
Step 1: User clicks "Pay Rs 500" in Payment UI
        └──> Payment UI builds ReqPay XML (type=PAY, PIN in Creds, Amount=500.00)
             └──> POST to Payer PSP /api/reqpay

Step 2: Payer PSP
        └──> Extracts VPA (Chandra@paytm) and PIN (1234)
        └──> Looks up user in DB: found, PIN matches
        └──> Forwards ORIGINAL XML to NPCI /api/reqpay

Step 3: NPCI Switch
        └──> Validates XML against upi_pay_request.xsd: PASS
        └──> Changes Txn.type to DEBIT (preserves all other attributes)
        └──> Stores context: {msgId, payer_addr, payee_addr, amount, codes, names}
        └──> Sends ReqPay DEBIT to Remitter Bank /api/reqpay
        └──> Returns 202 Accepted to Payer PSP

Step 4: Remitter Bank
        └──> Parses ReqPay DEBIT: payer=Chandra@paytm, amount=500
        └──> Validates: amount >= 65 (MIN_TXN_AMOUNT)? YES
        └──> Validates: payer account exists? YES (SBI-Chandra, balance=1000)
        └──> Validates: balance >= 500? YES
        └──> Debits: balance 1000 - 500 = 500
        └──> Builds RespPay (DEBIT, SUCCESS, balAmt=500.00)
        └──> Sends RespPay to NPCI /api/resppay

Step 5: NPCI Switch
        └──> Validates RespPay against upi_resppay_response.xsd: PASS
        └──> RespPay DEBIT SUCCESS detected
        └──> Looks up pending debit context by reqMsgId
        └──> Builds ReqPay CREDIT (preserves payer_code, payee_code, names, amounts)
        └──> Sends ReqPay CREDIT to Beneficiary Bank /api/reqpay

Step 6: Beneficiary Bank
        └──> Parses ReqPay CREDIT: payee=Gaurang@phonepe, amount=500
        └──> Validates: amount >= 65? YES
        └──> Validates: payee account exists? YES (HDFC-Gaurang, balance=0)
        └──> Credits: balance 0 + 500 = 500
        └──> Builds RespPay (CREDIT, SUCCESS, balAmt=500.00)
        └──> Sends RespPay to NPCI /api/resppay

Step 7: NPCI Switch
        └──> RespPay CREDIT SUCCESS detected
        └──> Builds final RespPay (SUCCESS) for Payer PSP
        └──> Sends final RespPay to Payer PSP /api/resppay

Step 8: Payment UI shows SUCCESS animation
```

### 6.2 Failure Paths

**Invalid PIN:**
- Payer PSP rejects at Step 2 with `INVALID_PIN` (HTTP 400).
- Payment UI shows error immediately.

**Insufficient Balance:**
- Remitter Bank rejects at Step 4 with `INSUFFICIENT_BALANCE` (HTTP 400).
- NPCI builds final RespPay FAILURE and sends to Payer PSP.

**Amount Below Minimum (Rs 65):**
- Remitter Bank rejects at Step 4 with `MIN_AMOUNT_VIOLATION`.
- OR Beneficiary Bank rejects at Step 6.

**Payee Not Found:**
- Beneficiary Bank rejects at Step 6 with `PAYEE_NOT_FOUND`.

---

## 7. UPI Message Schemas (XSD) -- Complete Reference

All schemas are in `common/schemas/`. Namespace: `http://npci.org/upi/schema/`

### 7.1 ReqPay (upi_pay_request.xsd)

The primary payment request message.

**Structure:**
```
ReqPay
├── Head (required)
│   ├── @ver (required) -- e.g. "2.0"
│   ├── @ts (required) -- ISO timestamp
│   ├── @orgId (required) -- e.g. "PAYER_PSP", "NPCI"
│   ├── @msgId (required) -- unique message ID
│   └── @prodType (required) -- e.g. "UPI"
├── Txn (required)
│   ├── @id (required) -- transaction ID
│   ├── @type (required) -- "PAY", "DEBIT", or "CREDIT"
│   ├── @purpose (optional) -- e.g. "PAY", "44" for utility
│   ├── @note (optional) -- description
│   ├── @ts (optional)
│   ├── @initiationMode (optional)
│   └── QR (optional) -- QR code metadata
├── Payer (required)
│   ├── @addr (required) -- payer VPA, e.g. "Chandra@paytm"
│   ├── @name (optional)
│   ├── @seqNum (optional)
│   ├── @type (optional) -- e.g. "PERSON"
│   ├── @code (optional) -- e.g. "0000"
│   ├── Info (optional) -- Identity
│   ├── Device (optional) -- Device tags
│   ├── Ac (optional, max 4) -- Account details
│   ├── Consent (optional)
│   ├── Creds (optional) -- contains PIN
│   │   └── Cred
│   │       ├── @type -- "PIN"
│   │       └── Data -- PIN value as text content
│   └── Amount (required)
│       ├── @value -- decimal, e.g. "500.00"
│       └── @curr -- "INR"
└── Payees (required)
    └── Payee (1..n)
        ├── @addr (required) -- payee VPA
        ├── @name (optional)
        ├── @seqNum (optional)
        ├── @type (optional)
        ├── @code (optional)
        ├── Institution (optional)
        ├── Merchant (optional) -- with Identifier, Ownership, Invoice
        ├── Info, Device, Ac, Consent (optional)
        └── Amount (optional)
```

### 7.2 RespPay (upi_resppay_response.xsd)

The payment response message (from banks back to NPCI and finally to Payer PSP).

**Structure:**
```
RespPay
├── Head -- same as ReqPay Head
├── Txn
│   ├── @id (required)
│   ├── @type (required) -- "DEBIT", "CREDIT", or "PAY"
│   ├── @purpose (optional)
│   └── RiskScores (optional)
│       └── Score (0..n) -- provider, type, value
└── Resp
    ├── @reqMsgId (optional) -- correlates to original ReqPay msgId
    ├── @result (optional) -- "SUCCESS" or "FAILURE"
    ├── @errCode (optional) -- e.g. "INSUFFICIENT_BALANCE"
    ├── @actn (optional)
    ├── Ref (0..n) -- reference details
    │   ├── @balAmt -- remaining balance after transaction
    │   ├── @settAmount, @orgAmount, @settCurrency
    │   └── other attrs (type, seqNum, addr, code, etc.)
    └── Consent (0..n)
```

### 7.3 ReqValAdd (upi_req_valadd.xsd)

VPA validation / value-add request -- used to verify a VPA exists and retrieve merchant information.

**Structure:**
```
ReqValAdd
├── Head -- same as above
├── Txn
│   ├── @id (required)
│   ├── @type (required) -- typically "VALADD"
│   └── @ts, @note, @custRef, @refId, @refUrl (optional)
├── Payer (optional) -- minimal: @addr, @name, @seqNum, @type, @code
└── Payee (required) -- minimal: @addr, @name, @seqNum, @type, @code
```

### 7.4 RespValAdd (upi_resp_valadd.xsd)

Response to VPA validation -- returns payee profile and merchant data.

**Structure:**
```
RespValAdd
├── Head
├── Txn
└── Resp
    ├── @reqMsgId, @result, @errCode
    ├── @maskName -- masked name of account holder
    ├── @code, @type, @IFSC, @accType, @IIN, @pType
    ├── Merchant (optional)
    │   ├── Identifier -- mid, sid, tid, merchantType, merchantGenre, pinCode, etc.
    │   ├── Name -- brand, legal, franchise
    │   └── Ownership -- type (SOLE, PRIVATE, etc.)
    └── FeatureSupported (optional) -- @value
```

### 7.5 Other Schemas (placeholder/future)

| Schema | Purpose |
|---|---|
| `upi_collect_request.xsd` | Collect request (PayeeVPA, PayerVPA, Amount, Note) -- placeholder |
| `upi_status_request.xsd` | Status request (RRN) -- placeholder |
| `upi_status_response.xsd` | Status response (RRN, Status) -- placeholder |
| `upi_generic_response.xsd` | Generic response (RRN, Status) -- placeholder |

---

## 8. AI Change Management -- Complete Reference

### 8.1 Concepts

**Change Manifest:** A structured JSON document describing a specification change. Fields:
- `change_id` -- UUID, auto-generated.
- `change_type` -- One of: `xsd_update`, `api_change`, `business_logic`, `validation_rule`, `field_addition`, `field_modification`, `field_removal`.
- `description` -- Human-readable description.
- `affected_components` -- List of service names (e.g. `["rem_bank", "bene_bank"]`).
- `xsd_changes` -- Optional XSD-level changes.
- `code_changes` -- Dict with change instructions (interpreted by LLM).
- `test_requirements` -- List of tests to run.
- `created_by` -- Agent ID (e.g. "NPCI_AGENT").
- `timestamp` -- ISO datetime.
- `status` -- PENDING, DISPATCHED, COMPLETED.

**A2A (Agent-to-Agent) Protocol:** HTTP/JSON messages between agents:
- Message types: `MANIFEST`, `STATUS_UPDATE`, `ACK`, `ERROR`.
- Each message has: `message_type`, `sender`, `receiver`, `payload`, `message_id`, `correlation_id`.

### 8.2 Agent Status Lifecycle -- In Detail

Every bank agent (Remitter Bank, Beneficiary Bank) progresses through a fixed status lifecycle when processing a change manifest. The Orchestrator dashboard tracks and displays each status in real time.

#### Status Diagram

```
                           HAPPY PATH (normal flow)
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │   ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐ │
  │   │            │    │            │    │            │    │            │ │
  │   │  RECEIVED  │───>│  APPLIED   │───>│  TESTED    │───>│   READY    │ │
  │   │            │    │            │    │            │    │            │ │
  │   └─────┬──────┘    └─────┬──────┘    └─────┬──────┘    └────────────┘ │
  │         │                 │                 │                           │
  │         │                 │                 │          FAILURE PATHS    │
  │         ▼                 ▼                 ▼                           │
  │   ┌────────────┐    ┌────────────┐    ┌────────────┐                   │
  │   │   ERROR    │    │   ERROR    │    │   ERROR    │                   │
  │   │ (manifest  │    │ (code edit │    │ (test      │                   │
  │   │  parse or  │    │  failed,   │    │  failed,   │                   │
  │   │  LLM fail) │    │  syntax    │    │  restart   │                   │
  │   │            │    │  error)    │    │  failed)   │                   │
  │   └────────────┘    └────────────┘    └────────────┘                   │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘
```

#### Status Definitions -- What Happens at Each Stage

**1. RECEIVED -- "Manifest acknowledged, analysis started"**

| Aspect | Detail |
|---|---|
| **Trigger** | Agent receives manifest via A2A `POST /api/agent/manifest` |
| **What the agent does** | Stores the manifest; sends acknowledgement back to sender; reports RECEIVED to Orchestrator; begins reading its own source files to provide context to the LLM |
| **Visible on dashboard** | Agent card shows "RECEIVED" pill; log shows "Received manifest: '...description...'" |
| **What can go wrong** | Manifest JSON is malformed, agent service is down, Orchestrator is unreachable (warning only, does not block) |
| **Example log messages** | "Analyzing manifest for required changes...", "Identified 2 dependent files to update" |

**2. APPLIED -- "Code changes written to files"**

| Aspect | Detail |
|---|---|
| **Trigger** | Agent sends manifest + file contents to LLM; LLM returns change instructions; Code Updater edits files |
| **What the agent does** | For each file the LLM identifies: (a) creates a `.backup` copy, (b) applies the edit (add validation, modify constant, add function, etc.), (c) runs Python syntax check (`ast.parse`), (d) commits to git. If any file edit succeeds, status becomes APPLIED. |
| **Visible on dashboard** | Agent card shows "APPLIED" pill; logs show per-file entries like "Successfully updated rem_bank/app.py" with diff |
| **What can go wrong** | LLM returns code that causes a syntax error (backup is restored), file not found, LLM returns empty/unparseable response |
| **Example log messages** | "Applying changes to rem_bank/app.py...", "Successfully updated rem_bank/app.py", "Restarting Docker services: rem_bank..." |

**3. TESTED -- "Verification checks passed"**

| Aspect | Detail |
|---|---|
| **Trigger** | All file edits complete; agent runs verification |
| **What the agent does** | In current implementation: simulated test pause (1 second) then marks TESTED. In a production system this would run unit tests, integration tests, or health checks against the restarted service. Also attempts to restart the affected Docker container so new code is loaded. |
| **Visible on dashboard** | Agent card shows "TESTED" pill; logs show "Running verification tests...", "All verification tests passed" |
| **What can go wrong** | Docker restart fails (no docker-compose in container), test assertions fail (future) |
| **Example log messages** | "Running verification tests...", "All verification tests passed" |

**4. READY -- "Agent confirms: safe to deploy"**

| Aspect | Detail |
|---|---|
| **Trigger** | All tests pass |
| **What the agent does** | Sends final READY status to Orchestrator; moves manifest from pending to completed list |
| **Visible on dashboard** | Agent card shows green "READY" pill; this is the terminal success state |
| **What it means for business** | This agent's portion of the change is complete. When ALL agents show READY for a change, the entire change is considered deployment-ready. |
| **Example log messages** | "Validation complete. Ready for deployment." |

**5. ERROR -- "Something went wrong" (can occur from any stage)**

| Aspect | Detail |
|---|---|
| **Trigger** | Any unrecoverable failure during processing |
| **Common causes** | LLM timeout or invalid response; code edit causes syntax error and cannot be fixed; target file not found; Docker service won't restart |
| **What the agent does** | Reports ERROR with descriptive message to Orchestrator; stops processing |
| **Visible on dashboard** | Agent card shows red "ERROR" pill with error message in logs |
| **What it means for business** | Manual intervention is needed. Check the error message, fix the issue, and re-deploy the change. |

#### Functional Flow: From User Click to All-READY

```
 USER clicks "Deploy" in Orchestrator UI
   │
   ▼
 ORCHESTRATOR registers change, proxies to NPCI
   │
   ▼
 NPCI AGENT creates manifest, dispatches to 2 bank agents
   │
   ├──────────────────────────────────┐
   ▼                                  ▼
 REMITTER BANK AGENT               BENEFICIARY BANK AGENT
   │                                  │
   ▼                                  ▼
 [RECEIVED]                         [RECEIVED]
 "Got the manifest"                 "Got the manifest"
   │                                  │
   ▼                                  ▼
 LLM interprets manifest            LLM interprets manifest
 reads rem_bank/app.py               reads bene_bank/app.py
 reads rem_bank/db/db.py             reads bene_bank/db/db.py
   │                                  │
   ▼                                  ▼
 Code Updater edits files            Code Updater edits files
 backup -> edit -> syntax check      backup -> edit -> syntax check
   │                                  │
   ▼                                  ▼
 [APPLIED]                          [APPLIED]
 "Code updated in 1 file"           "Code updated in 1 file"
   │                                  │
   ▼                                  ▼
 Docker restart rem_bank             Docker restart bene_bank
 Run verification                    Run verification
   │                                  │
   ▼                                  ▼
 [TESTED]                           [TESTED]
 "Tests passed"                     "Tests passed"
   │                                  │
   ▼                                  ▼
 [READY]                            [READY]
 "Safe to deploy"                   "Safe to deploy"
   │                                  │
   └──────────────┬───────────────────┘
                  ▼
         ORCHESTRATOR DASHBOARD
         shows: ALL AGENTS READY
         Change is deployment-ready
```

#### What the Dashboard Shows at Each Stage

| Dashboard Element | RECEIVED | APPLIED | TESTED | READY | ERROR |
|---|---|---|---|---|---|
| **Status pill colour** | Blue | Yellow/Amber | Purple | Green | Red |
| **Agent card content** | "Received manifest..." | File names + diffs | "Tests passed" | "Ready for deployment" | Error message |
| **Log entries** | 1-2 entries | 3-5 entries (per file) | 1-2 entries | 1 entry | 1 entry with error detail |
| **Overall change status** | In progress | In progress | In progress | Complete (if all agents READY) | Needs attention |

#### Timing

| Stage | Typical Duration | What Determines Speed |
|---|---|---|
| RECEIVED | < 1 second | Network latency only |
| RECEIVED -> APPLIED | 5-20 seconds | LLM response time (depends on model and prompt size) |
| APPLIED -> TESTED | 2-5 seconds | Docker restart + simulated test |
| TESTED -> READY | < 1 second | Instant status update |
| **Total end-to-end** | **10-30 seconds** | Dominated by LLM inference time |

### 8.3 Agent Roles

| Agent | ID | Hosted In | Role |
|---|---|---|---|
| **NPCI Agent** | NPCI_AGENT | npci/app.py | Creates manifests from natural language; dispatches via A2A to bank agents |
| **Remitter Bank Agent** | REMITTER_BANK_AGENT | rem_bank/app.py | Receives manifests; uses LLM to generate code changes for rem_bank/; applies changes; restarts service |
| **Beneficiary Bank Agent** | BENEFICIARY_BANK_AGENT | bene_bank/app.py | Same as above but for bene_bank/ |

### 8.3 LLM Integration

**LLM Wrapper (`llm.py`):**
- Uses LangChain's `ChatOpenAI`.
- Configurable via env vars: `LLM_MODEL`, `LLM_API_KEY`/`OPENAI_API_KEY`, `LLM_BASE_URL`/`OPENAI_BASE_URL`.
- Default model: `NPCI_Greviance` (custom/local model).
- Default base URL: `http://183.82.7.228:9532/v1` (internal model server).
- Temperature: 0.2 (low, for deterministic outputs).
- Max tokens: 2048.
- **Fallback mode:** If LLM is unavailable, agents use basic/hardcoded change logic.

**How agents use LLM:**
1. Agent reads all its component files (e.g. `rem_bank/app.py`, `rem_bank/db/db.py`).
2. Sends a prompt to LLM with: manifest details + full file contents + instructions to produce JSON with file paths and change instructions.
3. LLM returns structured JSON like:
   ```json
   [
     {
       "file_path": "rem_bank/app.py",
       "changes": {
         "type": "add_validation",
         "insert_point": "...",
         "validation_code": "..."
       }
     }
   ]
   ```
4. Agent passes this to Code Updater.

### 8.4 Code Updater (`code_updater.py`)

Handles the actual file modifications. Supported change types:

| Type | What It Does |
|---|---|
| `add_function` | Inserts a new function after a specified anchor point |
| `modify_function` | Replaces an existing function body |
| `add_import` | Adds an import statement after the last existing import |
| `add_validation` | Inserts validation logic at a specified point with correct indentation |
| `modify_field` | Replaces one string with another (e.g. constant change) |
| `generic` (default) | Supports multiple strategies: replacements list, SEARCH/REPLACE blocks, code-fence diffs |

**Safety features:**
- Creates `.backup` file before every edit.
- Runs Python `ast.parse()` syntax check on modified files; restores backup if syntax is broken.
- Optional git commit per change.

### 8.5 Docker Manager (`docker_manager.py`)

Maps modified file paths to Docker Compose service names:

| Path prefix | Service |
|---|---|
| `bene_bank/` | bene_bank |
| `rem_bank/` | rem_bank |
| `npci/` | npci |
| `payee_psp/` | payee_psp |
| `payer_psp/` | payer_psp |

Can restart individual services or all services via `docker-compose stop` + `docker-compose up -d`.

### 8.6 End-to-End AI Flow Example

**User input:** "Add minimum transaction amount of Rs 50,000"

1. **Orchestrator UI** sends: `POST /api/ui/deploy` with `{description: "Add minimum transaction amount of Rs 50,000", receivers: ["REMITTER_BANK_AGENT", "BENEFICIARY_BANK_AGENT"]}`.
2. **Orchestrator** proxies to NPCI `/api/agent/create-manifest`.
3. **NPCI Agent** creates manifest: `{change_type: "validation_rule", description: "...", affected_components: ["rem_bank", "bene_bank"]}`.
4. **NPCI Agent** registers change with Orchestrator.
5. **NPCI Agent** dispatches manifest to Remitter Bank Agent and Beneficiary Bank Agent via A2A.
6. **Remitter Bank Agent:**
   - Status: RECEIVED ("Analyzing manifest...")
   - Reads `rem_bank/app.py` and `rem_bank/db/db.py`.
   - Sends to LLM: "Change MIN_TXN_AMOUNT to 50000 in rem_bank/app.py".
   - LLM returns: `[{file_path: "rem_bank/app.py", changes: {type: "modify_field", old_field: "MIN_TXN_AMOUNT = 65", new_field: "MIN_TXN_AMOUNT = 50000"}}]`.
   - Code Updater edits file, creates backup, syntax-checks.
   - Status: APPLIED ("Successfully updated rem_bank/app.py").
   - Attempts Docker restart of `rem_bank`.
   - Status: TESTED ("All verification tests passed").
   - Status: READY ("Validation complete. Ready for deployment.").
7. **Beneficiary Bank Agent:** Same process for `bene_bank/app.py`.
8. **Orchestrator dashboard** shows both agents at READY.

---

## 9. Database & Data Model

### 9.1 Payer PSP Database

**File:** `payer_psp/payer_psp.sqlite`  
**ORM:** SQLAlchemy

**Table: `users`**

| Column | Type | Notes |
|---|---|---|
| id | Integer (PK) | Auto-increment |
| vpa | String(255) | Unique, not null. e.g. "Chandra@paytm" |
| name | String(255) | Not null |
| bank_code | String(64) | Nullable |
| psp_code | String(64) | Nullable. e.g. "PAYER_PSP" |
| role | String(32) | Not null. Always "payer_psp" |
| pin | String(10) | Not null. Default "1234" |

### 9.2 Remitter Bank Database

**File:** `rem_bank/rem_bank.sqlite`

**Table: `accounts`**

| Column | Type | Notes |
|---|---|---|
| id | String(64) (PK) | e.g. "SBI-Chandra" |
| vpa | String(255) | Unique, not null |
| name | String(255) | Not null |
| bank_code | String(64) | Not null. e.g. "SBI" |
| balance | Float | Not null. Default 0.0 |

### 9.3 Beneficiary Bank Database

**File:** `bene_bank/bene_bank.sqlite`

**Table: `accounts`** -- Same schema as Remitter Bank.

| Account ID | VPA | Bank | Initial Balance |
|---|---|---|---|
| HDFC-Chandra | Chandra@phonepe | HDFC | 0 |
| HDFC-Gaurang | Gaurang@phonepe | HDFC | 0 |
| HDFC-Hrithik | Hrithik@phonepe | HDFC | 0 |

### 9.4 Payee PSP Database

**File:** `payee_psp/payee_psp.sqlite`

**Table: `users`** -- Same as Payer PSP users (without PIN). VPAs: Chandra@phonepe, Gaurang@phonepe, Hrithik@phonepe.

**Table: `valadd_profiles`**

| Column | Type | Notes |
|---|---|---|
| vpa | String(255) (PK) | Payee VPA |
| org_id | String(64) | e.g. "PAYEE_PSP" |
| mask_name | String(255) | Masked name of account holder |
| code, type, ifsc, acc_type, iin, p_type | String | Account info attributes |
| feature_supported | String(255) | e.g. "UPI" |
| mid, sid, tid | String(64) | Merchant identifiers |
| merchant_type, merchant_genre | String(64) | e.g. "RETAIL", "ECOM" |
| pin_code, reg_id_no, tier, on_boarding_type | String | Additional merchant info |
| brand_name, legal_name, franchise_name | String(255) | Merchant name variants |
| ownership_type | String(32) | e.g. "SOLE", "PRIVATE" |

### 9.5 Orchestrator State

**File:** `orchestrator_state.json`

Not a database -- a JSON file. Structure:
```json
{
  "change_tracking": {
    "<change_id>": {
      "manifest": { ... },
      "receivers": ["REMITTER_BANK_AGENT", "BENEFICIARY_BANK_AGENT"],
      "statuses": {
        "REMITTER_BANK_AGENT": "READY",
        "BENEFICIARY_BANK_AGENT": "APPLIED"
      },
      "details": {
        "REMITTER_BANK_AGENT": {
          "logs": [
            {"timestamp": "...", "status": "RECEIVED", "message": "..."},
            {"timestamp": "...", "status": "APPLIED", "message": "..."}
          ]
        }
      },
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```

---

## 10. API Endpoint Catalogue

### 10.1 Payment UI (Port 9992)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/` | Serve the UI | -- | HTML |
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| GET | `/api/users` | List payer users | -- | JSON array |
| GET | `/api/contacts` | List payee contacts | -- | JSON array |
| POST | `/api/transaction` | Process payment | `{payer_vpa, payee_vpa, amount, pin}` | JSON with steps |
| POST | `/api/send-edited-reqpay` | Send edited XML | `{xml, payer_vpa, amount}` | JSON with steps |
| POST | `/api/preview-reqpay` | Preview ReqPay XML | `{payer_vpa, payee_vpa, amount, pin}` | `{xml}` |

### 10.2 Payer PSP (Port 5060)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| POST | `/api/reqpay` | Receive ReqPay XML, validate PIN, forward to NPCI | XML body | XML or JSON error |
| POST | `/api/reqvaladd` | Forward ReqValAdd to NPCI | XML body | XML response |
| POST | `/api/resppay` | Receive final RespPay from NPCI | XML body | JSON ack |

### 10.3 NPCI Switch (Port 5050)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| POST | `/api/reqpay` | Receive ReqPay, validate, route DEBIT to Rem Bank | XML body | JSON 202 or error |
| POST | `/api/resppay` | Receive RespPay from banks, route next leg | XML body | JSON ack |
| POST | `/api/reqvaladd` | Receive ReqValAdd, validate, route to Payee PSP | XML body | XML response |
| POST | `/api/agent/create-manifest` | Create and dispatch change manifest (AI) | JSON | JSON with manifest |
| POST | `/api/agent/manifest` | Receive manifest (A2A, if NPCI is a receiver) | JSON A2A message | JSON ack |

### 10.4 Remitter Bank (Port 5080)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| POST | `/api/reqpay` | Receive DEBIT ReqPay, debit account, send RespPay | XML body | JSON 202 or error |
| POST | `/api/agent/manifest` | Receive change manifest (A2A) | JSON A2A message | JSON result |
| GET | `/api/agent/status/<change_id>` | Get agent status for a change | -- | JSON status |

### 10.5 Beneficiary Bank (Port 5090)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| POST | `/api/reqpay` | Receive CREDIT ReqPay, credit account, send RespPay | XML body | JSON 202 or error |
| POST | `/api/agent/manifest` | Receive change manifest (A2A) | JSON A2A message | JSON result |
| GET | `/api/agent/status/<change_id>` | Get agent status for a change | -- | JSON status |

### 10.6 Payee PSP (Port 5070)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| POST | `/api/reqvaladd` | Receive ReqValAdd, look up profile, return RespValAdd | XML body | XML response |

### 10.7 Orchestrator (Port 9991)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| GET | `/` | Serve dashboard UI | -- | HTML |
| GET | `/health` | Health check | -- | `{"status": "ok"}` |
| POST | `/api/orchestrator/status` | Receive agent status updates | `{change_id, agent_id, status, details}` | `{"status": "updated"}` |
| GET | `/api/orchestrator/change/<id>` | Get status for a change | -- | JSON |
| GET | `/api/orchestrator/changes` | Get all tracked changes | -- | JSON dict |
| GET | `/api/orchestrator/summary` | Get summary counts | -- | `{total_changes, all_ready, in_progress}` |
| POST | `/api/orchestrator/register` | Register a new change | `{manifest, receivers}` | `{status, change_id}` |
| POST | `/api/ui/deploy` | Proxy deploy request to NPCI agent | `{description, change_type, receivers}` | JSON |

---

## 11. Configuration & Environment Variables

### 11.1 Key Variables

| Variable | Default | Used By | Purpose |
|---|---|---|---|
| `PORT` | varies | All services | HTTP port for the service |
| `PAYMENT_UI_PORT` | 9992 | Payment UI | External port mapping |
| `ORCHESTRATOR_PORT` | 9991 | Orchestrator | External port mapping (container listens on 6000) |
| `PAYER_PSP_PORT` | 5060 | Docker Compose | External port mapping |
| `NPCI_PORT` | 5050 | Docker Compose | External port mapping |
| `BENE_BANK_PORT` | 5090 | Docker Compose | External port mapping |
| `REM_BANK_PORT` | 5080 | Docker Compose | External port mapping |
| `PAYEE_PSP_PORT` | 5070 | Docker Compose | External port mapping |
| `NPCI_URL` | `http://npci:5002` | NPCI clients | URL to reach NPCI (Docker internal) |
| `REM_BANK_URL` | `http://rem_bank:5005` | NPCI | URL to reach Remitter Bank |
| `BENE_BANK_URL` | `http://bene_bank:5001` | NPCI | URL to reach Beneficiary Bank |
| `PAYEE_PSP_URL` | `http://payee_psp:5003` | NPCI | URL to reach Payee PSP |
| `PAYER_PSP_URL` | `http://payer_psp:5004` | NPCI / Payment UI | URL to reach Payer PSP / send ReqPay |
| `ORCHESTRATOR_URL` | `http://orchestrator:6000` | Agents (internal) | URL to report status (host: 9991) |
| `DATABASE_URL` | SQLite file path | All DB services | Database connection string |
| `LLM_MODEL` | `NPCI_Greviance` | LLM wrapper | Model name |
| `LLM_API_KEY` / `OPENAI_API_KEY` | `sk-xxx` | LLM wrapper | API key |
| `LLM_BASE_URL` / `OPENAI_BASE_URL` | `http://183.82.7.228:9532/v1` | LLM wrapper | LLM API endpoint |
| `FLASK_DEBUG` | `0` | All Flask apps | Debug mode |
| `PYTHONUNBUFFERED` | `1` | Docker | Force unbuffered output |

### 11.2 .env File

All Docker services load `.env` from project root. Override any of the above variables there.

---

## 12. Docker & Deployment

### 12.1 Docker Compose Services

The `docker-compose.yml` defines 7 services:

| Service | Dockerfile | Internal Port | External Port | Volumes | Notes |
|---|---|---|---|---|---|
| `bene_bank` | `bene_bank/Dockerfile` | 5001 | 5090 | `.:/app` | Mounts full repo; `PYTHONPATH=/app:/app/bene_bank` |
| `npci` | `npci/Dockerfile` | 5002 | 5050 | `.:/app` | Mounts full repo for agent access |
| `payee_psp` | `payee_psp/Dockerfile` | 5003 | 5070 | -- | Standalone build |
| `payer_psp` | `payer_psp/Dockerfile` | 5004 | 5060 | -- | Standalone build |
| `rem_bank` | `rem_bank/Dockerfile` | 5005 | 5080 | `.:/app` | Mounts full repo; `PYTHONPATH=/app:/app/rem_bank` |
| `orchestrator` | `Dockerfile.orchestrator` | 6000 | 9991 | `.:/app` | Mounts full repo (host port 9991) |
| `payment_ui` | `payment_ui/Dockerfile` | 9992 | 9992 | -- | Standalone build |

### 12.2 Why Some Services Mount `.:/app`

Services that host AI agents (bene_bank, rem_bank, npci, orchestrator) mount the full repo so the Code Updater and agent modules can access shared code (`agents/`, `manifest.py`, `llm.py`, etc.).

### 12.3 Commands

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f              # all
docker-compose logs -f npci          # NPCI only
docker-compose logs --tail=100 rem_bank

# Restart a service
docker-compose restart rem_bank

# Stop everything
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

---

## 13. Test Data & Sample Payloads

### 13.1 Test Users Summary

**Payers (Payer PSP + Remitter Bank):**

| Name | Payer VPA | PIN | Rem Bank Account | Bank | Balance |
|---|---|---|---|---|---|
| Chandra | Chandra@paytm | 1234 | SBI-Chandra | SBI | Rs 1,000 |
| Gaurang | Gaurang@paytm | 1111 | SBI-Gaurang | SBI | Rs 1,000 |
| Hrithik | Hrithik@paytm | 1234 | SBI-Hrithik | SBI | Rs 1,000 |

**Payees (Beneficiary Bank + Payee PSP):**

| Name | Payee VPA | Bene Bank Account | Bank | Balance |
|---|---|---|---|---|
| Chandra | Chandra@phonepe | HDFC-Chandra | HDFC | Rs 0 |
| Gaurang | Gaurang@phonepe | HDFC-Gaurang | HDFC | Rs 0 |
| Hrithik | Hrithik@phonepe | HDFC-Hrithik | HDFC | Rs 0 |

### 13.2 Sample ReqPay XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ReqPay xmlns="http://npci.org/upi/schema/">
  <Head ver="2.0" ts="2024-01-15T10:00:00" orgId="PAYER_PSP" msgId="pay-1" prodType="UPI"/>
  <Txn id="txn-pay-1" type="PAY" purpose="PAY"/>
  <Payer addr="Chandra@paytm" name="Chandra">
    <Amount value="100.00" curr="INR"/>
  </Payer>
  <Payees>
    <Payee addr="Gaurang@phonepe" name="Gaurang"/>
  </Payees>
</ReqPay>
```

### 13.3 Sample ReqValAdd XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ReqValAdd xmlns="http://npci.org/upi/schema/">
  <Head ver="2.0" ts="2024-01-15T10:00:00" orgId="PAYER_PSP" msgId="msg-1" prodType="UPI"/>
  <Txn id="txn-1" type="VALADD"/>
  <Payer addr="Chandra@paytm" name="Chandra"/>
  <Payee addr="Chandra@phonepe" name="Chandra"/>
</ReqValAdd>
```

### 13.4 Sample ReqPay with PIN (as built by Payment UI)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ns:ReqPay xmlns:ns="http://npci.org/upi/schema/">
  <ns:Head ver="2.0" ts="2026-02-09T10:00:00Z" orgId="PAYER_PSP"
           msgId="MSG20260209100000123" prodType="UPI"/>
  <ns:Txn id="TXN20260209100000123" note="UPI Payment" type="PAY"
          ts="2026-02-09T10:00:00Z" purpose="PAY"/>
  <ns:Payer addr="Chandra@paytm" name="Payer Name" seqNum="1"
            type="PERSON" code="0000">
    <ns:Creds>
      <ns:Cred type="PIN">
        <ns:Data>1234</ns:Data>
      </ns:Cred>
    </ns:Creds>
    <ns:Amount value="500.00" curr="INR"/>
  </ns:Payer>
  <ns:Payees>
    <ns:Payee addr="Gaurang@phonepe" name="Payee Name" seqNum="1"
              type="PERSON" code="0000">
      <ns:Amount value="500.00" curr="INR"/>
    </ns:Payee>
  </ns:Payees>
</ns:ReqPay>
```

### 13.5 Sample A2A Manifest Message

```json
{
  "message_type": "MANIFEST",
  "sender": "NPCI_AGENT",
  "receiver": "REMITTER_BANK_AGENT",
  "payload": {
    "manifest": {
      "change_id": "a1b2c3d4-...",
      "change_type": "validation_rule",
      "description": "Add minimum transaction amount of Rs 50,000",
      "affected_components": ["rem_bank", "bene_bank"],
      "code_changes": {"prompt": "Add minimum transaction amount of Rs 50,000"},
      "test_requirements": [],
      "created_by": "NPCI_AGENT",
      "timestamp": "2026-02-09T10:00:00Z",
      "status": "DISPATCHED"
    }
  },
  "message_id": "msg-xyz",
  "correlation_id": "a1b2c3d4-..."
}
```

---

## 14. Error Handling & Failure Modes

### 14.1 Payment Errors

| Error Code | Where | Meaning |
|---|---|---|
| `MISSING_PIN` | Payer PSP | No PIN in ReqPay Creds |
| `PAYER_NOT_FOUND` | Payer PSP or Rem Bank | VPA not in database |
| `INVALID_PIN` | Payer PSP | PIN does not match |
| `INSUFFICIENT_BALANCE` | Remitter Bank | Payer balance < amount |
| `MIN_AMOUNT_VIOLATION` | Remitter Bank | Amount < Rs 65 |
| `MIN_AMOUNT_NOT_MET` | Beneficiary Bank | Amount < Rs 65 |
| `PAYEE_NOT_FOUND` | Beneficiary Bank | Payee VPA not in database |
| `Code Blocked for Demo` | Rem/Bene Bank | Payer/Payee code = "1111" (demo rule) |
| `INVALID_REQUEST` | NPCI | Could not build debit message |
| `REM_BANK_UNREACHABLE` | NPCI | Remitter Bank service is down |

### 14.2 XSD Validation Errors

NPCI validates all XML messages against XSDs. If validation fails:
- Returns HTTP 400 with error message like "ReqPay does not match schema: ..."
- Common causes: missing required attributes (ver, ts, orgId, msgId, prodType), wrong element order (Creds must come before Amount in Payer per XSD).

### 14.3 AI Agent Errors

| Scenario | Result |
|---|---|
| LLM unavailable | Agent falls back to basic/hardcoded changes |
| LLM returns invalid JSON | Agent reports ERROR to Orchestrator |
| Code edit causes syntax error | Code Updater restores backup, reports failure |
| Docker restart fails | Agent reports ERROR but change may still be applied in code |
| Orchestrator unreachable | Agent logs warning but continues processing |

---

## 15. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Language** | Python | 3.11+ | All backend services |
| **Web framework** | Flask | 3.0 | HTTP APIs and static serving |
| **Database** | SQLite | built-in | Per-service data (users, accounts, profiles) |
| **ORM** | SQLAlchemy | 2.x | Database access |
| **XML processing** | lxml (NPCI), xml.etree (others) | -- | XML parse, build, XSD validation |
| **AI / LLM** | LangChain + ChatOpenAI | latest | Manifest interpretation, code generation |
| **Frontend** | HTML, CSS, Vanilla JavaScript | -- | Payment UI and Orchestrator dashboard |
| **Containerization** | Docker, Docker Compose | -- | Service orchestration |
| **HTTP client** | requests | -- | Inter-service communication |
| **Environment** | python-dotenv | -- | .env loading |

---

## 16. Repository Map -- File by File

### Root directory

| File/Folder | Purpose |
|---|---|
| `docker-compose.yml` | Defines all 7 Docker services |
| `Dockerfile.orchestrator` | Dockerfile for orchestrator service |
| `.env` | Environment variable overrides |
| `orchestrator.py` | Orchestrator backend (Flask) -- status tracking, deploy proxy |
| `manifest.py` | ChangeManifest class and ChangeType enum |
| `a2a_protocol.py` | A2AMessage, A2AClient for inter-agent communication |
| `code_updater.py` | CodeUpdater class -- applies file edits, backups, git |
| `docker_manager.py` | DockerManager -- maps files to services, restarts containers |
| `llm.py` | LLM wrapper (LangChain ChatOpenAI) |
| `agent_api.py` | Flask blueprint for agent endpoints (standalone mode) |
| `agent.py` | Standalone agent runner |
| `demo.py` | Demo script to test the full pipeline |
| `orchestrator_state.json` | Persistent state file for Orchestrator |

### `agents/` -- AI Agent implementations

| File | Purpose |
|---|---|
| `__init__.py` | Exports NPCIAgent, RemitterBankAgent, BeneficiaryBankAgent |
| `base_agent.py` | BaseAgent (abstract): receive_manifest, update_status, status history |
| `npci_agent.py` | NPCIAgent: create_manifest, dispatch_manifest via A2A |
| `remitter_bank_agent.py` | RemitterBankAgent: process_manifest with LLM + CodeUpdater for rem_bank/ |
| `beneficiary_bank_agent.py` | BeneficiaryBankAgent: process_manifest with LLM + CodeUpdater for bene_bank/ |

### `npci/` -- NPCI Switch service

| File | Purpose |
|---|---|
| `app.py` | 833-line Flask app: ReqPay/RespPay/ValAdd routing, XSD validation, NPCI Agent endpoints |
| `Dockerfile` | Docker build config |
| `requirements.txt` | Python dependencies |

### `payer_psp/` -- Payer PSP service

| File | Purpose |
|---|---|
| `app.py` | Flask app: PIN validation, forward to NPCI, receive final RespPay |
| `db/db.py` | User table, seed data, upsert_user |
| `Dockerfile`, `requirements.txt` | Build config |

### `payee_psp/` -- Payee PSP service

| File | Purpose |
|---|---|
| `app.py` | Flask app: ReqValAdd handler, builds RespValAdd from ValAddProfile |
| `db/db.py` | User + ValAddProfile tables, seed data, get_valadd_profile |
| `Dockerfile`, `requirements.txt` | Build config |

### `rem_bank/` -- Remitter Bank service

| File | Purpose |
|---|---|
| `app.py` | Flask app: DEBIT handler, debit logic, RespPay builder, Rem Bank Agent endpoints |
| `db/db.py` | Account table, seed data, get_account_by_vpa |
| `Dockerfile`, `requirements.txt` | Build config |

### `bene_bank/` -- Beneficiary Bank service

| File | Purpose |
|---|---|
| `app.py` | Flask app: CREDIT handler, credit logic, RespPay builder, Bene Bank Agent endpoints |
| `db/db.py` | Account table, seed data, get_account_by_vpa |
| `Dockerfile`, `requirements.txt` | Build config |

### `payment_ui/` -- Payment UI

| File | Purpose |
|---|---|
| `app.py` | Flask app: transaction processing, XML building, user/contact APIs |
| `static/index.html` | GPay-inspired UI |
| `static/style.css` | Styles (700+ lines, Material Design) |
| `static/app.js` | Frontend logic (payment flow, history, XML preview) |
| `Dockerfile`, `requirements.txt` | Build config |

### `orchestrator/static/` -- Orchestrator dashboard UI

| File | Purpose |
|---|---|
| `index.html` | Dashboard layout |
| `style.css` | Dashboard styles |
| `app.js` | Deploy handler, change polling, status rendering |

### `common/schemas/` -- XSD schemas

| File | Message Type |
|---|---|
| `upi_pay_request.xsd` | ReqPay |
| `upi_resppay_response.xsd` | RespPay |
| `upi_req_valadd.xsd` | ReqValAdd |
| `upi_resp_valadd.xsd` | RespValAdd |
| `upi_collect_request.xsd` | CollectRequest (placeholder) |
| `upi_status_request.xsd` | StatusRequest (placeholder) |
| `upi_status_response.xsd` | StatusResponse (placeholder) |
| `upi_generic_response.xsd` | GenericResponse (placeholder) |

### `scripts/` -- Helper scripts

| File | Purpose |
|---|---|
| `interactive_test.py` | Interactive payment tester |
| `test_reqpay.py` | Automated ReqPay test |
| `test_reqvaladd.py` | Automated ReqValAdd test |
| `check_balances.py` | Check account balances |
| `check_account.py` | Check specific account |
| `demo_phase2_docker.py` | Demo AI agent flow in Docker |
| `sample_reqpay.xml` | Sample ReqPay XML |
| `sample_reqvaladd.xml` | Sample ReqValAdd XML |
| `sample_reqvaladd_merchant.xml` | Sample merchant ReqValAdd |

---

## 17. Glossary of Terms

| Term | Definition |
|---|---|
| **UPI** | Unified Payments Interface -- India's real-time payment system run by NPCI |
| **NPCI** | National Payments Corporation of India -- operates UPI infrastructure |
| **VPA** | Virtual Payment Address -- e.g. "Chandra@paytm"; UPI identifier for a user |
| **PSP** | Payment Service Provider -- bank/app that provides UPI to users (e.g. Paytm, PhonePe) |
| **Payer PSP** | PSP of the person sending money |
| **Payee PSP** | PSP of the person receiving money |
| **Remitter Bank** | The payer's bank; debits the payer's account |
| **Beneficiary Bank** | The payee's bank; credits the payee's account |
| **ReqPay** | Payment request XML message |
| **RespPay** | Payment response XML message |
| **ReqValAdd** | Value-add / VPA validation request |
| **RespValAdd** | Value-add / VPA validation response |
| **DEBIT** | Transaction type where payer's account is debited |
| **CREDIT** | Transaction type where payee's account is credited |
| **PAY** | Original transaction type from the user's perspective |
| **XSD** | XML Schema Definition -- defines the structure of XML messages |
| **Manifest** | A structured document describing a specification/policy change |
| **A2A** | Agent-to-Agent protocol -- how agents communicate |
| **LLM** | Large Language Model -- AI that interprets change descriptions |
| **Code Updater** | Module that programmatically edits source code files |
| **Orchestrator** | Central hub that tracks and coordinates all change status |
| **Agent** | An AI component that processes manifests and updates code |
| **CBS** | Core Banking System -- the bank's main accounting system |

---

## 18. Important Disclaimers

1. **This is a SIMULATION.** No real money moves. No real bank accounts are debited or credited.
2. **Not production-ready.** PINs stored in plaintext, no TLS/encryption, no authentication/authorization on APIs.
3. **Not certified.** Not endorsed by NPCI; our XSD schemas are inspired by UPI but are not the official NPCI specifications.
4. **Do not use real credentials.** Only use the test VPAs and PINs provided.
5. **AI-generated code should be reviewed.** Changes applied by agents demonstrate capability but should not be deployed to production without human review.
6. **Seed data resets.** Databases may be re-seeded on restart depending on Docker volume configuration.

---

## 19. FAQ

**Q: How do I start the system?**  
A: `docker-compose up -d` from the project root. Then open http://localhost:9992 (Payment UI) and http://localhost:9991 (Orchestrator).

**Q: How do I make a test payment?**  
A: Payment UI -> Select Chandra (Chandra@paytm) -> Select Gaurang as contact -> Enter Rs 500 -> PIN 1234 -> Pay Now.

**Q: Why does my payment fail with "MIN_AMOUNT_VIOLATION"?**  
A: Amount must be >= Rs 65 (configurable). AI agents may have changed this value.

**Q: How do I deploy a spec change via AI?**  
A: Orchestrator UI (http://localhost:9991) -> Enter description -> Deploy. Watch agents progress through RECEIVED -> APPLIED -> TESTED -> READY.

**Q: What if the LLM is not configured?**  
A: Agents fall back to basic/hardcoded change logic. For full LLM features, set `OPENAI_API_KEY` and `LLM_BASE_URL` in `.env`.

**Q: Can I add new test users?**  
A: Edit the `seed_sample_users()` / `seed_sample_accounts()` functions in each service's `db/db.py` and restart.

**Q: Where are logs?**  
A: `docker-compose logs -f <service>`. All services log to stderr with structured format including service name.

**Q: How do I check account balances after a transaction?**  
A: Run `python scripts/check_balances.py` or query the SQLite databases directly.

**Q: What happens if a service is down?**  
A: The calling service gets a connection error and returns HTTP 502 (e.g. "REM_BANK_UNREACHABLE"). The payment fails gracefully.

**Q: Can the AI agents update any file?**  
A: Agents are scoped to their own service files (Rem Bank agent updates `rem_bank/`, Bene Bank agent updates `bene_bank/`). NPCI agent creates manifests but does not modify bank code directly.

**Q: Is there a collect/pull payment flow?**  
A: There is a placeholder XSD for CollectRequest but it is not implemented in the services yet.

---

*This document is the comprehensive knowledge base for UPI-AI. For quick access, use the Table of Contents above. For code-level details, refer to the specific source files mentioned throughout.*
