# Phase 2 - AI Agents for Spec Change → Code Update → Deployment

This implementation provides AI agents that automate change management in the UPI payment ecosystem.

## Overview

Phase 2 extends Phase 1 by creating intelligent AI agents for:
- **NPCI Switch** - Creates change manifests and dispatches them
- **Remitter Bank** - Updates debit/CBS integration logic per change
- **Beneficiary Bank** - Updates credit/CBS integration logic per change
- **Orchestrator** - Tracks change status across all parties

## Architecture

### Components

1. **Manifest System** (`manifest.py`)
   - `ChangeManifest` class for describing specification changes
   - Supports various change types (XSD updates, API changes, validation rules, etc.)

2. **Agent-to-Agent Protocol** (`a2a_protocol.py`)
   - `A2AMessage` for inter-agent communication
   - `A2AClient` for sending messages between agents

3. **Code Updater** (`code_updater.py`)
   - Automated code modification based on change manifests
   - Supports function additions, modifications, validation additions, etc.

4. **Agents** (`agents/`)
   - `BaseAgent` - Base class for all agents
   - `NPCIAgent` - Creates and dispatches manifests
   - `RemitterBankAgent` - Processes manifests for debit logic
   - `BeneficiaryBankAgent` - Processes manifests for credit logic

5. **Orchestrator** (`orchestrator.py`)
   - Tracks change status across all agents
   - Provides status board/log
   - REST API for status queries

6. **Agent API** (`agent_api.py`)
   - Flask endpoints for agent integration
   - Can be integrated into existing Flask services

## Status Flow

Changes progress through these statuses:
- **RECEIVED** - Agent received the manifest
- **APPLIED** - Code changes have been applied
- **TESTED** - Tests have been run and passed
- **READY** - Ready for deployment/approval
- **ERROR** - Error occurred during processing

## Usage

### Running the Demo

```bash
# Set up environment variables (optional)
export OPENAI_API_KEY="your-api-key"
export LLM_MODEL="gpt-3.5-turbo"
export LLM_BASE_URL="http://localhost:1234/v1"  # For local models

# Run the demo
python demo.py
```

### Running Individual Components

#### Orchestrator
```bash
python orchestrator.py
# Runs on http://localhost:9991
```

#### Agent API
```bash
export AGENT_TYPE="REMITTER_BANK_AGENT"  # or BENEFICIARY_BANK_AGENT
python agent_api.py
# Runs on http://localhost:7000
```

### Creating a Manifest (Programmatically)

```python
from agents import NPCIAgent
from manifest import ChangeType
from llm import LLM

llm = LLM()
npci_agent = NPCIAgent(llm_instance=llm)

manifest = npci_agent.create_manifest(
    description="Add minimum transaction amount validation",
    change_type=ChangeType.VALIDATION_RULE,
    affected_components=["rem_bank", "bene_bank"],
    code_changes={"type": "add_validation", "rule": "min_amount_1"},
)

# Dispatch to receivers
results = npci_agent.dispatch_manifest(manifest)
```

### API Endpoints

#### Orchestrator
- `GET /health` - Health check
- `POST /api/orchestrator/status` - Update agent status
- `GET /api/orchestrator/change/<change_id>` - Get change status
- `GET /api/orchestrator/changes` - Get all changes
- `GET /api/orchestrator/summary` - Get summary
- `POST /api/orchestrator/register` - Register new change

#### Agent API
- `GET /health` - Health check
- `POST /api/agent/manifest` - Receive manifest (A2A protocol)
- `GET /api/agent/status/<change_id>` - Get agent status
- `POST /api/agent/create-manifest` - Create new manifest (NPCI only)

## Integration with Existing Services

To integrate agents into existing Flask services (e.g., `npci/app.py`, `rem_bank/app.py`):

1. Import the agent API endpoints:
```python
from agent_api import app as agent_app
# Or mount specific routes
```

2. Set environment variable to identify agent type:
```bash
export AGENT_TYPE="REMITTER_BANK_AGENT"
```

3. Agents will automatically process manifests received via A2A protocol.

## Example Change Propagation Flow

1. **NPCI Agent** creates a manifest describing a specification change
2. **NPCI Agent** dispatches manifest to all receiver agents (banks, PSPs)
3. **Receiver Agents** receive manifest → Status: RECEIVED
4. **Receiver Agents** interpret manifest using LLM → Status: APPLIED
5. **Receiver Agents** apply code changes → Status: TESTED
6. **Receiver Agents** signal readiness → Status: READY
7. **Orchestrator** tracks all statuses and provides final report

## Code Changes

The code updater supports:
- Adding new functions
- Modifying existing functions
- Adding imports
- Adding validation logic
- Modifying fields
- Generic text replacements

All changes are logged with diffs for review.

## Requirements

Install required packages:
```bash
pip install langchain langchain-openai langchain-core langgraph flask requests lxml
```

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key (or use `LLM_API_KEY`)
- `LLM_MODEL` - Model to use (default: "gpt-3.5-turbo")
- `LLM_BASE_URL` - Base URL for LLM API (for local models)
- `AGENT_TYPE` - Agent type identifier
- `ORCHESTRATOR_PORT` - Orchestrator port (default: 9991)
- `AGENT_API_PORT` - Agent API port (default: 7000)

## Future Enhancements

- Human-in-the-loop approvals
- RAG over specifications/XSDs for exact rule citations
- Automated business logic identification
- Signed manifests for security
- Integration with CI/CD pipelines
- Real-time status dashboard

## Notes

- Agents use LangChain/LangGraph for LLM integration
- Code changes create backups (.backup files)
- Status tracking is in-memory (can be extended to database)
- A2A protocol uses HTTP/REST (can be extended to message queues)
