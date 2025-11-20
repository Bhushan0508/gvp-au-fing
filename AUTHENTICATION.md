# Audio Authentication for S.N. Goenka's Teachings

This application is specifically designed to verify the authenticity of Reverend Teacher S.N. Goenka's audio recordings, ensuring that his teachings remain unaltered and genuine.

## Purpose

Protect the integrity of S.N. Goenka's Dhamma teachings by:
- **Detecting tampering**: Identify any modifications to the original recordings
- **Verifying authenticity**: Confirm recordings are genuine and unaltered
- **Partial file support**: Validate partial recordings as long as they're untampered
- **Preserving teachings**: Maintain the purity of the original message

## How It Works

### Dual Verification System

#### 1. Cryptographic Hash (SHA-256)
- **What it does**: Creates an exact digital signature of the audio
- **Purpose**: Detects ANY modification, even a single bit
- **Use case**: Exact byte-level verification
- **Result**: Pass/Fail - no tolerance for changes

#### 2. Perceptual Fingerprint
- **What it does**: Analyzes acoustic characteristics of the audio
- **Purpose**: Detects content tampering while allowing format conversion
- **Features analyzed**:
  - MFCC (Mel-Frequency Cepstral Coefficients) - voice characteristics
  - Chroma features - pitch and melody
  - Spectral contrast - frequency distribution
  - Harmonic-to-noise ratio - voice quality
  - Temporal envelope - speech patterns
  - Zero-crossing rate - audio texture

### Verification Thresholds

- **95%+ similarity**: ✓ FULLY VERIFIED - Authentic
- **Below 95%**: ✗ TAMPERED - Content modified
- **Partial file**: ✓ AUTHENTIC if all present segments match

## Verification Scenarios

### Scenario 1: Complete Authentic Recording
```
Original audio fingerprint stored
→ Verify same audio file
→ Result: ✓ FULLY VERIFIED - AUTHENTIC
  - All segments match exactly (SHA-256)
  - 100% perceptual similarity
  - No tampering detected
```

### Scenario 2: Partial Recording (Untampered)
```
Original: 60 minutes (12 segments)
Verify:   30 minutes (6 segments)

→ Result: ✓ PARTIAL FILE - AUTHENTIC
  - All 6 segments match original
  - No tampering in present segments
  - Valid authentication for partial content
```

### Scenario 3: Tampered Recording
```
Original audio → Edit voice → Remove sections → Add content
→ Verify modified file
→ Result: ✗ TAMPERED CONTENT DETECTED
  - Specific time ranges flagged
  - Similarity drops below 95%
  - Cryptographic hash mismatch
  - Exact tampering locations shown
```

### Scenario 4: Format Conversion (Legitimate)
```
Original: WAV 44.1kHz
Convert: MP3 320kbps

→ Result: ✓ VERIFIED (Perceptual Match)
  - Cryptographic hash differs (different format)
  - Perceptual fingerprint matches (same content)
  - Legitimate format change detected
```

## Verification Process

### Step 1: Store Original Fingerprint
1. Upload authentic S.N. Goenka recording
2. Generate dual fingerprints:
   - SHA-256 hash for each 5-second segment
   - Perceptual fingerprint for each segment
3. Store in MongoDB with metadata
4. Original audio file preserved for reference

### Step 2: Verify Recording
1. Upload audio file to verify
2. Generate fingerprints using same algorithm
3. Compare against stored fingerprints:
   - Match segments by time overlap
   - Check SHA-256 for exact match
   - Check perceptual similarity (95% threshold)
4. Generate detailed report

### Step 3: Review Results
The verification report shows:
- **Overall Status**: VERIFIED / PARTIAL / TAMPERED
- **Valid Segments**: Time ranges that match
- **Tampered Segments**: Specific locations of tampering
- **Similarity Scores**: Percentage match for each segment
- **Verification Type**: Exact vs Perceptual match

## Understanding the Results

### ✓ FULLY VERIFIED - AUTHENTIC
- All segments match at ≥95% similarity
- No tampering detected
- Original teaching is intact
- **Action**: Audio is safe to use

### ✓ PARTIAL FILE - AUTHENTIC
- File is shorter than original
- All present segments match at ≥95%
- No tampering in available content
- **Action**: Audio is authentic but incomplete

### ⚠ TAMPERED CONTENT DETECTED
- One or more segments below 95% similarity
- Specific time ranges show modifications
- Original content has been altered
- **Action**: DO NOT USE - Content compromised

## Technical Details

### Fingerprint Features (86 values per segment)

1. **MFCC Features (39 values)**
   - Mean (13) - Average voice characteristics
   - Std (13) - Variation in voice
   - Delta (13) - Changes over time

2. **Chroma Features (24 values)**
   - Mean (12) - Pitch classes
   - Std (12) - Pitch variation

3. **Spectral Features (16 values)**
   - Centroid mean/std - Brightness
   - Rolloff mean/std - Frequency content
   - Contrast mean/std (12) - Frequency bands

4. **Temporal Features (7 values)**
   - Zero-crossing rate - Audio texture
   - Energy - Loudness
   - Envelope (4) - Speech dynamics
   - Harmonic-to-noise ratio - Voice quality

### Similarity Metrics

The system uses three similarity measures:
1. **Euclidean Distance** (30% weight)
2. **Cosine Similarity** (40% weight)
3. **Pearson Correlation** (30% weight)

Combined similarity ≥ 95% required for verification.

### Segment Duration

Default: 5 seconds
- Small enough to detect localized tampering
- Large enough for robust fingerprinting
- Configurable in the UI

## Best Practices

### For Original Recordings

1. **Store immediately**: Fingerprint original recordings as soon as received
2. **Preserve metadata**: Include source, date, location information
3. **High quality**: Use lossless formats (WAV, FLAC) when possible
4. **Multiple copies**: Store fingerprints of different versions/formats

### For Verification

1. **Check all recordings**: Verify before distribution
2. **Document results**: Save verification reports
3. **Investigate failures**: Any tampering should be investigated
4. **Regular audits**: Periodically re-verify stored recordings

### For Distribution

1. **Include fingerprint**: Distribute with fingerprint metadata
2. **Verification instructions**: Provide users with verification steps
3. **Report tampering**: Report any tampered copies found
4. **Version tracking**: Maintain version history

## Security Considerations

### Strengths
✓ Detects content modification
✓ Identifies exact tampering locations
✓ Resistant to format conversion
✓ Validates partial files
✓ Cryptographic security (SHA-256)

### Limitations
⚠ Requires original fingerprint storage
⚠ Cannot verify what's not present (deletions)
⚠ Threshold-based (may need adjustment)
⚠ Large files require more processing time

## Frequently Asked Questions

### Q: Can the system detect voice deepfakes?
A: Yes, voice deepfakes will show low perceptual similarity as the acoustic characteristics differ significantly from the original.

### Q: What if I only have part of a recording?
A: Partial recordings can be verified. The system will check only the segments present. If they match, the partial file is authentic.

### Q: Can someone bypass the verification?
A: To bypass verification, an attacker would need:
1. The original fingerprint (stored securely)
2. To modify audio AND match 86 acoustic features
3. To maintain ≥95% similarity across all metrics
This is computationally extremely difficult.

### Q: What about noise or quality degradation?
A: The perceptual fingerprint is robust to:
- Background noise (within reason)
- Format conversion (MP3, AAC, etc.)
- Slight quality degradation
But significant degradation may lower similarity below 95%.

### Q: How do I report tampered recordings?
A: If you find tampered recordings:
1. Save the verification report
2. Note the source of the audio
3. Contact your Dhamma organization
4. Do not distribute the file

## Conclusion

This system provides robust authentication of S.N. Goenka's audio teachings, ensuring that practitioners receive genuine, unaltered guidance. By combining cryptographic security with perceptual analysis, it detects tampering while allowing legitimate use cases like format conversion and partial recordings.

The integrity of the Dhamma teachings is paramount, and this tool helps preserve that integrity for future generations.

---

*May all beings be happy. May all beings be peaceful. May all beings be liberated.*
