import sys
import numpy as np
import soundcard as sc
import scipy.fftpack
import pyqtgraph as pg
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                             QLabel, QProgressBar, QWidget, QHBoxLayout,
                             QFrame, QComboBox, QMessageBox, QPushButton)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# --- SYSTEM CONFIGURATION ---
AMBER = "#FFB000"
DARK_BG = "#0B0C10"
PANEL_BG = "#1F2833"
TEXT_MUTED = "#8892B0"
TEXT_LIGHT = "#E0E6ED"
FS = 48000
BLOCK_SIZE = 8192
GUI_SPEED = 20

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
        self.device_mic = None  # Soundcard device reference
        self.active = True

    def stop_engine(self):
        """Safely shuts down the audio engine, preventing Windows WASAPI deadlocks."""
        self.active = False
        # Wait up to 500ms for the thread to finish cleanly
        if not self.wait(500): 
            # If it's stuck because Windows audio is completely silent, force kill it
            self.terminate()
            self.wait()

    def run(self):
        self.active = True
        try:
            # Fallback to the default system speaker loopback if no device is selected
            if self.device_mic is None:
                mic = sc.get_microphone(sc.default_speaker().id, include_loopback=True)
            else:
                mic = self.device_mic

            # Open a blocking recorder loop perfectly suited for a QThread
            with mic.recorder(samplerate=FS, channels=1, blocksize=BLOCK_SIZE) as recorder:
                while self.active:
                    # Blocks until chunk is ready. If system audio is completely silent, 
                    # Windows WASAPI may pause sending data here.
                    audio_data = recorder.record(numframes=BLOCK_SIZE)[:, 0]
                    
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

        except Exception as e: 
            print(f"Stream Error: {e}")


class VocalMasterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vocal Quality Measurement - Windows Loopback Engine")
        self.setMinimumSize(1350, 900)
        self.setStyleSheet(f"background-color: {DARK_BG}; font-family: 'Segoe UI', Arial, sans-serif;")

        self.stats_cache = {
            'spr': [], 'cents': [], 'vib_rate': [], 'rms': [],
            'sonority_hits': 0, 'total_samples': 0, 'brightness': []
        }
        self.is_recording_stats = False
        self.start_time = 0

        self.target_spr, self.current_spr = -40.0, -40.0
        self.target_vib, self.target_pitch, self.target_cents = 0.0, 0.0, 0
        self.pitch_trace_data = np.zeros(400)
        self.current_mag = np.zeros(BLOCK_SIZE // 2)
        self.target_mag = np.zeros(BLOCK_SIZE // 2)

        self.processor = AudioProcessor()
        self.init_ui()
        self.processor.update_signal.connect(self.store_data)
        self.processor.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.smooth_render)
        self.timer.start(GUI_SPEED)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Main Root Layout
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(20, 20, 20, 10)
        root_layout.setSpacing(20)

        # Content Layout (Graphs + Side Panel)
        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout, 1)

        # --- LEFT PANEL (GRAPHS) ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)

        # Spectral Graph
        self.pw_spec = pg.PlotWidget(title="SPECTRAL CHARACTER ANALYSIS")
        self.pw_spec.setBackground(DARK_BG)
        self.pw_spec.getAxis('bottom').setPen(pg.mkPen(color=TEXT_MUTED))
        self.pw_spec.getAxis('left').setPen(pg.mkPen(color=TEXT_MUTED))
        self.pw_spec.setTitle("<span style='color: #8892B0; font-size: 11pt; font-weight: bold;'>SPECTRAL CHARACTER ANALYSIS</span>")

        self.spec_curve = self.pw_spec.plot(pen=pg.mkPen(AMBER, width=2.5))
        self.pw_spec.setXRange(0, 3500, padding=0); self.pw_spec.setYRange(0, 45)

        regions = [(0, 500, "PITCH"), (500, 1000, "VOWEL"), (1000, 2000, "ARTICULATION"), (2000, 3500, "RING")]
        for s, e, label in regions:
            region = pg.LinearRegionItem([s, e], movable=False, brush=pg.mkBrush(255, 176, 0, 10))
            self.pw_spec.addItem(region)
            text = pg.TextItem(html=f'<b style="color:{AMBER}; font-family:Monospace; font-size:9pt; opacity: 0.7;">{label}</b>', anchor=(0.5, 0))
            text.setPos((s + e) / 2, 43); self.pw_spec.addItem(text)

        left_panel.addWidget(self.pw_spec, 2)

        # Pitch Trace Graph
        self.pw_pitch = pg.PlotWidget(title="INTONATION TRACE (CENTS)")
        self.pw_pitch.setBackground(DARK_BG)
        self.pw_pitch.getAxis('bottom').setPen(pg.mkPen(color=TEXT_MUTED))
        self.pw_pitch.getAxis('left').setPen(pg.mkPen(color=TEXT_MUTED))
        self.pw_pitch.setTitle("<span style='color: #8892B0; font-size: 11pt; font-weight: bold;'>INTONATION TRACE (CENTS)</span>")

        self.pitch_curve = self.pw_pitch.plot(pen=pg.mkPen(AMBER, width=2))
        self.pw_pitch.setYRange(-50, 50)
        self.pw_pitch.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(TEXT_MUTED, style=Qt.DotLine)))
        left_panel.addWidget(self.pw_pitch, 1)

        content_layout.addLayout(left_panel, 4)

        # --- RIGHT PANEL (CONTROLS & METERS) ---
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)

        # Configuration Frame
        config_frame = QFrame()
        config_frame.setStyleSheet(f"background-color: {PANEL_BG}; border-radius: 10px;")
        config_lyt = QVBoxLayout(config_frame)
        config_lyt.setContentsMargins(15, 15, 15, 15)

        combo_style = f"""
            QComboBox {{
                color: {TEXT_LIGHT}; background-color: #2A3644;
                border: 1px solid #4A5B6D; border-radius: 5px;
                padding: 8px; font-weight: bold; font-size: 10pt;
            }}
            QComboBox::drop-down {{ border: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: #2A3644; color: {TEXT_LIGHT};
                selection-background-color: {AMBER}; selection-color: #000;
            }}
        """

        # --- DEVICE DISCOVERY ---
        config_lyt.addWidget(QLabel("SYSTEM / AUDIO INPUT", styleSheet=f"color:{TEXT_MUTED}; font-weight:bold; font-size:9pt;"), alignment=Qt.AlignCenter)
        self.device_box = QComboBox(); self.device_box.setStyleSheet(combo_style)
        
        # Include loopback explicitly grabs both microphones AND system outputs (Speakers, Headphones)
        self.mics = sc.all_microphones(include_loopback=True)
        for i, mic in enumerate(self.mics):
            # Highlight system outputs in the UI drop-down for clarity
            display_name = f"[SYSTEM] {mic.name}" if "Loopback" in str(mic.id) else mic.name
            self.device_box.addItem(display_name, i)

        self.device_box.currentIndexChanged.connect(self.change_device); config_lyt.addWidget(self.device_box)

        config_lyt.addWidget(QLabel("ENGINE MODE", styleSheet=f"color:{TEXT_MUTED}; font-weight:bold; font-size:9pt; margin-top:10px;"), alignment=Qt.AlignCenter)
        self.mode_box = QComboBox(); self.mode_box.addItems(["REAL-TIME MONITOR", "STATISTIC ANALYSIS"]); self.mode_box.setStyleSheet(combo_style)
        self.mode_box.currentTextChanged.connect(self.sync_stats_ui); config_lyt.addWidget(self.mode_box)

        btn_layout = QHBoxLayout()
        btn_style = f"QPushButton {{ background-color: #2A3644; color: {TEXT_MUTED}; font-weight: bold; padding: 12px; border-radius: 5px; }}"
        self.start_btn = QPushButton("START RECORDING"); self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet(btn_style); self.start_btn.clicked.connect(self.start_stats_capture)

        self.stop_btn = QPushButton("STOP & REPORT"); self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(btn_style); self.stop_btn.clicked.connect(self.stop_stats_capture)

        btn_layout.addWidget(self.start_btn); btn_layout.addWidget(self.stop_btn); config_lyt.addLayout(btn_layout)
        right_panel.addWidget(config_frame)

        # Pitch Display Frame
        pitch_box = QFrame()
        pitch_box.setStyleSheet(f"background-color: {PANEL_BG}; border-radius: 10px;")
        pitch_lyt = QVBoxLayout(pitch_box)
        pitch_lyt.setContentsMargins(15, 25, 15, 25)
        self.pitch_label = QLabel("--")
        self.pitch_label.setStyleSheet(f"font-size: 72pt; color: {AMBER}; font-family: 'Monospace'; font-weight: bold;")
        self.freq_label = QLabel("0.0 Hz")
        self.freq_label.setStyleSheet(f"font-size: 14pt; color: {TEXT_MUTED}; font-family: 'Monospace';")
        pitch_lyt.addWidget(self.pitch_label, alignment=Qt.AlignCenter)
        pitch_lyt.addWidget(self.freq_label, alignment=Qt.AlignCenter)
        right_panel.addWidget(pitch_box)

        # Meters Layout
        meters = QHBoxLayout()

        # Resonance Gauge
        res_c = QFrame()
        res_c.setStyleSheet(f"background-color: {PANEL_BG}; border-radius: 10px;")
        res_l = QVBoxLayout(res_c)
        res_l.addWidget(QLabel("RESONANCE", styleSheet=f"color:{TEXT_MUTED}; font-size:8pt; font-weight:bold;"), alignment=Qt.AlignCenter)
        self.spr_val = QLabel("-40.0 dB")
        self.spr_val.setStyleSheet(f"color:{TEXT_LIGHT}; font-family:Monospace; font-size:12pt; font-weight: bold;")
        res_l.addWidget(self.spr_val, alignment=Qt.AlignCenter)

        self.spr_gauge = QProgressBar()
        self.spr_gauge.setOrientation(Qt.Vertical)
        self.spr_gauge.setRange(-35, 15)
        self.spr_gauge.setFixedWidth(30)
        self.spr_gauge.setFixedHeight(150)
        self.spr_gauge.setStyleSheet(f"""
            QProgressBar {{ background-color: #11151A; border-radius: 5px; }}
            QProgressBar::chunk {{ background-color: {AMBER}; border-radius: 5px; }}
        """)
        res_l.addWidget(self.spr_gauge, alignment=Qt.AlignCenter)
        meters.addWidget(res_c)

        # Sonority Lamp
        son_c = QFrame()
        son_c.setStyleSheet(f"background-color: {PANEL_BG}; border-radius: 10px;")
        son_l = QVBoxLayout(son_c)
        son_l.addWidget(QLabel("SONORITY", styleSheet=f"color:{TEXT_MUTED}; font-size:8pt; font-weight:bold;"), alignment=Qt.AlignCenter)
        self.pv_lamp = QLabel("OFF")
        self.pv_lamp.setFixedSize(90, 90)
        self.pv_lamp.setAlignment(Qt.AlignCenter)
        self.pv_lamp.setStyleSheet("border-radius: 45px; border: 4px solid #11151A; background-color: #1A2129; color: #4A5B6D; font-weight: bold; font-size: 11pt;")
        son_l.addWidget(self.pv_lamp, alignment=Qt.AlignCenter)
        meters.addWidget(son_c)

        right_panel.addLayout(meters)

        # Vibrato & Status
        self.vib_label = QLabel("VIB: 0.0 Hz")
        self.vib_label.setStyleSheet(f"color:{AMBER}; background-color: {PANEL_BG}; font-family:Monospace; font-size:16pt; border-radius: 10px; padding: 15px; font-weight:bold;")
        self.vib_label.setAlignment(Qt.AlignCenter)
        right_panel.addWidget(self.vib_label)

        self.status_box = QLabel("READY 💤")
        self.status_box.setStyleSheet(f"background-color: #11151A; border: 1px solid {TEXT_MUTED}; color:{TEXT_MUTED}; font-family:Monospace; font-size:11pt; font-weight:bold; border-radius: 5px;")
        self.status_box.setFixedHeight(45)
        self.status_box.setAlignment(Qt.AlignCenter)
        right_panel.addWidget(self.status_box)

        content_layout.addLayout(right_panel, 1)

        # --- FOOTER CREDITS ---
        footer_label = QLabel("DEVELOPED BY REKAMBERGERAKLAB YOGYAKARTA-INDONESIA")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9pt; font-weight: bold; letter-spacing: 2px; margin-top: 10px;")
        root_layout.addWidget(footer_label)

    def closeEvent(self, event):
        """Ensure the audio thread is safely killed when the app closes."""
        if self.is_recording_stats:
            self.stop_stats_capture()
        
        if self.processor.isRunning():
            self.processor.stop_engine()
            
        event.accept()

    def sync_stats_ui(self, mode):
        is_stats = mode == "STATISTIC ANALYSIS"
        self.start_btn.setEnabled(is_stats)

        if is_stats:
            self.start_btn.setStyleSheet(f"QPushButton {{ background-color: {AMBER}; color: #000; font-weight: bold; padding: 12px; border-radius: 5px; }} QPushButton:hover {{ background-color: #FFC033; }}")
        else:
            self.start_btn.setStyleSheet(f"QPushButton {{ background-color: #2A3644; color: {TEXT_MUTED}; font-weight: bold; padding: 12px; border-radius: 5px; }}")

        if not is_stats and self.is_recording_stats:
            self.stop_stats_capture()

    def start_stats_capture(self):
        self.stats_cache = {k: [] if isinstance(v, list) else 0 for k, v in self.stats_cache.items()}
        self.is_recording_stats = True; self.start_time = time.time()
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.stop_btn.setStyleSheet(f"QPushButton {{ background-color: #D9534F; color: #FFF; font-weight: bold; padding: 12px; border-radius: 5px; }} QPushButton:hover {{ background-color: #C9302C; }}")
        self.status_box.setText("DEEP ANALYSIS IN PROGRESS 🔴")
        self.status_box.setStyleSheet(f"background-color: #3B1B1B; border: 1px solid #D9534F; color:#D9534F; font-family:Monospace; font-size:11pt; font-weight:bold; border-radius: 5px;")

    def stop_stats_capture(self):
        if not self.is_recording_stats: return
        duration = time.time() - self.start_time
        self.is_recording_stats = False; self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(f"QPushButton {{ background-color: #2A3644; color: {TEXT_MUTED}; font-weight: bold; padding: 12px; border-radius: 5px; }}")
        self.status_box.setText("READY 💤")
        self.status_box.setStyleSheet(f"background-color: #11151A; border: 1px solid {TEXT_MUTED}; color:{TEXT_MUTED}; font-family:Monospace; font-size:11pt; font-weight:bold; border-radius: 5px;")
        self.show_vocal_report(duration)

    def show_vocal_report(self, duration):
        if not self.stats_cache['spr']: return

        avg_spr = np.mean(self.stats_cache['spr'])
        avg_vib = np.mean(self.stats_cache['vib_rate'])
        pitch_dev = np.std(self.stats_cache['cents'])
        stability = max(0, 100 - (pitch_dev * 2))
        sonority_score = (self.stats_cache['sonority_hits'] / self.stats_cache['total_samples']) * 100
        rms_stability = 100 - (np.std(self.stats_cache['rms']) * 1000)

        advice = []
        if avg_spr < -8:
            advice.append("❌ PROBLEM: Muffled Tone (Back Placement). \n   REASON: The larynx may be too high or the tongue is bunched. \n   SOLVE: Practice 'Bratty' sounds (like a child saying 'Nay-Nay') to narrow the epiglottic funnel.")
        elif avg_spr > 8:
            advice.append("⚠️ PROBLEM: Hyper-Compression (Twang Overload). \n   REASON: Too much squeezed energy in the high frequencies. \n   SOLVE: Soften the jaw and imagine a 'yawn' in the back of the throat to increase space.")
        if avg_vib < 4.2:
            advice.append("❌ PROBLEM: Heavy Wobble. \n   REASON: Vocal folds are too thick/pressed. \n   SOLVE: Shift to a lighter 'Head Voice' coordination and use sirens to find a thinner fold edge.")
        elif avg_vib > 7.8:
            advice.append("⚠️ PROBLEM: Nervous Bleat. \n   REASON: Excess subglottal air pressure or 'shaking' larynx. \n   SOLVE: Focus on the 'Farinelli' breathing exercise—inhale 4s, hold 4s, exhale 4s—to steady the air.")
        if stability < 75:
            advice.append("❌ PROBLEM: Intonation Instability. \n   REASON: Poor vowel modification as you go higher. \n   SOLVE: If singing high, 'round' your vowels (turn [A] toward [O]) to help the vocal folds transition.")
        if rms_stability < 65:
            advice.append("⚠️ PROBLEM: Weak Support (Decaying Energy). \n   REASON: The 'diaphragmatic anchor' is collapsing mid-phrase. \n   SOLVE: Sing while leaning against a wall or pushing a heavy object to engage the core muscles.")

        if not advice:
            advice.append("🌟 STATUS: PROFESSIONAL. Your metrics show balanced resonance and free vibrato. Practice complex runs next.")

        report = (f"🔍 DEEP PERFORMANCE DIAGNOSIS 🔍\n"
                  f"--------------------------------------\n"
                  f"⏱️ SESSION: {duration:.1f}s | ✨ SONORITY: {sonority_score:.1f}%\n"
                  f"🔊 RESONANCE: {avg_spr:.2f} dB | 🌀 VIBRATO: {avg_vib:.2f} Hz\n"
                  f"🎯 STABILITY: {stability:.1f}% | 🌬️ SUPPORT: {max(0, rms_stability):.1f}%\n"
                  f"--------------------------------------\n"
                  f"📋 BIOMECHANICAL ANALYSIS & FIXES:\n" + "\n\n".join(advice))

        msg = QMessageBox(self)
        msg.setWindowTitle("Professional Vocal Solution")
        msg.setText(report)
        msg.setStyleSheet(f"QMessageBox {{ background-color: {PANEL_BG}; }} QLabel {{ color: {TEXT_LIGHT}; font-family: Monospace; font-size: 10pt; }} QPushButton {{ background-color: {AMBER}; color: #000; font-weight: bold; padding: 5px 15px; border-radius: 3px; }}")
        msg.exec_()

    def change_device(self, index):
        self.processor.stop_engine()
        self.processor.device_mic = self.mics[index]  # Send actual soundcard object to thread
        self.processor.start()

    def store_data(self, spr, rms, mag, vib, pitch, cents):
        self.target_spr, self.target_vib, self.target_pitch, self.target_cents = spr, vib, pitch, cents
        if len(mag) == len(self.target_mag): self.target_mag = mag
        if self.is_recording_stats and rms > 0.005:
            self.stats_cache['spr'].append(spr); self.stats_cache['vib_rate'].append(vib)
            self.stats_cache['cents'].append(cents); self.stats_cache['rms'].append(rms)
            self.stats_cache['total_samples'] += 1
            self.stats_cache['brightness'].append(spr + 5.0)
            if spr > 2.0 and 4.0 < vib < 7.5: self.stats_cache['sonority_hits'] += 1

    def smooth_render(self):
        self.current_mag += (self.target_mag - self.current_mag) * 0.3; self.spec_curve.setData(self.current_mag)
        self.current_spr += (self.target_spr - self.current_spr) * 0.1; self.spr_gauge.setValue(int(self.current_spr))
        self.spr_val.setText(f"{self.current_spr:.1f} dB"); self.vib_label.setText(f"VIB: {self.target_vib:.1f} Hz")

        if self.current_spr > 2.0 and 4.0 < self.target_vib < 7.5:
            self.pv_lamp.setText("PERFECT")
            self.pv_lamp.setStyleSheet(f"border-radius: 45px; border: 4px solid #FFF; background-color: {AMBER}; color: #000; font-weight: bold; font-size: 12pt;")
        else:
            self.pv_lamp.setText("OFF")
            self.pv_lamp.setStyleSheet("border-radius: 45px; border: 4px solid #11151A; background-color: #1A2129; color: #4A5B6D; font-weight: bold; font-size: 11pt;")

        if self.target_pitch > 40:
            note, _ = get_note_details(self.target_pitch)
            self.pitch_label.setText(note)
            self.freq_label.setText(f"{self.target_pitch:.1f} Hz")
            self.pitch_trace_data = np.roll(self.pitch_trace_data, -1)
            self.pitch_trace_data[-1] = self.target_cents
            self.pitch_curve.setData(self.pitch_trace_data)
        else:
            self.pitch_label.setText("--")
            self.freq_label.setText("0.0 Hz")
            self.pitch_trace_data = np.roll(self.pitch_trace_data, -1)
            self.pitch_trace_data[-1] = 0
            self.pitch_curve.setData(self.pitch_trace_data)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = VocalMasterGUI()
    win.show()
    sys.exit(app.exec_())
