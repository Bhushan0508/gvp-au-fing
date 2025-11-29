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

            if (segmentMode === 'none') {
                // No segmentation - only full file fingerprint
                currentSegments = [];
            } else if (segmentMode === 'auto') {
                const chunkDuration = parseFloat(document.getElementById('chunkDuration').value);
                currentSegments = await audioProcessor.generateSegments(currentAudioData, chunkDuration);
            } else {
                const segmentPromises = manualRegions.map(region => {
                    return audioProcessor.generateCustomSegment(
                        currentAudioData,
                        region.start,
                        region.end
                    );
                });
                currentSegments = (await Promise.all(segmentPromises)).filter(s => s !== null);
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

            // Store traditional fingerprint
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
                // Generate and store AI vector fingerprint
                try {
                    const vectorResponse = await fetch(`${API_BASE}/fingerprint/vector/generate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            audioData: audioDataBase64
                        })
                    });

                    const vectorResult = await vectorResponse.json();

                    if (vectorResult.success && vectorResult.vectorSegments) {
                        // Store vector embeddings in Milvus
                        const storeVectorResponse = await fetch(`${API_BASE}/fingerprint/vector/store`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                fingerprintId: result.id,
                                vectorSegments: vectorResult.vectorSegments
                            })
                        });

                        const storeVectorResult = await storeVectorResponse.json();

                        if (storeVectorResult.success) {
                            showStatus('storeStatus', 'Fingerprint, audio file, and AI vector embeddings stored successfully!', 'success');
                        } else {
                            showStatus('storeStatus', 'Fingerprint stored, but AI vector storage failed: ' + storeVectorResult.error, 'warning');
                        }
                    } else {
                        showStatus('storeStatus', 'Fingerprint stored, but AI vector generation failed', 'warning');
                    }
                } catch (vectorError) {
                    console.error('Error with AI vector fingerprinting:', vectorError);
                    showStatus('storeStatus', 'Fingerprint stored, but AI vector processing failed: ' + vectorError.message, 'warning');
                }
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
    const verifySegmentModeRadios = document.querySelectorAll('input[name="verifySegmentMode"]');

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

    verifySegmentModeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            const autoOptions = document.querySelectorAll('.auto-chunk-options')[1]; // Second one for verify tab

            if (e.target.value === 'auto') {
                autoOptions.style.display = 'block';
            } else {
                autoOptions.style.display = 'none';
            }
        });
    });

    verifyBtn.addEventListener('click', async () => {
        if (!currentAudioData) {
            alert('Please load an audio file to verify');
            return;
        }

        // Get selected verification methods
        const useCryptographic = document.getElementById('useCryptographic').checked;
        const useBlake3 = document.getElementById('useBlake3').checked;
        const usePerceptual = document.getElementById('usePerceptual').checked;
        const useChromaprint = document.getElementById('useChromaprint').checked;

        // Validate at least one method is selected
        if (!useCryptographic && !useBlake3 && !usePerceptual && !useChromaprint) {
            alert('Please select at least one verification method');
            return;
        }

        try {
            showProgress('verifyProgress');

            const fingerprint = audioProcessor.generateFingerprint(currentAudioData);

            // Handle segmentation based on selected mode
            const segmentMode = document.querySelector('input[name="verifySegmentMode"]:checked').value;
            let segments = [];

            if (segmentMode === 'none') {
                // No segmentation - only full file fingerprint
                segments = [];
            } else if (segmentMode === 'auto') {
                const chunkDuration = parseFloat(document.getElementById('verifyChunkDuration').value);
                segments = await audioProcessor.generateSegments(currentAudioData, chunkDuration);
            }

            // Perform traditional fingerprint verification
            const response = await fetch(`${API_BASE}/fingerprint/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fullFingerprint: fingerprint,
                    segments: segments,
                    verificationMethods: {
                        cryptographic: useCryptographic,
                        blake3: useBlake3,
                        perceptual: usePerceptual,
                        chromaprint: useChromaprint
                    }
                })
            });

            const result = await response.json();

            // Generate AI vector fingerprint and verify against stored matches
            if (result.success && result.matches.length > 0 && currentAudioFile) {
                try {
                    const reader = new FileReader();
                    const audioDataBase64 = await new Promise((resolve, reject) => {
                        reader.onload = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(currentAudioFile);
                    });

                    // Generate vector embeddings for the query audio
                    const vectorResponse = await fetch(`${API_BASE}/fingerprint/vector/generate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            audioData: audioDataBase64
                        })
                    });

                    const vectorResult = await vectorResponse.json();

                    if (vectorResult.success && vectorResult.vectorSegments) {
                        // Verify against each match
                        for (let match of result.matches) {
                            try {
                                const verifyResponse = await fetch(`${API_BASE}/fingerprint/vector/verify`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        vectorSegments: vectorResult.vectorSegments,
                                        fingerprintId: match.id
                                    })
                                });

                                const verifyResult = await verifyResponse.json();

                                if (verifyResult.success) {
                                    match.vectorVerification = verifyResult.verification;
                                }
                            } catch (vectorVerifyError) {
                                console.error('Error verifying AI vector for match:', vectorVerifyError);
                            }
                        }
                    }
                } catch (vectorError) {
                    console.error('Error with AI vector verification:', vectorError);
                }
            }

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
    const segmentText = currentSegments.length === 0 ? 'None (Full file only)' : currentSegments.length;
    document.getElementById('segmentCount').textContent = segmentText;
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
            const similarityClass = similarity >= 95 ? 'high' : similarity >= 85 ? 'medium' : 'low';

            const matchItem = document.createElement('div');
            matchItem.className = 'match-item';

            // Calculate method statistics
            let cryptoCount = 0, cryptoTotal = 0;
            let blake3Count = 0, blake3Total = 0;
            let perceptualCount = 0, perceptualTotal = 0;
            let chromaprintCount = 0, chromaprintTotal = 0;

            if (match.segmentMatches) {
                match.segmentMatches.forEach(seg => {
                    // Count cryptographic matches
                    if (seg.cryptoMatched !== null && seg.cryptoMatched !== undefined) {
                        cryptoTotal++;
                        if (seg.cryptoMatched === true) cryptoCount++;
                    }
                    // Count BLAKE3 matches
                    if (seg.blake3Matched !== null && seg.blake3Matched !== undefined) {
                        blake3Total++;
                        if (seg.blake3Matched === true) blake3Count++;
                    }
                    // Count perceptual matches
                    if (seg.perceptualMatch !== undefined) {
                        perceptualTotal++;
                        if (seg.perceptualMatch) perceptualCount++;
                    }
                    // Count chromaprint matches
                    if (seg.chromaprintMatched !== null && seg.chromaprintMatched !== undefined) {
                        chromaprintTotal++;
                        if (seg.chromaprintMatched) chromaprintCount++;
                    }
                });
            }

            // Method breakdown HTML
            let methodsBreakdown = '';
            if (cryptoTotal > 0 || blake3Total > 0 || perceptualTotal > 0 || chromaprintTotal > 0) {
                methodsBreakdown = '<div class="methods-breakdown"><h4>🔍 Verification Methods Results:</h4>';

                if (cryptoTotal > 0) {
                    const cryptoPct = ((cryptoCount / cryptoTotal) * 100).toFixed(1);
                    const cryptoStatus = cryptoCount === cryptoTotal ? '✓' : cryptoCount > 0 ? '⚠' : '✗';
                    const cryptoClass = cryptoCount === cryptoTotal ? 'method-pass' : cryptoCount > 0 ? 'method-partial' : 'method-fail';
                    methodsBreakdown += `
                        <div class="method-result ${cryptoClass}">
                            <strong>${cryptoStatus} Cryptographic (SHA-256):</strong>
                            ${cryptoCount}/${cryptoTotal} segments (${cryptoPct}%)
                            <span class="method-note">Exact byte-level matching</span>
                        </div>
                    `;
                }

                if (blake3Total > 0) {
                    const blake3Pct = ((blake3Count / blake3Total) * 100).toFixed(1);
                    const blake3Status = blake3Count === blake3Total ? '✓' : blake3Count > 0 ? '⚠' : '✗';
                    const blake3Class = blake3Count === blake3Total ? 'method-pass' : blake3Count > 0 ? 'method-partial' : 'method-fail';
                    methodsBreakdown += `
                        <div class="method-result ${blake3Class}">
                            <strong>${blake3Status} BLAKE3:</strong>
                            ${blake3Count}/${blake3Total} segments (${blake3Pct}%)
                            <span class="method-note">Faster cryptographic hash</span>
                        </div>
                    `;
                }

                if (perceptualTotal > 0) {
                    const perceptualPct = ((perceptualCount / perceptualTotal) * 100).toFixed(1);
                    const perceptualStatus = perceptualCount === perceptualTotal ? '✓' : perceptualCount > 0 ? '⚠' : '✗';
                    const perceptualClass = perceptualCount === perceptualTotal ? 'method-pass' : perceptualCount > 0 ? 'method-partial' : 'method-fail';
                    methodsBreakdown += `
                        <div class="method-result ${perceptualClass}">
                            <strong>${perceptualStatus} Perceptual (86 Features):</strong>
                            ${perceptualCount}/${perceptualTotal} segments (${perceptualPct}%)
                            <span class="method-note">Audio content analysis</span>
                        </div>
                    `;
                }

                if (chromaprintTotal > 0) {
                    const chromaprintPct = ((chromaprintCount / chromaprintTotal) * 100).toFixed(1);
                    const chromaprintStatus = chromaprintCount === chromaprintTotal ? '✓' : chromaprintCount > 0 ? '⚠' : '✗';
                    const chromaprintClass = chromaprintCount === chromaprintTotal ? 'method-pass' : chromaprintCount > 0 ? 'method-partial' : 'method-fail';
                    methodsBreakdown += `
                        <div class="method-result ${chromaprintClass}">
                            <strong>${chromaprintStatus} Chromaprint:</strong>
                            ${chromaprintCount}/${chromaprintTotal} segments (${chromaprintPct}%)
                            <span class="method-note">Industry-standard audio fingerprint</span>
                        </div>
                    `;
                }

                methodsBreakdown += '</div>';
            }

            // Prepare AI Vector Matching results separately
            let vectorMatchingSection = '';
            if (match.vectorVerification) {
                const vv = match.vectorVerification;
                const vectorPct = vv.match_percentage ? vv.match_percentage.toFixed(1) : 0;
                const vectorStatus = vv.matched ? '✓ VERIFIED' : vv.is_partial_match ? '⚠ PARTIAL MATCH' : '✗ NO MATCH';
                const vectorClass = vv.matched ? 'method-pass' : vv.is_partial_match ? 'method-partial' : 'method-fail';
                const matchType = vv.is_tampered ? '🚨 Tampered Audio Detected' : vv.is_partial_match ? '📋 Partial File Match' : '✓ Full Match';

                vectorMatchingSection = `
                    <div class="vector-matching-section">
                        <h4>🤖 AI Vector Matching (CLAP) Results:</h4>
                        <div class="vector-status ${vectorClass}">
                            <div class="vector-header">
                                <strong>${vectorStatus}</strong>
                                <span class="vector-match-type">${matchType}</span>
                            </div>
                            <div class="vector-stats">
                                <p><strong>Overall Match:</strong> ${vectorPct}%</p>
                                <p><strong>Matched Segments:</strong> ${vv.matched_segments}/${vv.total_segments}</p>
                                <p><strong>Method:</strong> Semantic audio embedding using CLAP (512-dimensional vectors)</p>
                                <p><strong>Technology:</strong> Deep learning-based similarity search with Milvus vector database</p>
                            </div>
                        </div>`;

                // Add detailed segment-by-segment results if available
                if (vv.segment_matches && vv.segment_matches.length > 0) {
                    vectorMatchingSection += `
                        <div class="vector-segment-details">
                            <h5>Segment-by-Segment CLAP Matches:</h5>
                            <ul class="vector-segments-list">`;

                    vv.segment_matches.forEach(seg => {
                        const similarity = (seg.similarity * 100).toFixed(1);
                        const simClass = seg.similarity >= 0.95 ? 'high' : seg.similarity >= 0.85 ? 'medium' : 'low';
                        vectorMatchingSection += `
                            <li class="vector-segment ${simClass}">
                                <strong>Query Segment ${seg.query_segment}:</strong> ${seg.query_time}
                                → <strong>Matched Segment ${seg.matched_segment}:</strong> ${seg.matched_time}
                                <span class="similarity-badge">${similarity}% similarity</span>
                            </li>`;
                    });

                    vectorMatchingSection += `
                            </ul>
                        </div>`;
                }

                vectorMatchingSection += `
                    </div>`;
            }

            // Verification Summary
            const vr = match.verificationResult || {};
            let verificationSummary = '';
            if (vr.totalSegments) {
                const validPct = ((vr.validSegments / vr.totalSegments) * 100).toFixed(1);
                const tamperedPct = ((vr.tamperedSegments / vr.totalSegments) * 100).toFixed(1);

                let verificationStatus = '';
                if (vr.tamperedSegments > 0) {
                    verificationStatus = `<span class="status-badge tampered">⚠ TAMPERED CONTENT DETECTED</span>`;
                } else if (vr.isPartialFile && vr.validSegments === vr.totalSegments) {
                    verificationStatus = `<span class="status-badge partial-valid">✓ PARTIAL FILE - AUTHENTIC</span>`;
                } else if (vr.validSegments === vr.totalSegments) {
                    verificationStatus = `<span class="status-badge verified">✓ FULLY VERIFIED - AUTHENTIC</span>`;
                }

                verificationSummary = `
                    <div class="verification-summary">
                        <h4>Verification Summary</h4>
                        ${verificationStatus}
                        <div class="verification-stats">
                            <p><strong>Total Segments:</strong> ${vr.totalSegments}</p>
                            <p><strong>Valid Segments:</strong> ${vr.validSegments} (${validPct}%)</p>
                            <p><strong>Tampered Segments:</strong> ${vr.tamperedSegments} (${tamperedPct}%)</p>
                            <p><strong>Average Similarity:</strong> ${(vr.avgSimilarity * 100).toFixed(2)}%</p>
                            ${vr.isPartialFile ? '<p><strong>Type:</strong> Partial Audio File</p>' : ''}
                            ${vr.isComplete ? '<p><strong>Type:</strong> Complete Audio File</p>' : ''}
                        </div>
                        ${methodsBreakdown}
                        ${vectorMatchingSection}
                    </div>
                `;
            }

            // Tampered Regions
            let tamperedRegionsHtml = '';
            if (vr.tamperedRegions && vr.tamperedRegions.length > 0) {
                tamperedRegionsHtml = '<div class="tampered-regions"><h4>⚠ Tampered Regions Detected:</h4><ul>';
                vr.tamperedRegions.forEach(region => {
                    tamperedRegionsHtml += `
                        <li class="tampered-region">
                            <strong>Time:</strong> ${region.startTime.toFixed(2)}s - ${region.endTime.toFixed(2)}s
                            | <strong>Similarity:</strong> ${(region.similarity * 100).toFixed(2)}%
                        </li>
                    `;
                });
                tamperedRegionsHtml += '</ul></div>';
            }

            // Valid Regions
            let validRegionsHtml = '';
            if (vr.validRegions && vr.validRegions.length > 0) {
                validRegionsHtml = '<div class="valid-regions"><h4>✓ Verified Regions:</h4><ul>';
                vr.validRegions.forEach(region => {
                    const exactMatch = region.exactMatch ? '(Exact Match)' : '(Perceptual Match)';
                    validRegionsHtml += `
                        <li class="valid-region">
                            <strong>Time:</strong> ${region.startTime.toFixed(2)}s - ${region.endTime.toFixed(2)}s ${exactMatch}
                        </li>
                    `;
                });
                validRegionsHtml += '</ul></div>';
            }

            // Detailed Segment Analysis with Summary Table
            let segmentsHtml = '';
            if (match.segmentMatches && match.segmentMatches.length > 0) {
                segmentsHtml = '<div class="segment-matches">';

                // Build a map: originalSegmentIndex -> array of input segments matching it
                const originalSegmentMap = new Map();
                const unmatchedInputSegments = [];

                // Find the maximum original segment index to know total original segments
                let maxOriginalSegIndex = -1;
                match.segmentMatches.forEach(seg => {
                    if (seg.storedSegmentIndex !== undefined) {
                        maxOriginalSegIndex = Math.max(maxOriginalSegIndex, seg.storedSegmentIndex);

                        if (!originalSegmentMap.has(seg.storedSegmentIndex)) {
                            originalSegmentMap.set(seg.storedSegmentIndex, []);
                        }
                        originalSegmentMap.get(seg.storedSegmentIndex).push(seg);
                    } else {
                        unmatchedInputSegments.push(seg);
                    }
                });

                // Add summary table showing all original segments
                segmentsHtml += `
                    <h4>📋 Segment Matching Summary:</h4>
                    <div class="segment-summary-table">
                        <table class="match-table">
                            <thead>
                                <tr>
                                    <th>Original Segment</th>
                                    <th>Original Time Range</th>
                                    <th>↔</th>
                                    <th>Input Segment(s)</th>
                                    <th>Input Time Range</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>`;

                // Iterate through all original segments
                for (let origIdx = 0; origIdx <= maxOriginalSegIndex; origIdx++) {
                    const matchingInputSegs = originalSegmentMap.get(origIdx);
                    const origStartTime = origIdx * 10;
                    const origEndTime = (origIdx + 1) * 10;

                    if (matchingInputSegs && matchingInputSegs.length > 0) {
                        // This original segment has matching input segments
                        matchingInputSegs.forEach((seg, idx) => {
                            const matchStatus = seg.cryptoMatched ? '✓ Exact' :
                                              seg.chromaprintMatched ? '✓ Chromaprint' :
                                              seg.matched ? '✓ Match' :
                                              seg.isTampered ? '✗ Tampered' : '✗ No Match';
                            const rowClass = seg.matched ? 'match-row' : seg.isTampered ? 'tamper-row' : 'nomatch-row';

                            if (idx === 0) {
                                // First input segment for this original - show original info
                                segmentsHtml += `
                                    <tr class="${rowClass}">
                                        <td rowspan="${matchingInputSegs.length}">Segment ${origIdx + 1}</td>
                                        <td rowspan="${matchingInputSegs.length}">${origStartTime.toFixed(2)}s - ${origEndTime.toFixed(2)}s</td>
                                        <td class="arrow-cell">←</td>
                                        <td>Segment ${seg.segmentIndex + 1}</td>
                                        <td>${seg.startTime.toFixed(2)}s - ${seg.endTime.toFixed(2)}s</td>
                                        <td class="status-cell">${matchStatus}</td>
                                    </tr>`;
                            } else {
                                // Additional input segments for same original
                                segmentsHtml += `
                                    <tr class="${rowClass}">
                                        <td class="arrow-cell">←</td>
                                        <td>Segment ${seg.segmentIndex + 1}</td>
                                        <td>${seg.startTime.toFixed(2)}s - ${seg.endTime.toFixed(2)}s</td>
                                        <td class="status-cell">${matchStatus}</td>
                                    </tr>`;
                            }
                        });
                    } else {
                        // This original segment has no matching input segments
                        segmentsHtml += `
                            <tr class="missing-original-row">
                                <td>Segment ${origIdx + 1}</td>
                                <td>${origStartTime.toFixed(2)}s - ${origEndTime.toFixed(2)}s</td>
                                <td class="arrow-cell">✗</td>
                                <td colspan="2" class="no-match-cell">Not present in input</td>
                                <td class="status-cell">⚠ Missing from Input</td>
                            </tr>`;
                    }
                }

                // Add unmatched input segments (segments in input that don't match any original)
                if (unmatchedInputSegments.length > 0) {
                    segmentsHtml += `
                        <tr class="section-header">
                            <td colspan="6"><strong>⚠ Additional Segments in Input (Not in Original)</strong></td>
                        </tr>`;

                    unmatchedInputSegments.forEach(seg => {
                        segmentsHtml += `
                            <tr class="unmatched-input-row">
                                <td colspan="2" class="no-match-cell">Not in original</td>
                                <td class="arrow-cell">✗</td>
                                <td>Segment ${seg.segmentIndex + 1}</td>
                                <td>${seg.startTime.toFixed(2)}s - ${seg.endTime.toFixed(2)}s</td>
                                <td class="status-cell">⚠ Extra Segment</td>
                            </tr>`;
                    });
                }

                segmentsHtml += `
                            </tbody>
                        </table>
                    </div>
                    <h4>🔍 Detailed Segment Analysis:</h4>`;

                // Detailed analysis cards
                match.segmentMatches.forEach(seg => {
                    let segClass = seg.matched ? 'matched' : '';
                    if (seg.isTampered) segClass = 'tampered';

                    const segSimilarity = (seg.similarity * 100).toFixed(2);
                    const cryptoStatus = seg.cryptoMatched ? '🔒 Exact' : '🔓 Modified';

                    // Chromaprint status
                    const chromaprintSimilarity = seg.chromaprintSimilarity ? (seg.chromaprintSimilarity * 100).toFixed(2) : 'N/A';
                    const chromaprintStatus = seg.chromaprintMatched ? '🎵 Match' : '🎵 No Match';
                    const hasChromaprint = seg.chromaprintSimilarity !== undefined;

                    // Stored segment info
                    const storedSegInfo = seg.storedSegmentIndex !== undefined && seg.storedStartTime !== undefined
                        ? `matches <strong>Original Segment ${seg.storedSegmentIndex + 1}</strong> (${seg.storedStartTime.toFixed(2)}s - ${seg.storedEndTime.toFixed(2)}s)`
                        : 'no match in original file';

                    segmentsHtml += `
                        <div class="segment-match ${segClass}">
                            <div class="segment-info">
                                <div class="input-segment">
                                    <strong>Input Segment ${seg.segmentIndex + 1}:</strong>
                                    ${seg.startTime.toFixed(2)}s - ${seg.endTime.toFixed(2)}s
                                </div>
                                <div class="segment-mapping">
                                    → ${storedSegInfo}
                                </div>
                            </div>
                            <div class="segment-metrics">
                                <span><strong>Perceptual:</strong> ${segSimilarity}%</span>
                                <span><strong>Cryptographic:</strong> ${cryptoStatus}</span>
                                ${hasChromaprint ? `<span><strong>Chromaprint:</strong> ${chromaprintSimilarity}% ${seg.chromaprintMatched ? '✓' : '✗'}</span>` : ''}
                            </div>
                            <div class="segment-status">
                                ${seg.cryptoMatched ? '✓ EXACT MATCH' :
                                  seg.chromaprintMatched ? '✓ CHROMAPRINT MATCH' :
                                  seg.matched ? '✓ PERCEPTUAL MATCH' :
                                  seg.isTampered ? '✗ TAMPERED' : '✗ NO MATCH'}
                            </div>
                        </div>
                    `;
                });
                segmentsHtml += '</div>';
            }

            matchItem.innerHTML = `
                <div class="match-header">
                    <div class="match-title">${match.filename}</div>
                    <div class="similarity-badge ${similarityClass}">${similarity}%</div>
                </div>
                <div class="match-details">
                    <p><strong>Stored:</strong> ${new Date(match.createdAt).toLocaleString()}</p>
                    <p><strong>Overall Similarity:</strong> ${similarity}%</p>
                </div>
                ${verificationSummary}
                ${tamperedRegionsHtml}
                ${validRegionsHtml}
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
