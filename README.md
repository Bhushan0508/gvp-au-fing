# Audio Fingerprint Verifier

A full-stack web application for generating and verifying audio fingerprints using acoustic fingerprinting techniques. The app supports both full audio verification and partial fingerprinting with automatic chunking and manual region selection.

## Features

- **Triple Verification System**:
  - **SHA-256 Cryptographic Hash**: Exact byte-level verification
  - **Custom Perceptual Fingerprint**: 86 acoustic features (MFCC, chroma, spectral analysis)
  - **Chromaprint**: Industry-standard audio fingerprinting (used by MusicBrainz)
- **Full Audio Verification**: Verify complete audio files against stored fingerprints
- **Partial Fingerprinting**:
  - Automatic time-based chunking (configurable duration)
  - Manual region selection via interactive waveform
- **Tamper Detection**: Identifies exact time ranges of modifications with segment-level analysis
- **Modification Detection**: Verification fails if audio content has been modified
- **Similarity Scoring**: Shows percentage match for all three verification methods
- **MongoDB Storage**: Store original audio files and fingerprints in MongoDB with GridFS
- **Enhanced View**: Detailed fingerprint information with audio playback and metadata
- **Docker Support**: Easy deployment with Docker Compose

## Technology Stack

### Backend
- Python 3.11
- Flask (web framework)
- MongoDB with GridFS (database and file storage)
- PyMongo (MongoDB driver)
- NumPy & SciPy (audio processing)

### Frontend
- Vanilla JavaScript
- Web Audio API
- HTML5 Canvas for waveform visualization
- Responsive CSS

### Infrastructure
- Docker & Docker Compose
- MongoDB 7.0

## Installation & Running

### Option 1: Docker (Recommended)

This is the easiest way to run the application with all dependencies.

#### Prerequisites
- Docker
- Docker Compose

#### Steps

1. Navigate to the project directory:
```bash
cd audio-fingerprint-webapp
```

2. Build and start the containers:
```bash
docker-compose up --build
```

3. Open your browser and navigate to:
```
http://localhost:5002
```

4. To stop the containers:
```bash
docker-compose down
```

5. To remove all data (including stored fingerprints):
```bash
docker-compose down -v
```

### Option 2: Manual Setup

#### Prerequisites
- Python 3.8 or higher
- MongoDB 4.0 or higher
- pip (Python package manager)

#### Steps

1. Start MongoDB:
```bash
# On Linux/Mac
mongod --dbpath /path/to/data/directory

# Or use your system's MongoDB service
sudo systemctl start mongodb
```

2. Navigate to the project directory:
```bash
cd audio-fingerprint-webapp
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set MongoDB connection (optional):
```bash
export MONGO_URI="mongodb://localhost:27017/"
```

5. Start the Flask backend server:
```bash
python backend/app.py
```

The server will start on `http://localhost:5002`

6. Open your browser and navigate to:
```
http://localhost:5002
```

## Usage

### Generating Fingerprints

1. **Upload Audio**: Click "Generate Fingerprint" tab and upload an audio file (MP3, WAV, etc.)

2. **Choose Segmentation Method**:
   - **Automatic Chunking**: Select automatic mode and set chunk duration (default: 10 seconds)
   - **Manual Selection**: Select manual mode, view the waveform, and click to add custom regions

3. **Generate**: Click "Generate Fingerprint" button to process the audio

4. **Store**: Click "Store Fingerprint" to save it to the database

### Verifying Audio

1. **Upload Test Audio**: Go to "Verify Audio" tab and upload the audio file to verify

2. **Verify**: Click "Verify Audio" button

3. **View Results**:
   - See overall similarity percentage
   - Check if verification passed (>85% similarity threshold)
   - Review segment-by-segment analysis for partial matches

### Managing Stored Fingerprints

1. Go to "Stored Fingerprints" tab
2. View all stored fingerprints with comprehensive metadata:
   - Filename and creation date
   - Duration and sample rate
   - Number of segments
   - Fingerprint feature count
   - Audio file size and type
   - Segment breakdown (time ranges)
   - Audio player for playback
3. Click "View Details" to see the full fingerprint vector
4. Click "Delete" to remove fingerprints and associated audio files

## How It Works

### Acoustic Fingerprinting Algorithm

The fingerprint generation uses multiple audio features:

1. **MFCC (Mel-Frequency Cepstral Coefficients)**:
   - Extracts 13 coefficients representing spectral envelope
   - Captures timbre and tonal characteristics

2. **Spectral Features**:
   - Spectral Centroid (brightness)
   - Spectral Rolloff (frequency content distribution)

3. **Temporal Features**:
   - Zero-Crossing Rate (noisiness)
   - Energy (loudness)

Each feature is normalized and combined into a single fingerprint vector.

### Verification Process

1. Generate fingerprint for the audio to verify
2. Compare against all stored fingerprints using similarity metric
3. Calculate similarity as the percentage of matching features (within tolerance)
4. Verification passes if similarity > 85%

### Modification Detection

If the audio is modified:
- The fingerprint features will change
- Similarity score drops below threshold
- Verification fails
- Segment analysis shows which parts were modified

## API Endpoints

### POST /api/fingerprint/store
Store a new fingerprint with audio file
```json
{
  "filename": "audio.mp3",
  "fullFingerprint": [0.1, 0.2, ...],
  "segments": [...],
  "audioData": "base64-encoded-audio-file",
  "metadata": {
    "duration": 120.5,
    "sampleRate": 22050,
    "fileSize": 2048576,
    "fileType": "audio/mpeg"
  }
}
```

### POST /api/fingerprint/verify
Verify an audio fingerprint
```json
{
  "fullFingerprint": [0.1, 0.2, ...],
  "segments": [...]
}
```

### GET /api/fingerprints
Get all stored fingerprints with metadata

### GET /api/fingerprint/:id
Get a specific fingerprint by ID

### DELETE /api/fingerprint/:id
Delete a fingerprint and its audio file by ID

### GET /api/audio/:file_id
Stream/download the original audio file

### GET /api/stats
Get database statistics (total fingerprints, total storage)

## Project Structure

```
audio-fingerprint-webapp/
├── backend/
│   ├── app.py              # Flask server and API endpoints with MongoDB
│   └── fingerprint.py      # Acoustic fingerprinting algorithm
├── frontend/
│   ├── index.html          # Main HTML structure
│   ├── css/
│   │   └── style.css       # Styling
│   └── js/
│       ├── app.js          # Main application logic
│       └── audioProcessor.js # Audio processing and fingerprinting
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose orchestration
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## MongoDB Collections

### fingerprints
Stores fingerprint data and metadata
```javascript
{
  _id: ObjectId,
  filename: String,
  fullFingerprint: Array<Number>,
  segments: Array<{startTime, endTime, fingerprint}>,
  audioFileId: String (GridFS file ID),
  metadata: {
    duration: Number,
    sampleRate: Number,
    fileSize: Number,
    fileType: String
  },
  createdAt: Date
}
```

### fs.files & fs.chunks (GridFS)
Stores original audio files in MongoDB

## Configuration

### Environment Variables

- `MONGO_URI`: MongoDB connection string (default: `mongodb://mongodb:27017/`)
- `FLASK_ENV`: Flask environment (default: `development`)

### Application Settings

#### Chunk Duration
Default: 10 seconds
Modify in the UI or change default in `audioProcessor.js`

#### Similarity Threshold
Default: 85% for verification pass
Modify in `backend/app.py` (compare_fingerprints function)

#### Sample Rate
Default: 22050 Hz
Modify in `audioProcessor.js` and `backend/fingerprint.py`

#### Port
Default: 5002
Modify in `backend/app.py`, `frontend/js/app.js`, and `docker-compose.yml`

## Troubleshooting

### Docker Issues

#### Containers won't start
```bash
# Check container logs
docker-compose logs flask-app
docker-compose logs mongodb

# Rebuild containers
docker-compose down
docker-compose up --build
```

#### MongoDB connection refused
- Ensure MongoDB container is running: `docker-compose ps`
- Check network connectivity: `docker network ls`
- Verify MONGO_URI environment variable

#### Port conflicts
- Check if port 5002 or 27017 is already in use
- Modify ports in `docker-compose.yml`

### Application Issues

#### Audio file won't load
- Ensure browser supports the audio format
- Check browser console for errors
- Try converting to WAV or MP3
- Check file size (large files may cause browser issues)

#### Verification always fails
- Check that the same audio file is being used
- Ensure audio hasn't been re-encoded with different settings
- Lower the similarity threshold if needed
- Verify fingerprint generation completed successfully

#### Audio playback doesn't work
- Check browser console for network errors
- Verify audio file was stored (check MongoDB)
- Ensure GridFS file ID is valid

### Server Issues

#### Server won't start (manual setup)
- Check Python version (3.8+)
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check port 5002 is not in use: `lsof -i :5002`
- Verify MongoDB is running: `mongosh` or `mongo`

#### MongoDB connection issues
- Check MongoDB is running on the correct port
- Verify MONGO_URI environment variable
- Check MongoDB authentication settings

## Security Notes

- This is a development server (Flask debug mode)
- For production, use a production WSGI server (gunicorn, uWSGI)
- Add authentication for storing/deleting fingerprints
- Implement rate limiting for API endpoints
- Add input validation and sanitization

## License

MIT License - feel free to use and modify as needed
