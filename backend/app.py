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

app = Flask(__name__, static_folder='../frontend')
CORS(app)

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://mongodb:27017/')
client = MongoClient(MONGO_URI)
db = client['audio_fingerprint_db']
fingerprints_collection = db['fingerprints']
fs = gridfs.GridFS(db)

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

        matches = []

        for stored in fingerprints_collection.find():
            full_match = compare_fingerprints(full_fingerprint, stored['fullFingerprint'])

            segment_matches = []
            if segments and stored.get('segments'):
                for i in range(min(len(segments), len(stored['segments']))):
                    similarity = compare_fingerprints(
                        segments[i]['fingerprint'],
                        stored['segments'][i]['fingerprint']
                    )
                    segment_matches.append({
                        'segmentIndex': i,
                        'startTime': segments[i]['startTime'],
                        'endTime': segments[i]['endTime'],
                        'similarity': similarity['similarity'],
                        'matched': similarity['matched']
                    })

            if full_match['similarity'] > 0.5 or any(s['matched'] for s in segment_matches):
                matches.append({
                    'id': str(stored['_id']),
                    'filename': stored['filename'],
                    'fullMatch': full_match,
                    'segmentMatches': segment_matches,
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
                'totalAudioSizeMB': round(total_audio_size / (1024 * 1024), 2)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def compare_fingerprints(fp1, fp2):
    if not fp1 or not fp2 or len(fp1) != len(fp2):
        return {'similarity': 0.0, 'matched': False}

    matches = sum(1 for i in range(len(fp1)) if abs(fp1[i] - fp2[i]) < 0.1)
    similarity = matches / len(fp1)

    return {'similarity': similarity, 'matched': similarity > 0.85}

if __name__ == '__main__':
    print('Audio Fingerprint Server running on http://localhost:5002')
    app.run(debug=True, host='0.0.0.0', port=5002)
