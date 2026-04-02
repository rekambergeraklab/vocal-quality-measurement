import sys
import numpy as np
import sounddevice as sd
import scipy.fftpack
import pyqtgraph as pg
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                             QLabel, QProgressBar, QWidget, QHBoxLayout,
                             QFrame, QComboBox, QMessageBox, QPushButton)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# --- macOS OPTIMIZED CONFIGURATION ---
AMBER = "#FFB000"
DARK_BG = "#0B0C10"
PANEL_BG = "#1F2833"
TEXT_MUTED = "#8892B0"
TEXT_LIGHT = "#E0E6ED"
FS = 44100  # Changed to 44.1kHz as it is the most stable default for many Mac setups
BLOCK_SIZE = 4096 # Smaller block size for lower latency on CoreAudio
GUI_SPEED = 30 # Slightly faster refresh for Pro Retina displays

def get_note_details(freq):
    if freq < 40: return "--", 0
    h = 12 * np.log2(freq / 440.0)
    n = int(round(h))
    offset = int((h - n) * 100)
    notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
    return f"{notes[n % 12]}{(n + 69 + 9) // 12 - 1}", offset

class AudioProcessor(QThread):
    update_signal = pyqtSignal(float, float, np.ndarray, float, float, int)

    def __init__(self):
        super().__init__()
        self.pitch_history = []
        self.smoothed_vib = 0.0
        self.alpha = 0.15
        self.device_id = None
        self.active = True

    def stop_engine(self):
        self.active = False
        self.wait()

    def run(self):
        self.active = True
        def callback(indata, frames, time_info, status):
            if status:
                print(f"CoreAudio Status: {status}") # Helpful for debugging Mac buffer overflows
            if not self.active: raise sd.CallbackStop()

            audio_data = indata[:, 0]
            rms = np.sqrt(np.mean(audio_data**2))
            windowed = audio_data * np.hanning(len(audio_data))
            fft_mag = np.abs(scipy.fftpack.fft(windowed))[:len(audio_data)//2]
            freqs = scipy.fftpack.fftfreq(len(audio_data), 1/FS)[:len(audio_data)//2]
            current_f0, vibrato_rate, cents = 0.0, 0.0, 0

            if rms > 0.003:
                hps = np.copy(fft_mag)
                for i in range(2, 5):
                    ds = hps[::i]
                    hps[:len(ds)] *= ds
                peak_idx = np.argmax(hps[20:]) + 20
                current_f0 = freqs[peak_idx]
                if 60 < current_f0 < 1200:
                    _, cents = get_note_details(current_f0)
                    self.pitch_history.append(current_f0)
                    if len(self.pitch_history) > 25:
                        self.pitch_history.pop(0)
                        p_array = np.array(self.pitch_history)
                        raw_vib = (len(np.where(np.diff(np.sign(p_array - np.mean(p_array))))[0]) / 2.0) * (FS / BLOCK_SIZE)
                        self.smoothed_vib = (self.alpha * raw_vib) + ((1 - self.alpha) * self.smoothed_vib)
                        vibrato_rate = self.smoothed_vib

            spr = -40.0
            if rms > 0.002:
                low_idx = np.where((freqs >= 100) & (freqs <= 900))
                high_idx = np.where((freqs >= 2000) & (freqs <= 4000))
                if len(low_idx[0]) > 0 and len(high_idx[0]) > 0:
                    spr = (20 * np.log10(np.max(fft_mag[high_idx]) / (np.max(fft_mag[low_idx]) + 1e-9))) + 10.0

            self.update_signal.emit(float(spr), float(rms), fft_mag, float(vibrato_rate), float(current_f0), int(cents))

        try:
            # Added Mac-specific InputStream arguments
            with sd.InputStream(device=self.device_id,
                                channels=1,
                                samplerate=FS,
                                blocksize=BLOCK_SIZE,
                                latency='low',
                                clip_off=True,
                                callback=callback):
                while self.active: self.msleep(50)
        except Exception as e:
            print(f"CoreAudio/Stream Error: {e}")

class VocalMasterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # Ensure the app uses the Mac system font stack
        self.setWindowTitle("Vocal Quality Measurement - RBLAB Mac Edition")
        self.setMinimumSize(1350, 900)
        self.setStyleSheet(f"background-color: {DARK_BG}; font-family: '-apple-system', 'Helvetica Neue', Arial, sans-serif;")

        # ... [Rest of the GUI implementation from original file remains compatible] ...
        # [Note: Implementation of init_ui, sync_stats_ui, start_stats_capture, etc.
        # should be copied exactly from the previous professional version]
