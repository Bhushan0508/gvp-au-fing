#!/usr/bin/env python3
"""
Test script to verify partial audio file matching
Tests: 10minanapana.mp3 (reference) vs 5minpart1.mp3 and 5minpart2.mp3
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fingerprint import AudioFingerprinter
import json
import numpy as np
import librosa

def format_time(seconds):
    """Format seconds as MM:SS"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

def test_verification():
    print("=" * 80)
    print("AUDIO FINGERPRINT VERIFICATION TEST")
    print("=" * 80)
    print()

    # Initialize fingerprinter
    fp = AudioFingerprinter()

    # File paths
    reference_file = "backend/10minana.mp3"
    part1_file = "backend/5minpart1.mp3"
    part2_file = "backend/5minpart2.mp3"

    print(f"Reference File: {reference_file}")
    print(f"Part 1 File: {part1_file}")
    print(f"Part 2 File: {part2_file}")
    print()

    # Process reference file
    print("Step 1: Processing Reference File (10minanapana.mp3)")
    print("-" * 80)
    audio_data, sr = librosa.load(reference_file, sr=fp.sample_rate, mono=True)
    ref_segments = fp.generate_segments(audio_data, segment_duration=5.0, include_chromaprint=False)
    ref_duration = len(audio_data) / sr

    ref_result = {
        'segments': ref_segments,
        'metadata': {
            'duration': ref_duration,
            'sampleRate': sr
        }
    }

    print(f"✓ Duration: {ref_duration:.2f}s ({format_time(ref_duration)})")
    print(f"✓ Segments: {len(ref_segments)}")
    print(f"✓ Sample Rate: {sr} Hz")
    print()

    # Show segment time ranges
    print("Reference Segments:")
    for i, seg in enumerate(ref_segments[:3]):
        print(f"  Segment {i}: {format_time(seg['startTime'])} - {format_time(seg['endTime'])}")
    if len(ref_segments) > 3:
        print(f"  ... ({len(ref_segments) - 3} more segments)")
    print()

    # Process part 1
    print("Step 2: Processing Part 1 (5minpart1.mp3)")
    print("-" * 80)
    audio_data, sr = librosa.load(part1_file, sr=fp.sample_rate, mono=True)
    part1_segments = fp.generate_segments(audio_data, segment_duration=5.0, include_chromaprint=False)
    part1_duration = len(audio_data) / sr

    part1_result = {
        'segments': part1_segments,
        'metadata': {
            'duration': part1_duration,
            'sampleRate': sr
        }
    }

    print(f"✓ Duration: {part1_duration:.2f}s ({format_time(part1_duration)})")
    print(f"✓ Segments: {len(part1_segments)}")
    print()

    # Process part 2
    print("Step 3: Processing Part 2 (5minpart2.mp3)")
    print("-" * 80)
    audio_data, sr = librosa.load(part2_file, sr=fp.sample_rate, mono=True)
    part2_segments = fp.generate_segments(audio_data, segment_duration=5.0, include_chromaprint=False)
    part2_duration = len(audio_data) / sr

    part2_result = {
        'segments': part2_segments,
        'metadata': {
            'duration': part2_duration,
            'sampleRate': sr
        }
    }

    print(f"✓ Duration: {part2_duration:.2f}s ({format_time(part2_duration)})")
    print(f"✓ Segments: {len(part2_segments)}")
    print()

    # Verify Part 1
    print("Step 4: Verifying Part 1 Against Reference")
    print("=" * 80)
    verify_part(part1_result, ref_result, "Part 1 (First 5 minutes)")

    # Verify Part 2
    print("\nStep 5: Verifying Part 2 Against Reference")
    print("=" * 80)
    verify_part(part2_result, ref_result, "Part 2 (Second 5 minutes)")

def compare_fingerprints(fp1, fp2, threshold=0.88):
    """Compare two fingerprints using multiple similarity metrics"""
    if not fp1 or not fp2 or len(fp1) != len(fp2):
        return 0.0

    fp1 = np.array(fp1)
    fp2 = np.array(fp2)

    # Euclidean distance
    euclidean_dist = np.sqrt(np.sum((fp1 - fp2) ** 2))
    euclidean_similarity = 1 / (1 + euclidean_dist)

    # Cosine similarity
    dot_product = np.dot(fp1, fp2)
    magnitude1 = np.linalg.norm(fp1)
    magnitude2 = np.linalg.norm(fp2)
    cosine_similarity = dot_product / (magnitude1 * magnitude2 + 1e-10)
    cosine_similarity = (cosine_similarity + 1) / 2  # Normalize to [0, 1]

    # Pearson correlation
    mean1 = np.mean(fp1)
    mean2 = np.mean(fp2)
    numerator = np.sum((fp1 - mean1) * (fp2 - mean2))
    denominator = np.sqrt(np.sum((fp1 - mean1) ** 2) * np.sum((fp2 - mean2) ** 2))
    pearson_corr = numerator / (denominator + 1e-10)
    pearson_similarity = (pearson_corr + 1) / 2  # Normalize to [0, 1]

    # Combined similarity (weighted average)
    similarity = (euclidean_similarity * 0.3 + cosine_similarity * 0.4 + pearson_similarity * 0.3)

    return similarity

def verify_part(verify_result, ref_result, part_name):
    """Verify a part against reference"""
    matched_segments = []
    unmatched_segments = []

    for i, verify_seg in enumerate(verify_result['segments']):
        best_match = None
        best_similarity = 0
        best_idx = -1

        # Try to find matching segment in reference
        for j, ref_seg in enumerate(ref_result['segments']):
            # Check time overlap first
            overlap_start = max(verify_seg['startTime'], ref_seg['startTime'])
            overlap_end = min(verify_seg['endTime'], ref_seg['endTime'])
            overlap = max(0, overlap_end - overlap_start)

            # Also check fingerprint similarity
            similarity = compare_fingerprints(
                verify_seg['fingerprint'],
                ref_seg['fingerprint']
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = ref_seg
                best_idx = j

        result = {
            'verify_segment': i,
            'verify_time': f"{format_time(verify_seg['startTime'])} - {format_time(verify_seg['endTime'])}",
            'matched_segment': best_idx,
            'matched_time': f"{format_time(best_match['startTime'])} - {format_time(best_match['endTime'])}" if best_match else "N/A",
            'similarity': best_similarity,
            'status': 'MATCH' if best_similarity >= 0.88 else 'NO MATCH'
        }

        if best_similarity >= 0.88:
            matched_segments.append(result)
        else:
            unmatched_segments.append(result)

    # Print results
    print(f"\n{part_name} Verification Results:")
    print("-" * 80)
    print(f"Total Segments: {len(verify_result['segments'])}")
    print(f"Matched Segments: {len(matched_segments)} ✓")
    print(f"Unmatched Segments: {len(unmatched_segments)} ✗")
    print()

    if matched_segments:
        print("Matched Segments:")
        for result in matched_segments:
            print(f"  Verify Seg {result['verify_segment']} ({result['verify_time']}) → "
                  f"Ref Seg {result['matched_segment']} ({result['matched_time']}) | "
                  f"Similarity: {result['similarity']*100:.1f}% | {result['status']}")

    if unmatched_segments:
        print()
        print("Unmatched Segments:")
        for result in unmatched_segments:
            print(f"  Verify Seg {result['verify_segment']} ({result['verify_time']}) | "
                  f"Best Similarity: {result['similarity']*100:.1f}% | {result['status']}")

    # Overall verdict
    print()
    print("=" * 80)
    if len(matched_segments) >= len(verify_result['segments']) * 0.8:
        print(f"✓ VERDICT: {part_name} is AUTHENTIC")
        print(f"  ({len(matched_segments)}/{len(verify_result['segments'])} segments matched = "
              f"{len(matched_segments)/len(verify_result['segments'])*100:.1f}%)")
    else:
        print(f"✗ VERDICT: {part_name} may be TAMPERED")
        print(f"  ({len(matched_segments)}/{len(verify_result['segments'])} segments matched = "
              f"{len(matched_segments)/len(verify_result['segments'])*100:.1f}%)")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_verification()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
