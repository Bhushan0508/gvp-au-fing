const API_BASE = 'http://localhost:5002/api';

const audioProcessor = new AudioProcessor();
let currentAudioData = null;
let currentAudioFile = null;
let currentFingerprint = null;
let currentSegments = [];
let manualRegions = [];
let waveformCanvas = null;
let waveformContext = null;

document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupGenerateTab();
    setupVerifyTab();
    setupStoredTab();
});

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');

            if (targetTab === 'stored') {
                loadStoredFingerprints();
            }
        });
    });
}

function setupGenerateTab() {
    const audioFile = document.getElementById('audioFile');
    const generateBtn = document.getElementById('generateBtn');
    const storeBtn = document.getElementById('storeBtn');
    const segmentModeRadios = document.querySelectorAll('input[name="segmentMode"]');

    audioFile.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        try {
            currentAudioFile = file;
            const audioInfo = await audioProcessor.loadAudioFile(file);
            currentAudioData = audioInfo.channelData;

            document.getElementById('fileName').textContent = file.name;
            document.getElementById('audioDuration').textContent = `${audioInfo.duration.toFixed(2)}s`;

            const audioPreview = document.getElementById('audioPreview');
            const audioPlayer = document.getElementById('audioPlayer');
            audioPlayer.src = URL.createObjectURL(file);
            audioPreview.classList.remove('hidden');

            document.getElementById('fingerprintResult').classList.add('hidden');

            if (document.querySelector('input[name="segmentMode"]:checked').value === 'manual') {
                drawWaveform(currentAudioData);
            }
        } catch (error) {
            console.error('Error loading audio:', error);
            alert('Error loading audio file: ' + error.message);
        }
    });

    segmentModeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            const autoOptions = document.querySelector('.auto-chunk-options');
            const manualOptions = document.querySelector('.manual-selection-options');

            if (e.target.value === 'auto') {
                autoOptions.style.display = 'block';
                manualOptions.classList.add('hidden');
            } else {
                autoOptions.style.display = 'none';
                manualOptions.classList.remove('hidden');
                if (currentAudioData) {
                    drawWaveform(currentAudioData);
                }
            }
        });
    });

    document.getElementById('addRegion').addEventListener('click', () => {
        const duration = currentAudioData.length / audioProcessor.sampleRate;
        const start = manualRegions.length > 0 ? manualRegions[manualRegions.length - 1].end : 0;
        const end = Math.min(start + 10, duration);

        if (start < duration) {
            addRegion(start, end);
        }
    });

    document.getElementById('clearRegions').addEventListener('click', () => {
        manualRegions = [];
        updateRegionsList();
        if (currentAudioData) {
            drawWaveform(currentAudioData);
        }
    });

    generateBtn.addEventListener('click', async () => {
        if (!currentAudioData) {
            alert('Please load an audio file first');
            return;
        }

        try {
            showProgress('generateProgress');

            const segmentMode = document.querySelector('input[name="segmentMode"]:checked').value;

            currentFingerprint = audioProcessor.generateFingerprint(currentAudioData);

            if (segmentMode === 'auto') {
                const chunkDuration = parseFloat(document.getElementById('chunkDuration').value);
                currentSegments = audioProcessor.generateSegments(currentAudioData, chunkDuration);
            } else {
                currentSegments = manualRegions.map(region => {
                    return audioProcessor.generateCustomSegment(
                        currentAudioData,
                        region.start,
                        region.end
                    );
                }).filter(s => s !== null);
            }

            hideProgress('generateProgress');
            displayFingerprintResult();
        } catch (error) {
            hideProgress('generateProgress');
            console.error('Error generating fingerprint:', error);
            alert('Error generating fingerprint: ' + error.message);
        }
    });

    storeBtn.addEventListener('click', async () => {
        if (!currentFingerprint) {
            alert('Please generate a fingerprint first');
            return;
        }

        try {
            const filename = document.getElementById('fileName').textContent;

            let audioDataBase64 = null;
            if (currentAudioFile) {
                const reader = new FileReader();
                audioDataBase64 = await new Promise((resolve, reject) => {
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(currentAudioFile);
                });
            }

            const response = await fetch(`${API_BASE}/fingerprint/store`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename,
                    fullFingerprint: currentFingerprint,
                    segments: currentSegments,
                    audioData: audioDataBase64,
                    metadata: {
                        duration: currentAudioData.length / audioProcessor.sampleRate,
                        sampleRate: audioProcessor.sampleRate,
                        fileSize: currentAudioFile ? currentAudioFile.size : 0,
                        fileType: currentAudioFile ? currentAudioFile.type : 'unknown'
                    }
                })
            });

            const result = await response.json();

            if (result.success) {
                showStatus('storeStatus', 'Fingerprint and audio file stored successfully!', 'success');
            } else {
                showStatus('storeStatus', 'Error: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error storing fingerprint:', error);
            showStatus('storeStatus', 'Error storing fingerprint: ' + error.message, 'error');
        }
    });
}

function setupVerifyTab() {
    const verifyAudioFile = document.getElementById('verifyAudioFile');
    const verifyBtn = document.getElementById('verifyBtn');

    verifyAudioFile.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        try {
            const audioInfo = await audioProcessor.loadAudioFile(file);
            currentAudioData = audioInfo.channelData;

            document.getElementById('verifyFileName').textContent = file.name;
            document.getElementById('verifyAudioDuration').textContent = `${audioInfo.duration.toFixed(2)}s`;

            const audioPreview = document.getElementById('verifyAudioPreview');
            const audioPlayer = document.getElementById('verifyAudioPlayer');
            audioPlayer.src = URL.createObjectURL(file);
            audioPreview.classList.remove('hidden');

            document.getElementById('verifyResult').classList.add('hidden');
        } catch (error) {
            console.error('Error loading audio:', error);
            alert('Error loading audio file: ' + error.message);
        }
    });

    verifyBtn.addEventListener('click', async () => {
        if (!currentAudioData) {
            alert('Please load an audio file to verify');
            return;
        }

        try {
            showProgress('verifyProgress');

            const fingerprint = audioProcessor.generateFingerprint(currentAudioData);
            const segments = audioProcessor.generateSegments(currentAudioData, 10.0);

            const response = await fetch(`${API_BASE}/fingerprint/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fullFingerprint: fingerprint,
                    segments: segments
                })
            });

            const result = await response.json();

            hideProgress('verifyProgress');

            if (result.success) {
                displayVerificationResults(result.matches);
            } else {
                alert('Error: ' + result.error);
            }
        } catch (error) {
            hideProgress('verifyProgress');
            console.error('Error verifying audio:', error);
            alert('Error verifying audio: ' + error.message);
        }
    });
}

function setupStoredTab() {
    document.getElementById('refreshBtn').addEventListener('click', loadStoredFingerprints);
}

async function loadStoredFingerprints() {
    try {
        const response = await fetch(`${API_BASE}/fingerprints`);
        const result = await response.json();

        if (result.success) {
            displayStoredFingerprints(result.fingerprints);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error loading fingerprints:', error);
        alert('Error loading fingerprints: ' + error.message);
    }
}

function drawWaveform(audioData) {
    const container = document.getElementById('waveformContainer');
    container.innerHTML = '';

    waveformCanvas = document.createElement('canvas');
    waveformCanvas.width = container.clientWidth;
    waveformCanvas.height = container.clientHeight;
    waveformCanvas.className = 'waveform';
    container.appendChild(waveformCanvas);

    waveformContext = waveformCanvas.getContext('2d');

    const width = waveformCanvas.width;
    const height = waveformCanvas.height;
    const step = Math.ceil(audioData.length / width);

    waveformContext.fillStyle = '#f5f5f5';
    waveformContext.fillRect(0, 0, width, height);

    waveformContext.strokeStyle = '#667eea';
    waveformContext.lineWidth = 1;
    waveformContext.beginPath();

    for (let i = 0; i < width; i++) {
        let min = 1.0;
        let max = -1.0;

        for (let j = 0; j < step; j++) {
            const index = i * step + j;
            if (index < audioData.length) {
                const val = audioData[index];
                if (val < min) min = val;
                if (val > max) max = val;
            }
        }

        const yMin = (1 + min) * height / 2;
        const yMax = (1 + max) * height / 2;

        waveformContext.moveTo(i, yMin);
        waveformContext.lineTo(i, yMax);
    }

    waveformContext.stroke();

    manualRegions.forEach(region => {
        drawRegion(region);
    });

    waveformCanvas.addEventListener('click', handleWaveformClick);
}

function drawRegion(region) {
    if (!waveformContext || !currentAudioData) return;

    const duration = currentAudioData.length / audioProcessor.sampleRate;
    const x1 = (region.start / duration) * waveformCanvas.width;
    const x2 = (region.end / duration) * waveformCanvas.width;

    waveformContext.fillStyle = 'rgba(102, 126, 234, 0.3)';
    waveformContext.fillRect(x1, 0, x2 - x1, waveformCanvas.height);

    waveformContext.strokeStyle = '#667eea';
    waveformContext.lineWidth = 2;
    waveformContext.beginPath();
    waveformContext.moveTo(x1, 0);
    waveformContext.lineTo(x1, waveformCanvas.height);
    waveformContext.moveTo(x2, 0);
    waveformContext.lineTo(x2, waveformCanvas.height);
    waveformContext.stroke();
}

function handleWaveformClick(e) {
    const rect = waveformCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const duration = currentAudioData.length / audioProcessor.sampleRate;
    const time = (x / waveformCanvas.width) * duration;

    addRegion(time, Math.min(time + 10, duration));
}

function addRegion(start, end) {
    manualRegions.push({ start, end });
    updateRegionsList();
    if (currentAudioData) {
        drawWaveform(currentAudioData);
    }
}

function updateRegionsList() {
    const regionsList = document.getElementById('regionsList');
    regionsList.innerHTML = '';

    if (manualRegions.length === 0) {
        regionsList.innerHTML = '<p class="no-data">No regions defined. Click on waveform or Add Region button.</p>';
        return;
    }

    manualRegions.forEach((region, index) => {
        const item = document.createElement('div');
        item.className = 'region-item';
        item.innerHTML = `
            <span>Region ${index + 1}: ${region.start.toFixed(2)}s - ${region.end.toFixed(2)}s</span>
            <button onclick="removeRegion(${index})">Remove</button>
        `;
        regionsList.appendChild(item);
    });
}

function removeRegion(index) {
    manualRegions.splice(index, 1);
    updateRegionsList();
    if (currentAudioData) {
        drawWaveform(currentAudioData);
    }
}

function displayFingerprintResult() {
    document.getElementById('fpSize').textContent = currentFingerprint.length;
    document.getElementById('segmentCount').textContent = currentSegments.length;
    document.getElementById('fingerprintResult').classList.remove('hidden');
    document.getElementById('storeStatus').innerHTML = '';
}

function displayVerificationResults(matches) {
    const matchesList = document.getElementById('matchesList');
    matchesList.innerHTML = '';

    if (matches.length === 0) {
        matchesList.innerHTML = '<div class="no-data">No matches found. The audio does not match any stored fingerprints.</div>';
    } else {
        matches.forEach(match => {
            const similarity = (match.fullMatch.similarity * 100).toFixed(2);
            const similarityClass = similarity >= 85 ? 'high' : similarity >= 60 ? 'medium' : 'low';

            const matchItem = document.createElement('div');
            matchItem.className = 'match-item';

            let segmentsHtml = '';
            if (match.segmentMatches && match.segmentMatches.length > 0) {
                segmentsHtml = '<div class="segment-matches"><h4>Segment Analysis:</h4>';
                match.segmentMatches.forEach(seg => {
                    const segClass = seg.matched ? 'matched' : '';
                    const segSimilarity = (seg.similarity * 100).toFixed(2);
                    segmentsHtml += `
                        <div class="segment-match ${segClass}">
                            <strong>Segment ${seg.segmentIndex + 1}:</strong>
                            ${seg.startTime.toFixed(2)}s - ${seg.endTime.toFixed(2)}s
                            | Similarity: ${segSimilarity}%
                            ${seg.matched ? ' ✓ MATCH' : ' ✗ No match'}
                        </div>
                    `;
                });
                segmentsHtml += '</div>';
            }

            matchItem.innerHTML = `
                <div class="match-header">
                    <div class="match-title">${match.filename}</div>
                    <div class="similarity-badge ${similarityClass}">${similarity}% Match</div>
                </div>
                <div class="match-details">
                    <p><strong>Stored:</strong> ${new Date(match.createdAt).toLocaleString()}</p>
                    <p><strong>Full Audio Match:</strong> ${(match.fullMatch.similarity * 100).toFixed(2)}%</p>
                    <p><strong>Verification:</strong> ${match.fullMatch.matched ? '✓ VERIFIED' : '✗ FAILED'}</p>
                </div>
                ${segmentsHtml}
            `;

            matchesList.appendChild(matchItem);
        });
    }

    document.getElementById('verifyResult').classList.remove('hidden');
}

function displayStoredFingerprints(fingerprints) {
    const storedList = document.getElementById('storedList');
    storedList.innerHTML = '';

    if (fingerprints.length === 0) {
        storedList.innerHTML = '<div class="no-data">No fingerprints stored yet.</div>';
        return;
    }

    fingerprints.forEach(fp => {
        const item = document.createElement('div');
        item.className = 'stored-item';

        const audioFileInfo = fp.hasAudioFile ?
            `<p><strong>Audio File:</strong> Stored (${formatFileSize(fp.audioFileSize || 0)})</p>` :
            '<p><strong>Audio File:</strong> Not stored</p>';

        const audioPlayer = fp.hasAudioFile && fp.audioFileId ?
            `<div class="stored-audio-player">
                <audio controls>
                    <source src="${API_BASE.replace('/api', '')}/api/audio/${fp.audioFileId}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            </div>` : '';

        const segmentDetails = fp.segments && fp.segments.length > 0 ?
            `<div class="segment-details">
                <strong>Segment Breakdown:</strong>
                <ul>
                    ${fp.segments.slice(0, 5).map((seg, idx) =>
                        `<li>Segment ${idx + 1}: ${seg.startTime.toFixed(2)}s - ${seg.endTime.toFixed(2)}s</li>`
                    ).join('')}
                    ${fp.segments.length > 5 ? `<li>... and ${fp.segments.length - 5} more segments</li>` : ''}
                </ul>
            </div>` : '';

        item.innerHTML = `
            <div class="stored-header">
                <div class="stored-info">
                    <h3>${fp.filename}</h3>
                    <div class="stored-metadata">
                        <p><strong>ID:</strong> ${fp._id}</p>
                        <p><strong>Created:</strong> ${new Date(fp.createdAt).toLocaleString()}</p>
                        <p><strong>Duration:</strong> ${fp.metadata.duration ? fp.metadata.duration.toFixed(2) + 's' : 'N/A'}</p>
                        <p><strong>Sample Rate:</strong> ${fp.metadata.sampleRate || 'N/A'} Hz</p>
                        <p><strong>Total Segments:</strong> ${fp.segments ? fp.segments.length : 0}</p>
                        <p><strong>Fingerprint Size:</strong> ${fp.fullFingerprint ? fp.fullFingerprint.length : 0} features</p>
                        ${audioFileInfo}
                        ${fp.metadata.fileType ? `<p><strong>File Type:</strong> ${fp.metadata.fileType}</p>` : ''}
                    </div>
                    ${segmentDetails}
                    ${audioPlayer}
                </div>
                <div class="stored-actions">
                    <button class="view-details-btn" onclick="viewFingerprintDetails('${fp._id}')">View Details</button>
                    <button class="delete-btn" onclick="deleteFingerprint('${fp._id}')">Delete</button>
                </div>
            </div>
        `;
        storedList.appendChild(item);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

async function viewFingerprintDetails(id) {
    try {
        const response = await fetch(`${API_BASE}/fingerprint/${id}`);
        const result = await response.json();

        if (result.success) {
            const fp = result.fingerprint;
            const details = `
Fingerprint Details
==================
Filename: ${fp.filename}
ID: ${fp._id}
Created: ${new Date(fp.createdAt).toLocaleString()}

Metadata:
- Duration: ${fp.metadata.duration ? fp.metadata.duration.toFixed(2) + 's' : 'N/A'}
- Sample Rate: ${fp.metadata.sampleRate || 'N/A'} Hz
- File Size: ${formatFileSize(fp.metadata.fileSize || 0)}
- File Type: ${fp.metadata.fileType || 'N/A'}

Fingerprint:
- Features: ${fp.fullFingerprint ? fp.fullFingerprint.length : 0}
- Segments: ${fp.segments ? fp.segments.length : 0}
- Has Audio File: ${fp.hasAudioFile ? 'Yes' : 'No'}

Fingerprint Vector (first 10 values):
${fp.fullFingerprint ? fp.fullFingerprint.slice(0, 10).map((v, i) => `  [${i}] ${v.toFixed(6)}`).join('\n') : 'N/A'}
${fp.fullFingerprint && fp.fullFingerprint.length > 10 ? `  ... and ${fp.fullFingerprint.length - 10} more values` : ''}
            `;
            alert(details);
        } else {
            alert('Error loading details: ' + result.error);
        }
    } catch (error) {
        console.error('Error viewing details:', error);
        alert('Error loading details: ' + error.message);
    }
}

async function deleteFingerprint(id) {
    if (!confirm('Are you sure you want to delete this fingerprint?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/fingerprint/${id}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            loadStoredFingerprints();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting fingerprint:', error);
        alert('Error deleting fingerprint: ' + error.message);
    }
}

function showProgress(elementId) {
    document.getElementById(elementId).classList.remove('hidden');
}

function hideProgress(elementId) {
    document.getElementById(elementId).classList.add('hidden');
}

function showStatus(elementId, message, type) {
    const statusElement = document.getElementById(elementId);
    statusElement.textContent = message;
    statusElement.className = `status-message ${type}`;
    statusElement.style.display = 'block';
}
