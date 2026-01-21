from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
import gridfs
import json
import os
from datetime import datetime
from pathlib import Path
import base64
import numpy as np
import librosa

app = Flask(__name__, static_folder='../frontend')
CORS(app)

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://mongodb:27017/')
client = MongoClient(MONGO_URI)
db = client['audio_fingerprint_db']
fingerprints_collection = db['fingerprints']
fs = gridfs.GridFS(db)

# Initialize vector fingerprinter (optional - will gracefully fail if Milvus not available)
try:
    from vector_fingerprint import VectorFingerprinter
    print("Vector fingerprinting module available, will initialize on first use")
    vector_fp = None
    VECTOR_ENABLED = False  # Will be enabled on first use
    _vector_fp_module = VectorFingerprinter
except Exception as e:
    vector_fp = None
    _vector_fp_module = None
    VECTOR_ENABLED = False
    print(f"Vector fingerprinting disabled: {e}")

def get_vector_fingerprinter():
    global vector_fp, VECTOR_ENABLED, _vector_fp_module
    if vector_fp is None and _vector_fp_module is not None:
        try:
            vector_fp = _vector_fp_module(milvus_host=os.getenv('MILVUS_HOST', 'milvus'))
            VECTOR_ENABLED = True
            print("Vector fingerprinting enabled with CLAP + Milvus")
        except Exception as e:
            print(f"Failed to initialize vector fingerprinting: {e}")
    return vector_fp

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/fingerprint/store', methods=['POST'])
def store_fingerprint():
    try:
        data = request.json
        filename = data.get('filename')
        full_fingerprint = data.get('fullFingerprint')
        segments = data.get('segments', [])
        metadata = data.get('metadata', {})
        audio_data = data.get('audioData')

        file_id = None
        if audio_data:
            audio_bytes = base64.b64decode(audio_data.split(',')[1] if ',' in audio_data else audio_data)
            file_id = fs.put(
                audio_bytes,
                filename=filename,
                content_type='audio/mpeg',
                upload_date=datetime.now()
            )

        fingerprint_data = {
            'filename': filename,
            'fullFingerprint': full_fingerprint,
            'segments': segments,
            'metadata': metadata,
            'audioFileId': str(file_id) if file_id else None,
            'createdAt': datetime.now()
        }

        result = fingerprints_collection.insert_one(fingerprint_data)
        fingerprint_data['_id'] = str(result.inserted_id)
        fingerprint_data['createdAt'] = fingerprint_data['createdAt'].isoformat()

        return jsonify({'success': True, 'id': str(result.inserted_id), 'data': fingerprint_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprint/verify', methods=['POST'])
def verify_fingerprint():
    try:
        data = request.json
        full_fingerprint = data.get('fullFingerprint')
        segments = data.get('segments', [])
        verification_methods = data.get('verificationMethods', {
            'cryptographic': True,
            'blake3': True,
            'perceptual': True,
            'chromaprint': True
        })

        matches = []

        for stored in fingerprints_collection.find():
            # Full audio comparison
            full_match = compare_fingerprints(full_fingerprint, stored['fullFingerprint'])

            # Segment-level comparison for partial matching and tamper detection
            segment_matches = []
            crypto_matches = []
            verification_result = {}

            # Handle no-segmentation mode (only full-file comparison)
            if not segments and not stored.get('segments'):
                # Both files have no segmentation - pure full-file comparison
                verification_result = {
                    'isFullFileOnly': True,
                    'noSegmentation': True,
                    'validRegions': [],
                    'tamperedRegions': [],
                    'enabledMethods': verification_methods
                }
            elif segments and stored.get('segments'):
                # Normal segmented comparison
                segment_matches, crypto_matches, verification_result = compare_segments(
                    segments,
                    stored['segments'],
                    verification_methods
                )

                # Calculate overall statistics
                if segment_matches:
                    valid_segments = [s for s in segment_matches if s['matched']]
                    tampered_segments = [s for s in segment_matches if not s['matched'] and s['similarity'] < 0.95]

                    verification_result['totalSegments'] = len(segment_matches)
                    verification_result['validSegments'] = len(valid_segments)
                    verification_result['tamperedSegments'] = len(tampered_segments)
                    verification_result['partialMatch'] = len(valid_segments) > 0
                    verification_result['avgSimilarity'] = sum(s['similarity'] for s in segment_matches) / len(segment_matches)

            if full_match['similarity'] > 0.5 or any(s.get('matched') for s in segment_matches):
                matches.append({
                    'id': str(stored['_id']),
                    'filename': stored['filename'],
                    'fullMatch': full_match,
                    'segmentMatches': segment_matches,
                    'cryptoMatches': crypto_matches,
                    'verificationResult': verification_result,
                    'metadata': stored.get('metadata', {}),
                    'createdAt': stored['createdAt'].isoformat(),
                    'hasAudioFile': stored.get('audioFileId') is not None
                })

        matches.sort(key=lambda x: x['fullMatch']['similarity'], reverse=True)

        return jsonify({'success': True, 'matches': matches})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprints', methods=['GET'])
def get_fingerprints():
    try:
        fingerprints = []
        for fp in fingerprints_collection.find().sort('createdAt', -1):
            fp['_id'] = str(fp['_id'])
            fp['createdAt'] = fp['createdAt'].isoformat()

            audio_file_size = None
            if fp.get('audioFileId'):
                try:
                    file_obj = fs.get(ObjectId(fp['audioFileId']))
                    audio_file_size = file_obj.length
                except:
                    pass

            fp['audioFileSize'] = audio_file_size
            fp['hasAudioFile'] = fp.get('audioFileId') is not None
            fingerprints.append(fp)

        return jsonify({'success': True, 'fingerprints': fingerprints})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprint/<fingerprint_id>', methods=['GET'])
def get_fingerprint(fingerprint_id):
    try:
        fp = fingerprints_collection.find_one({'_id': ObjectId(fingerprint_id)})
        if not fp:
            return jsonify({'success': False, 'error': 'Fingerprint not found'}), 404

        fp['_id'] = str(fp['_id'])
        fp['createdAt'] = fp['createdAt'].isoformat()
        fp['hasAudioFile'] = fp.get('audioFileId') is not None

        return jsonify({'success': True, 'fingerprint': fp})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprint/<fingerprint_id>', methods=['DELETE'])
def delete_fingerprint(fingerprint_id):
    try:
        fp = fingerprints_collection.find_one({'_id': ObjectId(fingerprint_id)})
        if fp and fp.get('audioFileId'):
            try:
                fs.delete(ObjectId(fp['audioFileId']))
            except:
                pass

        fingerprints_collection.delete_one({'_id': ObjectId(fingerprint_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<file_id>', methods=['GET'])
def get_audio(file_id):
    try:
        file_obj = fs.get(ObjectId(file_id))
        return Response(
            file_obj.read(),
            mimetype=file_obj.content_type or 'audio/mpeg',
            headers={'Content-Disposition': f'inline; filename="{file_obj.filename}"'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total_fingerprints = fingerprints_collection.count_documents({})
        total_audio_size = 0

        for fp in fingerprints_collection.find({'audioFileId': {'$ne': None}}):
            try:
                file_obj = fs.get(ObjectId(fp['audioFileId']))
                total_audio_size += file_obj.length
            except:
                pass

        return jsonify({
            'success': True,
            'stats': {
                'totalFingerprints': total_fingerprints,
                'totalAudioSize': total_audio_size,
                'totalAudioSizeMB': round(total_audio_size / (1024 * 1024), 2),
                'vectorEnabled': VECTOR_ENABLED
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprint/vector/generate', methods=['POST'])
def generate_vector_fingerprint():
    """Generate vector-based fingerprint using CLAP embeddings"""
    vfp = get_vector_fingerprinter()
    if vfp is None:
        return jsonify({'success': False, 'error': 'Vector fingerprinting not available'}), 503

    try:
        data = request.json
        audio_data_base64 = data.get('audioData')

        if not audio_data_base64:
            return jsonify({'success': False, 'error': 'No audio data provided'}), 400

        # Decode audio data
        audio_bytes = base64.b64decode(audio_data_base64.split(',')[1] if ',' in audio_data_base64 else audio_data_base64)

        # Load audio using librosa
        import io
        audio_data, sr = librosa.load(io.BytesIO(audio_bytes), sr=vfp.sample_rate, mono=True)

        # Generate embeddings for segments
        segments = vfp.generate_segment_embeddings(audio_data, segment_duration=10.0)

        return jsonify({
            'success': True,
            'segments': len(segments),
            'vectorSegments': segments,
            'duration': len(audio_data) / sr
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprint/vector/store', methods=['POST'])
def store_vector_fingerprint():
    """Store vector embeddings in Milvus"""
    vfp = get_vector_fingerprinter()
    if vfp is None:
        return jsonify({'success': False, 'error': 'Vector fingerprinting not available'}), 503

    try:
        data = request.json
        fingerprint_id = data.get('fingerprintId')
        vector_segments = data.get('vectorSegments', [])

        if not fingerprint_id or not vector_segments:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400

        # Store in Milvus
        success = vfp.store_embeddings(fingerprint_id, vector_segments)

        if success:
            return jsonify({'success': True, 'message': f'Stored {len(vector_segments)} vector embeddings'})
        else:
            return jsonify({'success': False, 'error': 'Failed to store embeddings'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fingerprint/vector/verify', methods=['POST'])
def verify_vector_fingerprint():
    """Verify audio using vector similarity search"""
    vfp = get_vector_fingerprinter()
    if vfp is None:
        return jsonify({'success': False, 'error': 'Vector fingerprinting not available'}), 503

    try:
        data = request.json
        query_segments = data.get('vectorSegments', [])
        stored_fingerprint_id = data.get('fingerprintId')

        if not query_segments or not stored_fingerprint_id:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400

        # Verify using vector similarity
        result = vfp.verify_audio(query_segments, stored_fingerprint_id)

        return jsonify({
            'success': True,
            'verification': result
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def compare_chromaprint(fp1, fp2):
    """
    Compare two Chromaprint fingerprints
    Chromaprint returns a compressed fingerprint string
    We use bit error rate for comparison
    """
    if not fp1 or not fp2:
        return 0.0

    try:
        # Chromaprint fingerprints are base64-encoded compressed data
        # Simple approach: check string similarity as proxy for audio similarity
        # In production, you'd decode and compare the actual bit patterns

        if fp1 == fp2:
            return 1.0

        # Calculate Levenshtein distance-based similarity for the compressed strings
        len1, len2 = len(fp1), len(fp2)
        if len1 == 0 or len2 == 0:
            return 0.0

        # Create distance matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if fp1[i-1] == fp2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )

        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        similarity = 1.0 - (distance / max_len)

        return max(0.0, similarity)

    except Exception as e:
        print(f"Chromaprint comparison error: {e}")
        return 0.0

def compare_fingerprints(fp1, fp2, threshold=0.95):
    """
    Compare two perceptual fingerprints with enhanced similarity metrics
    Returns similarity score and match status
    """
    if not fp1 or not fp2 or len(fp1) != len(fp2):
        return {'similarity': 0.0, 'matched': False, 'method': 'none'}

    # Euclidean distance
    euclidean_dist = sum((fp1[i] - fp2[i]) ** 2 for i in range(len(fp1))) ** 0.5
    euclidean_similarity = 1 / (1 + euclidean_dist)

    # Cosine similarity
    dot_product = sum(fp1[i] * fp2[i] for i in range(len(fp1)))
    magnitude1 = sum(x ** 2 for x in fp1) ** 0.5
    magnitude2 = sum(x ** 2 for x in fp2) ** 0.5
    cosine_similarity = dot_product / (magnitude1 * magnitude2 + 1e-10)
    cosine_similarity = (cosine_similarity + 1) / 2  # Normalize to [0, 1]

    # Pearson correlation
    mean1 = sum(fp1) / len(fp1)
    mean2 = sum(fp2) / len(fp2)
    numerator = sum((fp1[i] - mean1) * (fp2[i] - mean2) for i in range(len(fp1)))
    denominator = (sum((x - mean1) ** 2 for x in fp1) * sum((x - mean2) ** 2 for x in fp2)) ** 0.5
    pearson_corr = numerator / (denominator + 1e-10)
    pearson_similarity = (pearson_corr + 1) / 2  # Normalize to [0, 1]

    # Combined similarity (weighted average)
    similarity = (euclidean_similarity * 0.3 + cosine_similarity * 0.4 + pearson_similarity * 0.3)

    return {
        'similarity': similarity,
        'matched': similarity >= threshold,
        'euclidean': euclidean_similarity,
        'cosine': cosine_similarity,
        'pearson': pearson_similarity,
        'method': 'perceptual'
    }

def compare_segments(segments_to_verify, stored_segments, verification_methods=None):
    """
    Compare segments with support for partial matching and tamper detection
    verification_methods: dict with keys 'cryptographic', 'perceptual', 'chromaprint'
    """
    if verification_methods is None:
        verification_methods = {
            'cryptographic': True,
            'perceptual': True,
            'chromaprint': True
        }

    segment_matches = []
    crypto_matches = []

    # Build verification result
    verification_result = {
        'isPartialFile': len(segments_to_verify) < len(stored_segments),
        'isComplete': len(segments_to_verify) == len(stored_segments),
        'hasExtendedContent': len(segments_to_verify) > len(stored_segments),
        'tamperedRegions': [],
        'validRegions': [],
        'enabledMethods': verification_methods
    }

    for i in range(len(segments_to_verify)):
        verify_seg = segments_to_verify[i]

        # Find best matching stored segment by fingerprint similarity
        # This allows matching partial files regardless of time position
        best_match = None
        best_match_idx = -1

        for j, stored_seg in enumerate(stored_segments):
            # First try time overlap for efficiency (same position in file)
            overlap_start = max(verify_seg['startTime'], stored_seg['startTime'])
            overlap_end = min(verify_seg['endTime'], stored_seg['endTime'])
            overlap = max(0, overlap_end - overlap_start)

            # If significant time overlap exists, prefer it
            if overlap > 2.0:  # More than 2 seconds overlap
                if best_match is None or overlap > best_match.get('overlap', 0):
                    best_match = {
                        'overlap': overlap,
                        'stored_idx': j,
                        'stored_seg': stored_seg,
                        'match_type': 'time_overlap'
                    }
                    best_match_idx = j

        # If no time overlap match found, try fingerprint-based matching
        # This handles partial files extracted from different positions
        if best_match is None:
            for j, stored_seg in enumerate(stored_segments):
                # Quick perceptual similarity check
                if verify_seg.get('fingerprint') and stored_seg.get('fingerprint'):
                    quick_similarity = compare_fingerprints(
                        verify_seg['fingerprint'],
                        stored_seg['fingerprint'],
                        threshold=0.80  # Lower threshold for finding candidates
                    )

                    # Accept matches with 80%+ similarity as candidates
                    if quick_similarity['similarity'] > 0.80:
                        if best_match is None or quick_similarity['similarity'] > best_match.get('similarity', 0):
                            best_match = {
                                'similarity': quick_similarity['similarity'],
                                'stored_idx': j,
                                'stored_seg': stored_seg,
                                'match_type': 'fingerprint'
                            }
                            best_match_idx = j

        if best_match:
            stored_seg = best_match['stored_seg']

            # Cryptographic hash comparison (exact match)
            # Only apply crypto check for time-overlap matches (same file position)
            # For extracted partial files, crypto will always fail due to re-encoding
            crypto_matched = None  # Default: not applicable
            if verification_methods.get('cryptographic', True):
                # Only use crypto for time-overlap matches, not fingerprint-based matches
                if best_match.get('match_type') == 'time_overlap':
                    if verify_seg.get('cryptoHash') and stored_seg.get('cryptoHash'):
                        crypto_matched = verify_seg['cryptoHash'] == stored_seg['cryptoHash']
                        crypto_matches.append({
                            'segmentIndex': i,
                            'matched': crypto_matched,
                            'startTime': verify_seg['startTime'],
                            'endTime': verify_seg['endTime']
                        })
                # If not time_overlap, crypto_matched stays None (not applicable)

            # BLAKE3 hash comparison (exact match, faster than SHA-256)
            blake3_matched = None  # Default: not applicable
            if verification_methods.get('blake3', True):
                # Only use blake3 for time-overlap matches, not fingerprint-based matches
                if best_match.get('match_type') == 'time_overlap':
                    if verify_seg.get('blake3Hash') and stored_seg.get('blake3Hash'):
                        blake3_matched = verify_seg['blake3Hash'] == stored_seg['blake3Hash']
                # If not time_overlap, blake3_matched stays None (not applicable)

            # Chromaprint comparison (industry-standard audio matching)
            chromaprint_matched = None  # None means "not available"
            chromaprint_similarity = 0.0
            if verification_methods.get('chromaprint', True):
                if verify_seg.get('chromaprint') and stored_seg.get('chromaprint'):
                    chromaprint_similarity = compare_chromaprint(
                        verify_seg['chromaprint'],
                        stored_seg['chromaprint']
                    )
                    chromaprint_matched = chromaprint_similarity >= 0.9  # 90% threshold for Chromaprint
                # If chromaprint data is missing, keep as None (not applicable)

            # Perceptual fingerprint comparison
            perceptual_matched = False
            similarity = {'similarity': 0.0, 'euclidean': 0, 'cosine': 0, 'pearson': 0}
            if verification_methods.get('perceptual', True):
                # Use adaptive threshold based on match type
                # For partial files (fingerprint matching), use lower threshold (88%)
                # For complete files (time overlap), use medium threshold (92%)
                # Note: Lowered from 95% to 92% because browser audio decoding can introduce
                # slight variations even when loading the same file
                adaptive_threshold = 0.88 if best_match.get('match_type') == 'fingerprint' else 0.92

                similarity = compare_fingerprints(
                    verify_seg['fingerprint'],
                    stored_seg['fingerprint'],
                    threshold=adaptive_threshold
                )
                perceptual_matched = similarity['matched']

            # Determine overall match based on enabled methods
            methods_results = []
            if verification_methods.get('cryptographic', True) and crypto_matched is not None:
                # Only include crypto if it's applicable (time-overlap matches)
                methods_results.append(crypto_matched)
            if verification_methods.get('blake3', True) and blake3_matched is not None:
                # Only include blake3 if it's applicable (time-overlap matches)
                methods_results.append(blake3_matched)
            if verification_methods.get('perceptual', True):
                methods_results.append(perceptual_matched)
            if verification_methods.get('chromaprint', True) and chromaprint_matched is not None:
                # Only include chromaprint if data is available
                methods_results.append(chromaprint_matched)

            # Match if ANY enabled method passes
            overall_matched = any(methods_results) if methods_results else False

            # Tampered if ALL enabled methods fail
            is_tampered = not overall_matched

            segment_match = {
                'segmentIndex': i,
                'storedSegmentIndex': best_match_idx,
                'startTime': verify_seg['startTime'],
                'endTime': verify_seg['endTime'],
                'similarity': similarity['similarity'],
                'matched': overall_matched,
                'cryptoMatched': crypto_matched,
                'blake3Matched': blake3_matched,
                'chromaprintMatched': chromaprint_matched,
                'chromaprintSimilarity': chromaprint_similarity,
                'exactMatch': crypto_matched or blake3_matched,
                'perceptualMatch': perceptual_matched,
                'isTampered': is_tampered,
                'enabledMethods': verification_methods,
                'similarityDetails': {
                    'euclidean': similarity.get('euclidean', 0),
                    'cosine': similarity.get('cosine', 0),
                    'pearson': similarity.get('pearson', 0),
                    'chromaprint': chromaprint_similarity
                }
            }

            segment_matches.append(segment_match)

            # Track tampered and valid regions
            if is_tampered:
                verification_result['tamperedRegions'].append({
                    'startTime': verify_seg['startTime'],
                    'endTime': verify_seg['endTime'],
                    'similarity': similarity['similarity']
                })
            elif similarity['matched']:
                verification_result['validRegions'].append({
                    'startTime': verify_seg['startTime'],
                    'endTime': verify_seg['endTime'],
                    'exactMatch': crypto_matched
                })

    return segment_matches, crypto_matches, verification_result

if __name__ == '__main__':
    print('Audio Fingerprint Server running on http://localhost:5002')
    app.run(debug=True, host='0.0.0.0', port=5002)
