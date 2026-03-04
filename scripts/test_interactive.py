#!/usr/bin/env python3
"""
Automated test for interactive_test.py
Tests the transaction flow with different amounts
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.interactive_test import send_transaction, check_services, DEFAULT_PAYER_VPA, DEFAULT_PAYEE_VPA

def test_transaction(amount, expected_success=True):
    """Test a single transaction."""
    print(f"\nTesting transaction: ₹{amount:.2f}")
    print("-" * 50)
    
    result = send_transaction(DEFAULT_PAYER_VPA, DEFAULT_PAYEE_VPA, amount, "1234")
    
    if result["success"] == expected_success:
        print(f"✓ PASS: Transaction {'succeeded' if expected_success else 'failed'} as expected")
        print(f"  Status: {result['message']}")
        return True
    else:
        print(f"✗ FAIL: Expected {'success' if expected_success else 'failure'}, got {'success' if result['success'] else 'failure'}")
        print(f"  Status: {result['message']}")
        print(f"  Details: {result['details']}")
        return False

def main():
    print("=" * 70)
    print("  Automated Test for UPI Transaction Script")
    print("=" * 70)
    
    # Check services
    print("\nStep 1: Checking services...")
    if not check_services():
        print("\n✗ Services not available. Exiting.")
        sys.exit(1)
    
    print("\n✓ Services are running")
    
    # Run tests
    print("\nStep 2: Running transaction tests...")
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Amount below minimum (should fail if validation is active)
    # Note: This might succeed if the minimum validation hasn't been deployed yet
    tests_total += 1
    if test_transaction(0.50, expected_success=False):
        tests_passed += 1
    
    # Test 2: Amount at minimum (should succeed)
    tests_total += 1
    if test_transaction(1.00, expected_success=True):
        tests_passed += 1
    
    # Test 3: Amount above minimum (should succeed)
    tests_total += 1
    if test_transaction(10.00, expected_success=True):
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 70)
    print(f"  Test Results: {tests_passed}/{tests_total} passed")
    print("=" * 70)
    
    if tests_passed == tests_total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {tests_total - tests_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(1)
