#!/usr/bin/env python3
"""
Test script to verify no-segmentation option for fingerprinting
Tests: Full-file-only fingerprinting without segmentation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fingerprint import AudioFingerprinter
import json
import numpy as np
import librosa

def test_no_segmentation():
    print("=" * 80)
    print("NO-SEGMENTATION FINGERPRINTING TEST")
    print("=" * 80)
    print()

    # Initialize fingerprinter
    fp = AudioFingerprinter()

    # File paths (using the same test files)
    reference_file = "backend/10minana.mp3"
    part1_file = "backend/5minpart1.mp3"

    print(f"Reference File: {reference_file}")
    print(f"Test File: {part1_file}")
    print()

    # Test 1: Full file fingerprint with no segmentation
    print("Test 1: Full File Fingerprint (No Segmentation)")
    print("-" * 80)

    audio_data, sr = librosa.load(reference_file, sr=fp.sample_rate, mono=True)
    duration = len(audio_data) / sr

    full_file_result = fp.generate_full_file_fingerprint(audio_data, include_chromaprint=False)

    if full_file_result:
        print(f"✓ Full file fingerprint generated successfully")
        print(f"  Duration: {full_file_result['duration']:.2f}s")
        print(f"  Start Time: {full_file_result['startTime']:.2f}s")
        print(f"  End Time: {full_file_result['endTime']:.2f}s")
        print(f"  Fingerprint Features: {len(full_file_result['fingerprint'])}")
        print(f"  Crypto Hash: {full_file_result['cryptoHash'][:16]}...")
    else:
        print("✗ Failed to generate full file fingerprint")
        return

    print()

    # Test 2: Compare with segmented approach
    print("Test 2: Compare No-Segmentation vs Segmented")
    print("-" * 80)

    segments = fp.generate_segments(audio_data, segment_duration=5.0, include_chromaprint=False)

    print(f"Segmented approach: {len(segments)} segments")
    print(f"No-segmentation approach: 1 full-file fingerprint")
    print()

    # Test 3: Verify the fingerprint structure
    print("Test 3: Verify Fingerprint Structure")
    print("-" * 80)

    required_fields = ['startTime', 'endTime', 'fingerprint', 'cryptoHash', 'duration']
    all_fields_present = all(field in full_file_result for field in required_fields)

    if all_fields_present:
        print("✓ All required fields present in fingerprint")
        for field in required_fields:
            print(f"  - {field}: present")
    else:
        print("✗ Missing required fields")
        return

    print()

    # Test 4: Verify fingerprint is not empty or invalid
    print("Test 4: Verify Fingerprint Quality")
    print("-" * 80)

    fingerprint_array = np.array(full_file_result['fingerprint'])

    checks = {
        'Non-empty fingerprint': len(fingerprint_array) > 0,
        'Correct fingerprint size (86 features)': len(fingerprint_array) == 86,
        'No NaN values': not np.any(np.isnan(fingerprint_array)),
        'No Inf values': not np.any(np.isinf(fingerprint_array)),
        'Normalized values [-1, 1]': np.all(np.abs(fingerprint_array) <= 1.0)
    }

    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")

    all_passed = all(checks.values())
    print()

    # Test 5: Load and fingerprint a partial file with no segmentation
    print("Test 5: Partial File (No Segmentation)")
    print("-" * 80)

    audio_data_part1, sr = librosa.load(part1_file, sr=fp.sample_rate, mono=True)
    part1_full_file = fp.generate_full_file_fingerprint(audio_data_part1, include_chromaprint=False)

    if part1_full_file:
        print(f"✓ Partial file fingerprint generated successfully")
        print(f"  Duration: {part1_full_file['duration']:.2f}s")
        print(f"  Fingerprint Features: {len(part1_full_file['fingerprint'])}")
    else:
        print("✗ Failed to generate partial file fingerprint")
        return

    print()

    # Test 6: Compare fingerprints
    print("Test 6: Compare Full File vs Partial File Fingerprints")
    print("-" * 80)

    # Simple cosine similarity
    fp1 = np.array(full_file_result['fingerprint'])
    fp2 = np.array(part1_full_file['fingerprint'])

    dot_product = np.dot(fp1, fp2)
    magnitude1 = np.linalg.norm(fp1)
    magnitude2 = np.linalg.norm(fp2)
    cosine_similarity = dot_product / (magnitude1 * magnitude2 + 1e-10)
    cosine_similarity = (cosine_similarity + 1) / 2  # Normalize to [0, 1]

    print(f"Cosine Similarity: {cosine_similarity * 100:.2f}%")

    if cosine_similarity > 0.5:
        print("✓ Partial file shows some similarity to full file (expected)")
    else:
        print("✗ Unexpected low similarity")

    print()

    # Final Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    if all_passed and full_file_result and part1_full_file:
        print("✓ ALL TESTS PASSED")
        print("  - Full file fingerprinting works correctly")
        print("  - No-segmentation option is functional")
        print("  - Fingerprints are valid and normalized")
    else:
        print("✗ SOME TESTS FAILED")
        print("  Please review the output above for details")

    print("=" * 80)

if __name__ == "__main__":
    try:
        test_no_segmentation()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
