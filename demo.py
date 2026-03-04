"""
Demo script for Phase 2 - End-to-end demonstration of AI agents processing change manifests.
"""

import json
import logging
import os
import time
from manifest import ChangeManifest, ChangeType
from agents import NPCIAgent, RemitterBankAgent, BeneficiaryBankAgent
from agents.base_agent import AgentStatus
from orchestrator import Orchestrator
from llm import LLM

# Enable local mode for A2A protocol (skip HTTP calls when services aren't running)
os.environ["A2A_LOCAL_MODE"] = "true"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    """Run end-to-end demo."""
    print("=" * 80)
    print("Phase 2 Demo: AI Agents for Spec Change -> Code Update -> Deployment")
    print("=" * 80)
    print()
    
    # Initialize LLM (use environment variables or defaults)
    try:
        llm = LLM(
            model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("LLM_BASE_URL"),
        )
        print("[OK] LLM initialized")
    except Exception as e:
        print(f"[WARNING] LLM initialization failed: {e}")
        print("  Continuing in fallback mode (basic manifest processing without LLM)...")
        llm = LLM(api_key="")  # Force fallback mode
    
    # Initialize agents
    print("Initializing agents...")
    npci_agent = NPCIAgent(llm_instance=llm)
    remitter_agent = RemitterBankAgent(llm_instance=llm)
    beneficiary_agent = BeneficiaryBankAgent(llm_instance=llm)
    
    # Initialize orchestrator
    orchestrator = Orchestrator()
    
    print("[OK] Agents initialized\n")
    
    # Step 1: NPCI Agent creates a manifest
    print("Step 1: NPCI Agent creating change manifest...")
    manifest = npci_agent.create_manifest(
        description="Add new validation rule for minimum transaction amount of INR 1",
        change_type=ChangeType.VALIDATION_RULE,
        affected_components=["rem_bank", "bene_bank"],
        code_changes={
            "type": "add_validation",
            "rule": "minimum_amount_1",
        },
        test_requirements=[
            "Test transaction with amount < INR 1 should fail",
            "Test transaction with amount >= INR 1 should succeed",
        ],
    )
    
    print(f"[OK] Created manifest: {manifest.change_id}")
    print(f"  Description: {manifest.description}")
    print(f"  Type: {manifest.change_type.value}")
    print()
    
    # Register with orchestrator
    receivers = ["REMITTER_BANK_AGENT", "BENEFICIARY_BANK_AGENT"]
    orchestrator.register_change(manifest, receivers)
    
    # Step 2: Dispatch manifest to receiver agents
    print("Step 2: Dispatching manifest to receiver agents...")
    dispatch_results = npci_agent.dispatch_manifest(manifest, receivers)
    
    for receiver, success in dispatch_results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {receiver}: {'Success' if success else 'Failed'}")
    print()
    
    # Step 3: Simulate agents receiving and processing manifests
    print("Step 3: Agents processing manifests...")
    print()
    
    # Remitter Bank Agent
    print(f"[{remitter_agent.agent_name}] Processing manifest {manifest.change_id}...")
    remitter_result = remitter_agent.receive_manifest(manifest)
    print(f"  Status: {remitter_result['status']}")
    
    remitter_result = remitter_agent.process_manifest(manifest)
    print(f"  Final Status: {remitter_result['status']}")
    if "applied_changes" in remitter_result:
        print(f"  Applied Changes: {len(remitter_result['applied_changes'])} files")
    print()
    
    # Update orchestrator
    orchestrator.update_agent_status(
        manifest.change_id,
        remitter_agent.agent_id,
        AgentStatus(remitter_result['status']),
        remitter_result,
    )
    
    # Beneficiary Bank Agent
    print(f"[{beneficiary_agent.agent_name}] Processing manifest {manifest.change_id}...")
    beneficiary_result = beneficiary_agent.receive_manifest(manifest)
    print(f"  Status: {beneficiary_result['status']}")
    
    beneficiary_result = beneficiary_agent.process_manifest(manifest)
    print(f"  Final Status: {beneficiary_result['status']}")
    if "applied_changes" in beneficiary_result:
        print(f"  Applied Changes: {len(beneficiary_result['applied_changes'])} files")
    print()
    
    # Update orchestrator
    orchestrator.update_agent_status(
        manifest.change_id,
        beneficiary_agent.agent_id,
        AgentStatus(beneficiary_result['status']),
        beneficiary_result,
    )
    
    # Step 4: Show orchestrator status board
    print("Step 4: Orchestrator Status Board")
    print("-" * 80)
    
    change_status = orchestrator.get_change_status(manifest.change_id)
    if change_status:
        print(f"Change ID: {manifest.change_id}")
        print(f"Description: {manifest.description}")
        print(f"\nAgent Statuses:")
        for agent_id, status in change_status["statuses"].items():
            print(f"  {agent_id}: {status}")
        
        # Check if all ready
        all_ready = all(
            status == AgentStatus.READY.value
            for status in change_status["statuses"].values()
        )
        
        if all_ready:
            print("\n[OK] All agents are READY for deployment!")
        else:
            print("\n[WAIT] Some agents are still processing...")
    
    print()
    
    # Step 5: Summary
    print("Step 5: Summary")
    print("-" * 80)
    summary = orchestrator.get_summary()
    print(f"Total Changes: {summary['total_changes']}")
    print(f"All Ready: {summary['all_ready']}")
    print(f"In Progress: {summary['in_progress']}")
    print()
    
    # Show code changes log
    print("Code Changes Applied:")
    print("-" * 80)
    remitter_changes = remitter_agent.code_updater.get_changes_log()
    beneficiary_changes = beneficiary_agent.code_updater.get_changes_log()
    
    all_changes = remitter_changes + beneficiary_changes
    if all_changes:
        for change in all_changes:
            print(f"  [{change['status']}] {change['file']} - {change['change_type']}")
    else:
        print("  No code changes applied (using basic manifest processing)")
    
    print()
    print("=" * 80)
    print("Demo completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
