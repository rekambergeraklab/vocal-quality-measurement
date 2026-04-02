# Vocal Quality Measurement (RBLAB) - Technical Documentation

Sistem penganalisis kualitas vokal berbasis Python yang menggunakan pemrosesan sinyal digital (DSP) untuk mengevaluasi teknik vokal secara real-time.

## Deskripsi Fungsional
Aplikasi ini melakukan ekstraksi parameter akustik dari input audio untuk memberikan umpan balik objektif mengenai teknik vokal. Sistem ini membedah suara berdasarkan struktur harmonik dan distribusi energi spektral.

## Parameter Analisis Utama
* **Ekstraksi Pitch (f0):** Menggunakan algoritma *Harmonic Product Spectrum* (HPS) untuk mendeteksi nada dasar dengan mengalikan spektrum magnitudo yang dikompresi.
* **Singer's Formant / Resonance (SPR):** Mengukur rasio energi antara pita frekuensi rendah (100-900 Hz) dan pita frekuensi tinggi (2000-4000 Hz) untuk menentukan daya proyeksi suara.
* **Analisis Vibrato:** Mendeteksi kecepatan osilasi frekuensi periodik. Rentang ideal ditetapkan pada 4.0 Hz hingga 7.5 Hz.
* **Intonation Trace:** Visualisasi deviasi nada dalam satuan *cents* (1/100 semitone) untuk memantau stabilitas intonasi.

## Spesifikasi Sistem
* **Sample Rate (FS):** 48.000 Hz.
* **Block Size:** 8.192 samples.
* **Library Utama:** PyQt5, NumPy, SoundDevice, SciPy, dan PyQtGraph.

## Instalasi dan Penggunaan
1. Pastikan Python 3.10+ telah terinstal.
2. Instal dependensi: `pip install numpy scipy sounddevice pyqt5 pyqtgraph`.
3. Jalankan aplikasi: `python vocal_mesin_io.py`.

## macOS Permissions Note
Untuk pengguna macOS, pastikan langkah berikut telah dilakukan:
1. **Microphone Access:** Berikan izin akses mikrofon pada `System Settings > Privacy & Security > Microphone`.
2. **Gatekeeper:** Jika aplikasi diblokir, buka melalui `System Settings > Privacy & Security > Open Anyway`.
3. **Executable Bit:** Gunakan `chmod +x <file_name>` jika muncul error 'Permission Denied'.

---
© 2026 Developed by Rekambergerak - Yogyakarta, Indonesia.
