import numpy as np
from scipy import signal
from scipy.fftpack import dct

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
        return np.abs(spectrogram)

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
        chroma_bins = 12
        chroma = np.zeros((chroma_bins, spectrogram.shape[1]))

        for i, freq in enumerate(frequencies):
            if freq > 0:
                note = int(np.round(12 * np.log2(freq / 440.0))) % 12
                chroma[note] += spectrogram[i]

        return chroma

    def generate_fingerprint(self, audio_data):
        if len(audio_data) == 0:
            return []

        spectrogram = self.compute_spectrogram(audio_data)

        mfcc = self.compute_mfcc(spectrogram, n_mfcc=13)
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)

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

        zcr = np.mean(np.abs(np.diff(np.sign(audio_data)))) / 2

        energy = np.sum(audio_data ** 2) / len(audio_data)

        fingerprint = np.concatenate([
            mfcc_mean,
            mfcc_std,
            [centroid_mean, centroid_std],
            [rolloff_mean, rolloff_std],
            [zcr, energy]
        ])

        fingerprint = fingerprint / (np.max(np.abs(fingerprint)) + 1e-10)

        return fingerprint.tolist()

    def generate_segments(self, audio_data, segment_duration=10.0):
        samples_per_segment = int(segment_duration * self.sample_rate)
        segments = []

        for i in range(0, len(audio_data), samples_per_segment):
            segment_data = audio_data[i:i + samples_per_segment]

            if len(segment_data) < samples_per_segment * 0.5:
                continue

            fingerprint = self.generate_fingerprint(segment_data)

            segments.append({
                'startTime': i / self.sample_rate,
                'endTime': min((i + samples_per_segment) / self.sample_rate, len(audio_data) / self.sample_rate),
                'fingerprint': fingerprint
            })

        return segments

    def generate_custom_segment(self, audio_data, start_time, end_time):
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)

        segment_data = audio_data[start_sample:end_sample]

        if len(segment_data) == 0:
            return None

        fingerprint = self.generate_fingerprint(segment_data)

        return {
            'startTime': start_time,
            'endTime': end_time,
            'fingerprint': fingerprint
        }
