# Vocal Quality Measurement (RBLAB) - Technical Documentation

Sistem ini merupakan instrumen analisis akustik vokal berbasis *Digital Signal Processing* (DSP) yang dirancang untuk mengevaluasi parameter psikoakustik dan musikologi secara real-time.

## 1. Analisis Frekuensi Fundamental ($f_0$) dan Intonasi
Sistem mengimplementasikan metodologi ekstraksi nada yang presisi untuk memantau performa melodi:
* **Algoritma HPS:** Menggunakan *Harmonic Product Spectrum* untuk mengidentifikasi nada dasar ($f_0$) penyanyi dengan cara memperkuat harmoni pada spektrum frekuensi.
* **Akurasi Pitch:** Mengonversi frekuensi yang terdeteksi ke dalam notasi musik standar (seperti A4 atau C#3) berdasarkan referensi A440.
* **Analisis Cents:** Mengukur deviasi intonasi dalam satuan *cents* (1/100 *semitone*) melalui grafik *Intonation Trace* yang berfungsi sebagai osiloskop real-time untuk memantau stabilitas napas.

## 2. Kualitas Spektral dan Resonansi (*Singer’s Formant*)
Karakter timbre dianalisis melalui distribusi energi pada spektrum frekuensi:
* **Singer’s Formant / Resonance (SPR):** Metrik ini mengukur rasio energi antara frekuensi rendah (100–900 Hz) yang merepresentasikan bobot vokal, dengan frekuensi tinggi (2000–4000 Hz) yang merepresentasikan kecerahan atau proyeksi suara.
* **Interpretasi Akustik:** Nilai SPR positif menunjukkan penguatan pada *formant* ketiga hingga kelima ($F_3, F_4, F_5$), yang memungkinkan suara "menembus" iringan instrumen lain (proyeksi vokal).

## 3. Dinamika Vibrato (*Vibrato Rate*)
Vibrato dianalisis sebagai modulasi frekuensi periodik untuk menentukan kesehatan teknik vokal:
* **Kecepatan Vibrato (Hz):** Menghitung jumlah osilasi frekuensi per detik.
* **Standar Estetika:** Rentang **4.0 Hz hingga 7.5 Hz** diklasifikasikan sebagai vibrato ideal. Frekuensi di bawah rentang ini diidentifikasi sebagai *wobble*, sementara di atasnya disebut *tremolo* atau *bleat*.

## 4. Sonority dan Diagnosa Performa
Evaluasi komprehensif terhadap efisiensi vokal dilakukan melalui logika sistem:
* **Indikator Sonority (Lampu "PERFECT"):** Gerbang logika yang aktif hanya jika penyanyi mencapai sinergi antara resonansi tinggi ($SPR > 2.0$ dB) dan vibrato stabil (4.0–7.5 Hz) secara simultan.
* **Laporan Diagnostik:** Menggunakan analisis statistik (standar deviasi *cents* dan rata-rata RMS) untuk mengidentifikasi masalah teknik seperti *hyper-compression* atau *weak support* serta memberikan saran biomekanis perbaikan.

## 5. Konfigurasi Sistem
Untuk memastikan resolusi frekuensi tinggi yang mampu menangkap nuansa harmonik terkecil, sistem beroperasi pada:
* **Sample Rate:** 48.000 Hz.
* **Block Size:** 8.192 samples.

---
*Developed by Rekambergerak - Yogyakarta, Indonesia.*
