class AudioProcessor {
    constructor() {
        this.audioContext = null;
        this.currentBuffer = null;
        this.sampleRate = 22050;
    }

    async computeSHA256(audioData) {
        const buffer = new Float32Array(audioData).buffer;
        const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hashHex;
    }

    async loadAudioFile(file) {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        const arrayBuffer = await file.arrayBuffer();
        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

        const offlineContext = new OfflineAudioContext(
            1,
            audioBuffer.duration * this.sampleRate,
            this.sampleRate
        );

        const source = offlineContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(offlineContext.destination);
        source.start();

        const resampledBuffer = await offlineContext.startRendering();
        this.currentBuffer = resampledBuffer;

        return {
            duration: audioBuffer.duration,
            sampleRate: this.sampleRate,
            channelData: resampledBuffer.getChannelData(0)
        };
    }

    computeSpectrogram(audioData, fftSize = 2048, hopSize = 512) {
        const numFrames = Math.floor((audioData.length - fftSize) / hopSize) + 1;
        const spectrogram = [];

        for (let i = 0; i < numFrames; i++) {
            const offset = i * hopSize;
            const frame = audioData.slice(offset, offset + fftSize);

            const windowed = this.applyHannWindow(frame);
            const fft = this.fft(windowed);
            const magnitude = fft.map(c => Math.sqrt(c.real * c.real + c.imag * c.imag));

            spectrogram.push(magnitude.slice(0, fftSize / 2));
        }

        return spectrogram;
    }

    applyHannWindow(frame) {
        const windowed = new Float32Array(frame.length);
        for (let i = 0; i < frame.length; i++) {
            windowed[i] = frame[i] * (0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (frame.length - 1)));
        }
        return windowed;
    }

    fft(signal) {
        const n = signal.length;
        if (n === 1) {
            return [{ real: signal[0], imag: 0 }];
        }

        const even = new Float32Array(n / 2);
        const odd = new Float32Array(n / 2);

        for (let i = 0; i < n / 2; i++) {
            even[i] = signal[2 * i];
            odd[i] = signal[2 * i + 1];
        }

        const fftEven = this.fft(even);
        const fftOdd = this.fft(odd);

        const result = new Array(n);

        for (let k = 0; k < n / 2; k++) {
            const angle = -2 * Math.PI * k / n;
            const twiddle = {
                real: Math.cos(angle),
                imag: Math.sin(angle)
            };

            const t = {
                real: twiddle.real * fftOdd[k].real - twiddle.imag * fftOdd[k].imag,
                imag: twiddle.real * fftOdd[k].imag + twiddle.imag * fftOdd[k].real
            };

            result[k] = {
                real: fftEven[k].real + t.real,
                imag: fftEven[k].imag + t.imag
            };

            result[k + n / 2] = {
                real: fftEven[k].real - t.real,
                imag: fftEven[k].imag - t.imag
            };
        }

        return result;
    }

    computeMFCC(spectrogram, numCoeffs = 13) {
        const mfccs = [];

        for (let frame of spectrogram) {
            const melSpec = this.applyMelFilterbank(frame);
            const logMelSpec = melSpec.map(val => Math.log(val + 1e-10));
            const dct = this.dct(logMelSpec).slice(0, numCoeffs);
            mfccs.push(dct);
        }

        const mfccTranspose = this.transpose(mfccs);
        const mfccMean = mfccTranspose.map(coeff => this.mean(coeff));
        const mfccStd = mfccTranspose.map(coeff => this.std(coeff));

        return { mean: mfccMean, std: mfccStd };
    }

    applyMelFilterbank(spectrum, numFilters = 128) {
        const melFilters = new Array(numFilters).fill(0);
        const minMel = this.hzToMel(0);
        const maxMel = this.hzToMel(this.sampleRate / 2);

        const melPoints = [];
        for (let i = 0; i <= numFilters + 1; i++) {
            melPoints.push(minMel + (maxMel - minMel) * i / (numFilters + 1));
        }

        const hzPoints = melPoints.map(mel => this.melToHz(mel));
        const binPoints = hzPoints.map(hz => Math.floor(spectrum.length * hz / (this.sampleRate / 2)));

        for (let i = 0; i < numFilters; i++) {
            const left = binPoints[i];
            const center = binPoints[i + 1];
            const right = binPoints[i + 2];

            let sum = 0;
            for (let j = left; j < center; j++) {
                if (j < spectrum.length && center !== left) {
                    sum += spectrum[j] * (j - left) / (center - left);
                }
            }
            for (let j = center; j < right; j++) {
                if (j < spectrum.length && right !== center) {
                    sum += spectrum[j] * (right - j) / (right - center);
                }
            }
            melFilters[i] = sum;
        }

        return melFilters;
    }

    hzToMel(hz) {
        return 2595 * Math.log10(1 + hz / 700);
    }

    melToHz(mel) {
        return 700 * (Math.pow(10, mel / 2595) - 1);
    }

    dct(signal) {
        const n = signal.length;
        const result = new Array(n);

        for (let k = 0; k < n; k++) {
            let sum = 0;
            for (let i = 0; i < n; i++) {
                sum += signal[i] * Math.cos(Math.PI * k * (i + 0.5) / n);
            }
            result[k] = sum * Math.sqrt(2 / n);
        }

        return result;
    }

    generateFingerprint(audioData) {
        const spectrogram = this.computeSpectrogram(audioData);
        const mfcc = this.computeMFCC(spectrogram);

        const spectralCentroids = spectrogram.map(frame => {
            let sum = 0;
            let weightedSum = 0;
            for (let i = 0; i < frame.length; i++) {
                sum += frame[i];
                weightedSum += i * frame[i];
            }
            return sum > 0 ? weightedSum / sum : 0;
        });

        const centroidMean = this.mean(spectralCentroids);
        const centroidStd = this.std(spectralCentroids);

        const spectralRolloffs = spectrogram.map(frame => {
            const total = frame.reduce((a, b) => a + b, 0);
            let cumSum = 0;
            for (let i = 0; i < frame.length; i++) {
                cumSum += frame[i];
                if (cumSum >= 0.85 * total) {
                    return i;
                }
            }
            return frame.length - 1;
        });

        const rolloffMean = this.mean(spectralRolloffs);
        const rolloffStd = this.std(spectralRolloffs);

        let zeroCrossings = 0;
        for (let i = 1; i < audioData.length; i++) {
            if ((audioData[i] >= 0 && audioData[i - 1] < 0) ||
                (audioData[i] < 0 && audioData[i - 1] >= 0)) {
                zeroCrossings++;
            }
        }
        const zcr = zeroCrossings / audioData.length;

        const energy = audioData.reduce((sum, val) => sum + val * val, 0) / audioData.length;

        const fingerprint = [
            ...mfcc.mean,
            ...mfcc.std,
            centroidMean,
            centroidStd,
            rolloffMean,
            rolloffStd,
            zcr,
            energy
        ];

        const maxAbs = Math.max(...fingerprint.map(Math.abs));
        return fingerprint.map(val => val / (maxAbs + 1e-10));
    }

    async generateSegments(audioData, segmentDuration = 5.0) {
        const samplesPerSegment = Math.floor(segmentDuration * this.sampleRate);
        const segments = [];

        for (let i = 0; i < audioData.length; i += samplesPerSegment) {
            const segmentData = audioData.slice(i, i + samplesPerSegment);

            if (segmentData.length < samplesPerSegment * 0.3) {
                continue;
            }

            const fingerprint = this.generateFingerprint(segmentData);
            const cryptoHash = await this.computeSHA256(segmentData);

            segments.push({
                startTime: i / this.sampleRate,
                endTime: Math.min((i + samplesPerSegment) / this.sampleRate, audioData.length / this.sampleRate),
                fingerprint: fingerprint,
                cryptoHash: cryptoHash,
                duration: segmentData.length / this.sampleRate
            });
        }

        return segments;
    }

    async generateCustomSegment(audioData, startTime, endTime) {
        const startSample = Math.floor(startTime * this.sampleRate);
        const endSample = Math.floor(endTime * this.sampleRate);

        const segmentData = audioData.slice(startSample, endSample);

        if (segmentData.length === 0) {
            return null;
        }

        const fingerprint = this.generateFingerprint(segmentData);
        const cryptoHash = await this.computeSHA256(segmentData);

        return {
            startTime,
            endTime,
            fingerprint,
            cryptoHash: cryptoHash,
            duration: segmentData.length / this.sampleRate
        };
    }

    transpose(matrix) {
        return matrix[0].map((_, i) => matrix.map(row => row[i]));
    }

    mean(arr) {
        return arr.reduce((a, b) => a + b, 0) / arr.length;
    }

    std(arr) {
        const m = this.mean(arr);
        const variance = arr.reduce((sum, val) => sum + Math.pow(val - m, 2), 0) / arr.length;
        return Math.sqrt(variance);
    }
}
