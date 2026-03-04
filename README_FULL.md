# 🏦 UPI-AI: Complete Ecosystem

> A comprehensive UPI payment simulation system with AI-powered change management and modern payment UI

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey)](https://flask.palletsprojects.com/)

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Components](#components)
- [Use Cases](#use-cases)
- [Documentation](#documentation)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

UPI-AI is a full-featured UPI payment ecosystem simulator with two main capabilities:

### 1. 💳 Transaction Simulation (Payment UI)
Beautiful, GPay-inspired interface for testing real UPI payment flows through the complete ecosystem.

**Access**: http://localhost:9992

### 2. 🤖 AI-Powered Change Management (Orchestrator)
Intelligent agents that automatically interpret specification changes and update code across all services.

**Access**: http://localhost:9991

## 🚀 Quick Start

### One-Command Setup

```bash
# Start everything with Docker
docker-compose up -d

# Access the UIs
# Payment UI: http://localhost:9992
# Orchestrator: http://localhost:9991
```

### Or Use Quick Start Script

```bash
# Start Payment UI with helper script
./start_payment_ui.sh
```

### Test a Payment

1. Open http://localhost:9992
2. Select user: **Chandra** (Chandra@paytm)
3. Choose contact: **Gaurang**
4. Enter amount: **₹500**
5. Enter PIN: **1234**
6. Click **Pay Now** 🎉

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      UPI AI ECOSYSTEM                        │
│                                                              │
│  ┌──────────────┐                    ┌──────────────┐      │
│  │  Payment UI  │                    │ Orchestrator │      │
│  │  Port 9992   │                    │  Port 9991   │      │
│  │   (GPay UI)  │                    │ (AI Monitor) │      │
│  └──────┬───────┘                    └──────────────┘      │
│         │                                                    │
│         ↓ ReqPay XML                                        │
│  ┌──────────────┐                                          │
│  │  Payer PSP   │                                          │
│  │  Port 5060   │                                          │
│  └──────┬───────┘                                          │
│         │                                                    │
│         ↓                                                    │
│  ┌──────────────┐        AI Agents                         │
│  │     NPCI     │◄────────────────────────────┐           │
│  │  Port 5050   │                              │           │
│  │   (Switch)   │                              │           │
│  └──────┬───────┘                              │           │
│         │                                       │           │
│    ┌────┴─────┬──────────────┐                │           │
│    ↓          ↓              ↓                 │           │
│ ┌─────┐  ┌─────┐        ┌─────┐               │           │
│ │ Rem │  │Bene │        │Payee│               │           │
│ │Bank │  │Bank │        │ PSP │               │           │
│ │5080 │  │5090 │        │5070 │               │           │
│ └─────┘  └─────┘        └─────┘               │           │
│    ▲         ▲                                 │           │
│    └─────────┴─────────────────────────────────┘           │
│           AI Code Updates                                   │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Components

### 💳 Payment UI (Port 9992)

**Purpose**: Simulate UPI transactions with beautiful UI

**Features**:
- ✅ GPay-inspired modern design
- ✅ Multiple user accounts
- ✅ Contact management
- ✅ Real-time transactions
- ✅ PIN validation
- ✅ Transaction history
- ✅ Success animations
- ✅ Mobile responsive

**Tech Stack**: Flask, HTML/CSS/JS, Vanilla JavaScript

**Documentation**: [`payment_ui/README.md`](payment_ui/README.md)

### 🤖 Orchestrator (Port 9991)

**Purpose**: Monitor and coordinate AI agents

**Features**:
- ✅ AI agent status tracking
- ✅ Change manifest management
- ✅ Real-time logs
- ✅ Code update monitoring
- ✅ Multi-agent coordination

**Tech Stack**: Flask, JavaScript, LangChain (AI agents)

**Documentation**: [`PHASE2_README.md`](PHASE2_README.md)

### 🔄 UPI Services

| Service | Port | Purpose |
|---------|------|---------|
| **NPCI** | 5050 | Central switch/router |
| **Payer PSP** | 5060 | Payer payment service provider |
| **Payee PSP** | 5070 | Payee payment service provider |
| **Remitter Bank** | 5080 | Debit/CBS integration |
| **Beneficiary Bank** | 5090 | Credit/CBS integration |

## 📖 Use Cases

### Use Case 1: Test Payment Flow

```bash
# 1. Start services
docker-compose up -d

# 2. Open Payment UI
open http://localhost:9992

# 3. Make a payment
# - Select: Chandra (Chandra@paytm)
# - Pay to: Gaurang (Gaurang@phonepe)
# - Amount: ₹500
# - PIN: 1234
# - Submit!

# 4. See the transaction flow through:
# Payer PSP → NPCI → Rem Bank (debit) → Bene Bank (credit) → Success!
```

**Transaction Flow**:
```
Payment UI
    ↓ (POST /api/transaction)
Payer PSP [PIN validation]
    ↓ (ReqPay XML)
NPCI [Route transaction]
    ↓ (Parallel)
    ├→ Remitter Bank [Debit ₹500]
    └→ Beneficiary Bank [Credit ₹500]
    ↓
RespPay (Success)
    ↓
Payment UI (Show success ✓)
```

### Use Case 2: Test AI Agents

```bash
# 1. Open Orchestrator UI
open http://localhost:9991

# 2. Deploy a change
# Enter: "Add validation for maximum transaction amount of ₹50,000"
# Click: "Initialize Agents"

# 3. Watch AI agents:
# - NPCI Agent: Create manifest
# - Remitter Bank Agent: Apply code changes
# - Beneficiary Bank Agent: Apply code changes
# - All agents: Test and mark READY

# 4. View detailed logs and status
```

**AI Agent Flow**:
```
Orchestrator (Change prompt)
    ↓
NPCI Agent [LLM interprets, creates manifest]
    ↓ (Dispatch manifest)
    ├→ Remitter Bank Agent
    │   ↓ [RECEIVED → APPLIED → TESTED → READY]
    │
    └→ Beneficiary Bank Agent
        ↓ [RECEIVED → APPLIED → TESTED → READY]
    ↓
All READY (Deploy!)
```

## 📚 Documentation

### Quick Guides
- **Payment UI Quick Start**: [`PAYMENT_UI_README.md`](PAYMENT_UI_README.md)
- **Project Overview**: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)

### Detailed Docs
- **Payment UI Features**: [`payment_ui/FEATURES.md`](payment_ui/FEATURES.md)
- **Payment UI API**: [`payment_ui/README.md`](payment_ui/README.md)
- **AI Agents**: [`PHASE2_README.md`](PHASE2_README.md)
- **UPI Schemas**: [`common/schemas/`](common/schemas/)

### Scripts
- **Interactive Testing**: [`scripts/interactive_test.py`](scripts/interactive_test.py)
- **Quick Start**: [`start_payment_ui.sh`](start_payment_ui.sh)

## 👥 Test Users

### Payer Users (for Payment UI)

| Name | VPA | PIN | Balance |
|------|-----|-----|---------|
| Chandra | Chandra@paytm | 1234 | ₹10,000 |
| Gaurang | Gaurang@paytm | 1111 | ₹15,000 |
| Hrithik | Hrithik@paytm | 1234 | ₹20,000 |

### Payee Users (Contacts)

| Name | VPA |
|------|-----|
| Chandra | Chandra@phonepe |
| Gaurang | Gaurang@phonepe |
| Hrithik | Hrithik@phonepe |

## 🔧 Development

### Prerequisites
- Docker & Docker Compose (recommended)
- Python 3.11+
- Git

### Local Development Setup

```bash
# Clone repository
git clone <repo-url>
cd upi-ai-main

# Copy environment template
cp .env.example .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Running Individual Services

**Payment UI Only**:
```bash
cd payment_ui
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

**Orchestrator Only**:
```bash
python orchestrator.py
```

### Project Structure

```
upi-ai-main/
├── payment_ui/              # GPay-like transaction UI
│   ├── app.py              # Flask backend
│   ├── static/             # HTML, CSS, JS
│   │   ├── index.html
│   │   ├── style.css
│   │   └── app.js
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── README.md
│   └── FEATURES.md
├── orchestrator/           # AI agent dashboard
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── agents/                 # AI agent implementations
│   ├── base_agent.py
│   ├── npci_agent.py
│   ├── remitter_bank_agent.py
│   └── beneficiary_bank_agent.py
├── npci/                   # NPCI switch service
│   ├── app.py
│   └── Dockerfile
├── payer_psp/             # Payer PSP service
│   ├── app.py
│   ├── db/
│   └── Dockerfile
├── payee_psp/             # Payee PSP service
├── rem_bank/              # Remitter bank
├── bene_bank/             # Beneficiary bank
├── common/                # Shared code
│   ├── schemas/           # UPI XSD schemas
│   └── db/                # Shared database code
├── scripts/               # Helper scripts
├── docker-compose.yml     # Docker orchestration
├── orchestrator.py        # Orchestrator backend
├── manifest.py            # Change manifest definitions
├── llm.py                 # LLM integration
├── a2a_protocol.py        # Agent-to-agent protocol
└── code_updater.py        # Automated code updates
```

## 🧪 Testing

### Automated Testing

```bash
# Run demo script
python demo.py

# Run interactive test
python scripts/interactive_test.py
```

### Manual Testing via UIs

**Payment Flow**:
1. Open http://localhost:9992
2. Follow the guided UI
3. Check transaction success

**AI Agents**:
1. Open http://localhost:9991
2. Submit a change prompt
3. Monitor agent progress

### API Testing

```bash
# Test Payer PSP health
curl http://localhost:5060/health

# Test Payment UI API
curl http://localhost:9992/api/users

# Test transaction (requires XML)
# See scripts/interactive_test.py for examples
```

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check Docker status
docker ps

# View logs for errors
docker-compose logs

# Restart all services
docker-compose down
docker-compose up -d
```

### Payment Fails

**Issue**: Transaction returns error

**Solutions**:
- ✅ Verify services are running: `docker-compose ps`
- ✅ Check correct PIN (see Test Users table)
- ✅ Ensure amount ≥ ₹150 (system minimum)
- ✅ Check logs: `docker-compose logs payer_psp`

### Port Already in Use

**Issue**: Port 9992 or other ports conflict

**Solution**:
```bash
# Edit .env file
echo "PAYMENT_UI_PORT=8001" >> .env
echo "ORCHESTRATOR_PORT=9993" >> .env

# Restart
docker-compose down
docker-compose up -d
```

### Connection Refused

**Issue**: UI shows "Connection failed"

**Solution**:
```bash
# Check if services are up
docker-compose ps

# Wait for services to initialize
sleep 5

# Try again
```

### AI Agents Not Working

**Issue**: Orchestrator shows errors

**Solution**:
```bash
# Check if LLM API key is set (if using OpenAI)
echo "OPENAI_API_KEY=your-key" >> .env

# Or use local mode (basic functionality)
export A2A_LOCAL_MODE=true

# Restart orchestrator
docker-compose restart orchestrator
```

## 🔐 Security Notes

⚠️ **Important**: This is a **simulation environment**

- ❌ Do NOT use real payment credentials
- ❌ PINs are stored in plaintext (demo only)
- ❌ No encryption (demo only)
- ❌ Not production-ready
- ❌ No authentication/authorization

✅ **For Testing/Learning Purposes Only**

## 🚀 Performance

- **Transaction Processing**: <1s end-to-end
- **UI Responsiveness**: <100ms interactions
- **AI Agent Updates**: 10-30s (depends on LLM)
- **Concurrent Users**: Supports multiple simultaneous

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f payment_ui
docker-compose logs -f payer_psp
docker-compose logs -f npci

# Last 100 lines
docker-compose logs --tail=100 payment_ui
```

### Check Status

```bash
# Service health
docker-compose ps

# API health checks
curl http://localhost:9992/health  # Payment UI
curl http://localhost:9991/health  # Orchestrator
curl http://localhost:5060/health  # Payer PSP
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 Environment Variables

See [`.env.example`](.env.example) for all available configuration options.

Key variables:
```bash
# Service Ports
PAYMENT_UI_PORT=9992
ORCHESTRATOR_PORT=9991
PAYER_PSP_PORT=5060

# LLM Configuration (optional)
OPENAI_API_KEY=your-key
LLM_MODEL=gpt-3.5-turbo
```

## 📄 License

[Add license information]

## 🙏 Acknowledgments

- UPI protocol specifications (NPCI)
- Google Pay UI inspiration
- Flask, Docker communities
- LangChain for AI agent framework

---

## 🎉 Ready to Start?

```bash
# Quick start - Payment UI
./start_payment_ui.sh

# Or start everything
docker-compose up -d

# Open in browser
# Payment UI:      http://localhost:9992
# Orchestrator UI: http://localhost:9991
```

**Have fun testing the UPI ecosystem! 🚀**

---

Made with ❤️ for UPI simulation and AI-powered change management

