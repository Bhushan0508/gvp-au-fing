import numpy as np
from scipy import signal
from scipy.fftpack import dct
import hashlib
import blake3
import acoustid
import tempfile
import soundfile as sf
import os

class AudioFingerprinter:
    def __init__(self, sample_rate=22050, n_fft=2048, hop_length=512, n_mels=128):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels

    def compute_spectrogram(self, audio_data):
        frequencies, times, spectrogram = signal.spectrogram(
            audio_data,
            fs=self.sample_rate,
            window='hann',
            nperseg=self.n_fft,
            noverlap=self.n_fft - self.hop_length,
            scaling='spectrum'
        )
        return frequencies, np.abs(spectrogram)

    def mel_filterbank(self, n_filters, fft_bins):
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)

        def mel_to_hz(mel):
            return 700 * (10 ** (mel / 2595) - 1)

        min_mel = hz_to_mel(0)
        max_mel = hz_to_mel(self.sample_rate / 2)

        mel_points = np.linspace(min_mel, max_mel, n_filters + 2)
        hz_points = mel_to_hz(mel_points)
        bin_points = np.floor((self.n_fft + 1) * hz_points / self.sample_rate).astype(int)

        filterbank = np.zeros((n_filters, fft_bins))

        for i in range(1, n_filters + 1):
            left = bin_points[i - 1]
            center = bin_points[i]
            right = bin_points[i + 1]

            for j in range(left, center):
                if center != left:
                    filterbank[i - 1, j] = (j - left) / (center - left)

            for j in range(center, right):
                if right != center:
                    filterbank[i - 1, j] = (right - j) / (right - center)

        return filterbank

    def compute_mfcc(self, spectrogram, n_mfcc=20):
        mel_fb = self.mel_filterbank(self.n_mels, spectrogram.shape[0])
        mel_spec = np.dot(mel_fb, spectrogram)
        mel_spec = np.where(mel_spec == 0, np.finfo(float).eps, mel_spec)
        log_mel_spec = np.log(mel_spec)
        mfcc = dct(log_mel_spec, axis=0, norm='ortho')[:n_mfcc]

        return mfcc

    def compute_chroma(self, spectrogram, frequencies):
        """Compute chroma features (12 pitch classes) for melody/voice detection"""
        chroma_bins = 12
        chroma = np.zeros((chroma_bins, spectrogram.shape[1]))

        for i, freq in enumerate(frequencies):
            if freq > 0:
                note = int(np.round(12 * np.log2(freq / 440.0))) % 12
                chroma[note] += spectrogram[i]

        chroma = chroma / (np.sum(chroma, axis=0, keepdims=True) + 1e-10)
        return chroma

    def compute_spectral_contrast(self, spectrogram, frequencies, n_bands=6):
        """Compute spectral contrast to detect frequency manipulation"""
        freq_bands = np.logspace(np.log10(200), np.log10(self.sample_rate / 2), n_bands + 1)
        contrast = np.zeros((n_bands, spectrogram.shape[1]))

        for i in range(n_bands):
            lower_idx = np.searchsorted(frequencies, freq_bands[i])
            upper_idx = np.searchsorted(frequencies, freq_bands[i + 1])

            if upper_idx > lower_idx:
                band_spec = spectrogram[lower_idx:upper_idx, :]
                peak = np.percentile(band_spec, 90, axis=0)
                valley = np.percentile(band_spec, 10, axis=0)
                contrast[i] = peak - valley

        return contrast

    def compute_harmonic_ratio(self, audio_data):
        """Compute harmonic-to-noise ratio to detect noise injection"""
        frame_length = 2048
        hop_length = 512
        num_frames = (len(audio_data) - frame_length) // hop_length + 1

        hnr_values = []

        for i in range(num_frames):
            start = i * hop_length
            end = start + frame_length
            frame = audio_data[start:end]

            autocorr = np.correlate(frame, frame, mode='full')
            autocorr = autocorr[len(autocorr) // 2:]

            if len(autocorr) > 1:
                peaks = signal.find_peaks(autocorr)[0]
                if len(peaks) > 0:
                    max_peak = np.max(autocorr[peaks])
                    noise = np.abs(np.mean(autocorr) - max_peak)  # Use absolute value
                    hnr = max_peak / (noise + 1e-10)
                    # Ensure hnr is positive before log
                    hnr_values.append(np.log10(np.abs(hnr) + 1))
                else:
                    hnr_values.append(0)

        result = np.mean(hnr_values) if hnr_values else 0
        # Handle NaN/inf cases
        return 0 if np.isnan(result) or np.isinf(result) else result

    def compute_temporal_envelope(self, audio_data):
        """Compute temporal envelope to detect speed/pitch changes"""
        frame_length = 2048
        hop_length = 512
        envelope = []

        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i:i + frame_length]
            envelope.append(np.sqrt(np.mean(frame ** 2)))

        envelope = np.array(envelope)

        # Calculate attack rate safely
        above_mean = envelope[envelope > np.mean(envelope)]
        if len(above_mean) > 1:
            attack_rate = np.mean(np.diff(above_mean))
        else:
            attack_rate = 0

        # Handle NaN/inf cases
        attack_rate = 0 if np.isnan(attack_rate) or np.isinf(attack_rate) else attack_rate

        return {
            'mean': np.mean(envelope),
            'std': np.std(envelope),
            'max': np.max(envelope),
            'attack_rate': attack_rate
        }

    def compute_cryptographic_hash(self, audio_data):
        """Compute SHA-256 hash for exact content verification"""
        audio_bytes = audio_data.tobytes()
        return hashlib.sha256(audio_bytes).hexdigest()

    def compute_blake3_hash(self, audio_data):
        """Compute BLAKE3 hash for exact content verification (faster than SHA-256)"""
        audio_bytes = audio_data.tobytes()
        return blake3.blake3(audio_bytes).hexdigest()

    def compute_chromaprint(self, audio_data):
        """
        Compute Chromaprint fingerprint using AcoustID
        Chromaprint is industry-standard for audio identification
        """
        try:
            # Create temporary WAV file for Chromaprint
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                # Write audio data to temporary WAV file
                sf.write(tmp_path, audio_data, self.sample_rate)

            # Compute Chromaprint fingerprint
            duration, fingerprint = acoustid.fingerprint_file(tmp_path)

            # Clean up temporary file
            os.unlink(tmp_path)

            return {
                'fingerprint': fingerprint,
                'duration': duration,
                'algorithm': 'chromaprint'
            }
        except Exception as e:
            print(f"Chromaprint error: {e}")
            return None

    def generate_fingerprint(self, audio_data):
        """Generate comprehensive perceptual fingerprint"""
        if len(audio_data) == 0:
            return []

        frequencies, spectrogram = self.compute_spectrogram(audio_data)

        # MFCC features
        mfcc = self.compute_mfcc(spectrogram, n_mfcc=13)
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)
        mfcc_delta = np.mean(np.diff(mfcc, axis=1), axis=1)

        # Chroma features (voice/melody)
        chroma = self.compute_chroma(spectrogram, frequencies)
        chroma_mean = np.mean(chroma, axis=1)
        chroma_std = np.std(chroma, axis=1)

        # Spectral features
        spectral_centroid = np.sum(
            np.arange(spectrogram.shape[0])[:, np.newaxis] * spectrogram,
            axis=0
        ) / (np.sum(spectrogram, axis=0) + 1e-10)
        centroid_mean = np.mean(spectral_centroid)
        centroid_std = np.std(spectral_centroid)

        spectral_rolloff = np.array([
            np.where(np.cumsum(spectrogram[:, i]) >= 0.85 * np.sum(spectrogram[:, i]))[0][0]
            if np.sum(spectrogram[:, i]) > 0 else 0
            for i in range(spectrogram.shape[1])
        ])
        rolloff_mean = np.mean(spectral_rolloff)
        rolloff_std = np.std(spectral_rolloff)

        # Spectral contrast
        contrast = self.compute_spectral_contrast(spectrogram, frequencies)
        contrast_mean = np.mean(contrast, axis=1)
        contrast_std = np.std(contrast, axis=1)

        # Temporal features
        zcr = np.mean(np.abs(np.diff(np.sign(audio_data)))) / 2
        energy = np.sum(audio_data ** 2) / len(audio_data)

        envelope = self.compute_temporal_envelope(audio_data)

        # Harmonic features
        hnr = self.compute_harmonic_ratio(audio_data)

        # Combine all features
        fingerprint = np.concatenate([
            mfcc_mean,           # 13 features
            mfcc_std,            # 13 features
            mfcc_delta,          # 13 features
            chroma_mean,         # 12 features
            chroma_std,          # 12 features
            [centroid_mean, centroid_std],  # 2 features
            [rolloff_mean, rolloff_std],    # 2 features
            contrast_mean,       # 6 features
            contrast_std,        # 6 features
            [zcr, energy],       # 2 features
            [envelope['mean'], envelope['std'], envelope['max'], envelope['attack_rate']], # 4 features
            [hnr]                # 1 feature
        ])

        # Normalize
        fingerprint = fingerprint / (np.max(np.abs(fingerprint)) + 1e-10)

        return fingerprint.tolist()

    def generate_segments(self, audio_data, segment_duration=5.0, include_chromaprint=True):
        """Generate segments with perceptual, cryptographic, BLAKE3, and Chromaprint fingerprints"""
        samples_per_segment = int(segment_duration * self.sample_rate)
        segments = []

        for i in range(0, len(audio_data), samples_per_segment):
            segment_data = audio_data[i:i + samples_per_segment]

            if len(segment_data) < samples_per_segment * 0.3:
                continue

            fingerprint = self.generate_fingerprint(segment_data)
            crypto_hash = self.compute_cryptographic_hash(segment_data)
            blake3_hash = self.compute_blake3_hash(segment_data)

            segment = {
                'startTime': i / self.sample_rate,
                'endTime': min((i + samples_per_segment) / self.sample_rate, len(audio_data) / self.sample_rate),
                'fingerprint': fingerprint,
                'cryptoHash': crypto_hash,
                'blake3Hash': blake3_hash,
                'duration': len(segment_data) / self.sample_rate
            }

            # Add Chromaprint if requested
            if include_chromaprint:
                chromaprint_result = self.compute_chromaprint(segment_data)
                if chromaprint_result:
                    segment['chromaprint'] = chromaprint_result['fingerprint']
                    segment['chromaprintDuration'] = chromaprint_result['duration']

            segments.append(segment)

        return segments

    def generate_custom_segment(self, audio_data, start_time, end_time, include_chromaprint=True):
        """Generate custom segment fingerprint with BLAKE3"""
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)

        segment_data = audio_data[start_sample:end_sample]

        if len(segment_data) == 0:
            return None

        fingerprint = self.generate_fingerprint(segment_data)
        crypto_hash = self.compute_cryptographic_hash(segment_data)
        blake3_hash = self.compute_blake3_hash(segment_data)

        segment = {
            'startTime': start_time,
            'endTime': end_time,
            'fingerprint': fingerprint,
            'cryptoHash': crypto_hash,
            'blake3Hash': blake3_hash,
            'duration': len(segment_data) / self.sample_rate
        }

        # Add Chromaprint if requested
        if include_chromaprint:
            chromaprint_result = self.compute_chromaprint(segment_data)
            if chromaprint_result:
                segment['chromaprint'] = chromaprint_result['fingerprint']
                segment['chromaprintDuration'] = chromaprint_result['duration']

        return segment

    def generate_full_file_fingerprint(self, audio_data, include_chromaprint=True):
        """Generate fingerprint for the entire file without segmentation (includes BLAKE3)"""
        if len(audio_data) == 0:
            return None

        fingerprint = self.generate_fingerprint(audio_data)
        crypto_hash = self.compute_cryptographic_hash(audio_data)
        blake3_hash = self.compute_blake3_hash(audio_data)
        duration = len(audio_data) / self.sample_rate

        full_file = {
            'startTime': 0,
            'endTime': duration,
            'fingerprint': fingerprint,
            'cryptoHash': crypto_hash,
            'blake3Hash': blake3_hash,
            'duration': duration
        }

        # Add Chromaprint if requested
        if include_chromaprint:
            chromaprint_result = self.compute_chromaprint(audio_data)
            if chromaprint_result:
                full_file['chromaprint'] = chromaprint_result['fingerprint']
                full_file['chromaprintDuration'] = chromaprint_result['duration']

        return full_file
