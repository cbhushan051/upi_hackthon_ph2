#!/usr/bin/env python3
"""
Docker-compatible demo script for Phase 2 AI agents.
Demonstrates end-to-end flow via HTTP APIs.
"""

import json
import logging
import time
import requests
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Service URLs (Docker networking - using host port mappings from .env)
NPCI_URL = "http://localhost:5050"
REM_BANK_URL = "http://localhost:5080"
BENE_BANK_URL = "http://localhost:5090"
ORCHESTRATOR_URL = "http://localhost:5040"


def check_services():
    """Check if all services are running."""
    services = {
        "NPCI": f"{NPCI_URL}/health",
        "Remitter Bank": f"{REM_BANK_URL}/health",
        "Beneficiary Bank": f"{BENE_BANK_URL}/health",
        "Orchestrator": f"{ORCHESTRATOR_URL}/health",
    }
    
    logger.info("=" * 80)
    logger.info("Checking service health...")
    logger.info("=" * 80)
    
    all_healthy = True
    for name, url in services.items():
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                logger.info(f"✓ {name}: OK")
            else:
                logger.error(f"✗ {name}: HTTP {r.status_code}")
                all_healthy = False
        except requests.RequestException as e:
            logger.error(f"✗ {name}: {e}")
            all_healthy = False
    
    logger.info("")
    return all_healthy


def create_and_dispatch_manifest():
    """Create a manifest via NPCI API and dispatch to banks."""
    logger.info("=" * 80)
    logger.info("Step 1: Creating and dispatching manifest via NPCI...")
    logger.info("=" * 80)
    
    manifest_data = {
        "description": "Add minimum transaction amount validation (INR 1)",
        "change_type": "validation_rule",
        "affected_components": ["rem_bank", "bene_bank"],
        "code_changes": {
            "type": "add_validation",
            "rule": "min_amount_1",
        },
        "test_requirements": [
            "Test transaction with amount < INR 1 should fail",
            "Test transaction with amount >= INR 1 should succeed",
        ],
        "receivers": ["REMITTER_BANK_AGENT", "BENEFICIARY_BANK_AGENT"],
    }
    
    try:
        r = requests.post(
            f"{NPCI_URL}/api/agent/create-manifest",
            json=manifest_data,
            timeout=30,
        )
        r.raise_for_status()
        result = r.json()
        
        logger.info(f"✓ Manifest created: {result['change_id']}")
        logger.info(f"  Status: {result['status']}")
        
        if "dispatch_results" in result:
            logger.info("  Dispatch results:")
            for receiver, success in result["dispatch_results"].items():
                status = "✓" if success else "✗"
                logger.info(f"    {status} {receiver}")
        
        logger.info("")
        return result
    except requests.RequestException as e:
        logger.error(f"✗ Failed to create manifest: {e}")
        return None


def poll_orchestrator(change_id, max_attempts=10, delay=2):
    """Poll orchestrator for status updates."""
    logger.info("=" * 80)
    logger.info("Step 2: Polling orchestrator for status updates...")
    logger.info("=" * 80)
    
    for attempt in range(max_attempts):
        try:
            r = requests.get(f"{ORCHESTRATOR_URL}/api/orchestrator/change/{change_id}", timeout=5)
            if r.status_code == 200:
                status_data = r.json()
                logger.info(f"\nAttempt {attempt + 1}/{max_attempts}:")
                logger.info(f"  Change ID: {change_id}")
                logger.info(f"  Agent statuses:")
                
                for agent_id, status in status_data.get("statuses", {}).items():
                    logger.info(f"    {agent_id}: {status}")
                
                # Check if all agents are READY
                statuses = status_data.get("statuses", {})
                if all(s == "READY" for s in statuses.values()):
                    logger.info("\n✓ All agents are READY!")
                    logger.info("")
                    return status_data
                
                time.sleep(delay)
            elif r.status_code == 404:
                logger.warning(f"  Change {change_id} not found in orchestrator yet...")
                time.sleep(delay)
            else:
                logger.error(f"  HTTP {r.status_code}")
                time.sleep(delay)
        except requests.RequestException as e:
            logger.warning(f"  Orchestrator unreachable: {e}")
            time.sleep(delay)
    
    logger.warning("\n⚠ Timeout waiting for all agents to be READY")
    logger.info("")
    return None


def get_summary():
    """Get orchestrator summary."""
    logger.info("=" * 80)
    logger.info("Step 3: Getting orchestrator summary...")
    logger.info("=" * 80)
    
    try:
        r = requests.get(f"{ORCHESTRATOR_URL}/api/orchestrator/summary", timeout=5)
        r.raise_for_status()
        summary = r.json()
        
        logger.info(f"Total changes: {summary.get('total_changes', 0)}")
        logger.info(f"All ready: {summary.get('all_ready', 0)}")
        logger.info(f"In progress: {summary.get('in_progress', 0)}")
        logger.info("")
        return summary
    except requests.RequestException as e:
        logger.error(f"✗ Failed to get summary: {e}")
        logger.info("")
        return None


def main():
    """Run the demo."""
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("Phase 2 Docker Demo: AI Agents for Automated Change Management")
    logger.info("=" * 80)
    logger.info("")
    
    # Step 0: Check services
    if not check_services():
        logger.error("✗ Not all services are healthy. Please ensure all Docker containers are running.")
        logger.error("  Run: docker-compose up --build")
        sys.exit(1)
    
    # Step 1: Create and dispatch manifest
    result = create_and_dispatch_manifest()
    if not result:
        logger.error("✗ Failed to create manifest. Exiting.")
        sys.exit(1)
    
    change_id = result.get("change_id")
    if not change_id:
        logger.error("✗ No change_id in result. Exiting.")
        sys.exit(1)
    
    # Step 2: Poll orchestrator
    final_status = poll_orchestrator(change_id)
    
    # Step 3: Get summary
    get_summary()
    
    # Final result
    logger.info("=" * 80)
    logger.info("Demo completed!")
    logger.info("=" * 80)
    logger.info("")
    
    if final_status:
        logger.info("✓ SUCCESS: All agents processed the manifest.")
    else:
        logger.info("⚠ PARTIAL: Some agents may still be processing.")
    
    logger.info("\nNext steps:")
    logger.info("  - Check logs: docker-compose logs")
    logger.info("  - View orchestrator: curl http://localhost:8881/api/orchestrator/changes")
    logger.info("  - Test agent status: curl http://localhost:6005/api/agent/status/<change_id>")
    logger.info("")


if __name__ == "__main__":
    main()
