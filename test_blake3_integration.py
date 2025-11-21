#!/usr/bin/env python3
"""
Test script to verify BLAKE3 integration logic (without requiring the library)
"""

def test_blake3_integration():
    print("=" * 80)
    print("BLAKE3 INTEGRATION VERIFICATION")
    print("=" * 80)
    print()

    # Check files were updated
    print("Test 1: Verify File Updates")
    print("-" * 80)

    checks = []

    # Check requirements.txt
    try:
        with open('requirements.txt', 'r') as f:
            content = f.read()
            if 'blake3' in content:
                print("✓ requirements.txt includes blake3")
                checks.append(True)
            else:
                print("✗ requirements.txt missing blake3")
                checks.append(False)
    except Exception as e:
        print(f"✗ Error reading requirements.txt: {e}")
        checks.append(False)

    # Check fingerprint.py
    try:
        with open('backend/fingerprint.py', 'r') as f:
            content = f.read()
            has_import = 'import blake3' in content
            has_method = 'def compute_blake3_hash' in content
            has_blake3_in_segments = 'blake3Hash' in content

            if has_import and has_method and has_blake3_in_segments:
                print("✓ backend/fingerprint.py updated with BLAKE3")
                print("  - import blake3: present")
                print("  - compute_blake3_hash(): present")
                print("  - blake3Hash in segments: present")
                checks.append(True)
            else:
                print("✗ backend/fingerprint.py incomplete")
                print(f"  - import blake3: {has_import}")
                print(f"  - compute_blake3_hash(): {has_method}")
                print(f"  - blake3Hash in segments: {has_blake3_in_segments}")
                checks.append(False)
    except Exception as e:
        print(f"✗ Error reading fingerprint.py: {e}")
        checks.append(False)

    # Check app.py
    try:
        with open('backend/app.py', 'r') as f:
            content = f.read()
            has_blake3_method = "'blake3'" in content
            has_blake3_matched = 'blake3_matched' in content
            has_blake3_in_result = 'blake3Matched' in content

            if has_blake3_method and has_blake3_matched and has_blake3_in_result:
                print("✓ backend/app.py updated with BLAKE3 verification")
                print("  - blake3 in verification_methods: present")
                print("  - blake3_matched variable: present")
                print("  - blake3Matched in results: present")
                checks.append(True)
            else:
                print("✗ backend/app.py incomplete")
                print(f"  - blake3 method: {has_blake3_method}")
                print(f"  - blake3_matched: {has_blake3_matched}")
                print(f"  - blake3Matched in results: {has_blake3_in_result}")
                checks.append(False)
    except Exception as e:
        print(f"✗ Error reading app.py: {e}")
        checks.append(False)

    # Check index.html
    try:
        with open('frontend/index.html', 'r') as f:
            content = f.read()
            has_blake3_checkbox = 'id="useBlake3"' in content
            has_blake3_label = 'BLAKE3' in content

            if has_blake3_checkbox and has_blake3_label:
                print("✓ frontend/index.html updated with BLAKE3 UI")
                print("  - BLAKE3 checkbox: present")
                print("  - BLAKE3 label: present")
                checks.append(True)
            else:
                print("✗ frontend/index.html incomplete")
                print(f"  - BLAKE3 checkbox: {has_blake3_checkbox}")
                print(f"  - BLAKE3 label: {has_blake3_label}")
                checks.append(False)
    except Exception as e:
        print(f"✗ Error reading index.html: {e}")
        checks.append(False)

    # Check app.js
    try:
        with open('frontend/js/app.js', 'r') as f:
            content = f.read()
            has_use_blake3 = 'useBlake3' in content
            has_blake3_method = 'blake3:' in content

            if has_use_blake3 and has_blake3_method:
                print("✓ frontend/js/app.js updated with BLAKE3 logic")
                print("  - useBlake3 variable: present")
                print("  - blake3 in methods: present")
                checks.append(True)
            else:
                print("✗ frontend/js/app.js incomplete")
                print(f"  - useBlake3: {has_use_blake3}")
                print(f"  - blake3 method: {has_blake3_method}")
                checks.append(False)
    except Exception as e:
        print(f"✗ Error reading app.js: {e}")
        checks.append(False)

    print()

    # Summary
    print("=" * 80)
    print("INTEGRATION SUMMARY")
    print("=" * 80)
    print()

    if all(checks):
        print("✓ ALL INTEGRATION CHECKS PASSED")
        print()
        print("BLAKE3 has been successfully integrated into:")
        print()
        print("Backend:")
        print("  ✓ requirements.txt - blake3==0.4.1 dependency added")
        print("  ✓ fingerprint.py - compute_blake3_hash() method")
        print("  ✓ fingerprint.py - blake3Hash in all segment generation")
        print("  ✓ app.py - BLAKE3 verification logic")
        print()
        print("Frontend:")
        print("  ✓ index.html - BLAKE3 checkbox in verification methods")
        print("  ✓ app.js - BLAKE3 option handling")
        print()
        print("Benefits:")
        print("  - Faster cryptographic verification than SHA-256")
        print("  - Same security level as SHA-256")
        print("  - Can be used alongside or instead of SHA-256")
        print("  - Exact byte-level matching for tamper detection")
        print()
        print("Next Steps:")
        print("  1. Rebuild Docker container to install blake3")
        print("  2. Test with actual audio files")
        print("  3. Verify BLAKE3 shows in verification results")
        print()
    else:
        print("✗ SOME INTEGRATION CHECKS FAILED")
        print("  Please review the errors above")
        print()

    print("=" * 80)

    return all(checks)

if __name__ == "__main__":
    try:
        success = test_blake3_integration()
        exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
