# Quick Start Guide

Get the Audio Fingerprint Verifier up and running in minutes!

## Docker Setup (Recommended - 2 minutes)

1. **Clone or navigate to the project directory**
```bash
cd audio-fingerprint-webapp
```

2. **Start the application**
```bash
docker-compose up --build
```

3. **Open your browser**
```
http://localhost:5002
```

That's it! The application is now running with MongoDB.

## Usage Example

### 1. Generate a Fingerprint

1. Click the "Generate Fingerprint" tab
2. Upload an audio file (MP3, WAV, etc.)
3. Choose segmentation mode:
   - **Automatic**: Set chunk duration (e.g., 10 seconds)
   - **Manual**: Click on waveform to create custom regions
4. Click "Generate Fingerprint"
5. Click "Store Fingerprint" to save to MongoDB

### 2. Verify Audio

1. Click the "Verify Audio" tab
2. Upload the same audio file (or a modified version)
3. Click "Verify Audio"
4. View results:
   - **Match > 85%**: Audio is verified ✓
   - **Match < 85%**: Audio has been modified ✗
   - See segment-by-segment analysis

### 3. View Stored Fingerprints

1. Click the "Stored Fingerprints" tab
2. Browse all stored fingerprints with:
   - Audio file playback
   - Detailed metadata
   - Segment breakdown
   - Fingerprint vectors
3. Click "View Details" for full information
4. Click "Delete" to remove

## Testing Modification Detection

1. Generate and store a fingerprint for an audio file
2. Modify the audio file:
   - Edit with audio software
   - Change volume
   - Cut/trim sections
   - Add effects
3. Verify the modified file
4. Observe verification failure and see which segments changed

## Docker Commands

```bash
# Start containers
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Remove all data
docker-compose down -v

# Rebuild after changes
docker-compose up --build
```

## Accessing MongoDB

```bash
# Connect to MongoDB container
docker exec -it audio-fingerprint-mongodb mongosh

# Use the database
use audio_fingerprint_db

# View fingerprints
db.fingerprints.find().pretty()

# View audio files
db.fs.files.find().pretty()

# Exit
exit
```

## Troubleshooting

### Port Already in Use

If port 5002 or 27017 is already in use:

Edit `docker-compose.yml`:
```yaml
services:
  flask-app:
    ports:
      - "5003:5002"  # Change 5003 to any available port
```

Then update `frontend/js/app.js`:
```javascript
const API_BASE = 'http://localhost:5003/api';
```

### Container Errors

```bash
# Check what's wrong
docker-compose logs flask-app
docker-compose logs mongodb

# Force rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Clear All Data

```bash
# Remove everything including stored fingerprints
docker-compose down -v
docker-compose up --build
```

## Manual Setup (Alternative)

If you prefer not to use Docker:

1. Install MongoDB locally
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start MongoDB:
   ```bash
   mongod
   ```
4. Start the application:
   ```bash
   python backend/app.py
   ```
5. Open `http://localhost:5002`

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the API endpoints
- Customize fingerprinting parameters
- Integrate with your applications

## Support

For issues or questions:
- Check the [README.md](README.md) troubleshooting section
- Review Docker logs
- Check browser console for errors
