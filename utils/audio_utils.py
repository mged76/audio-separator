import os
import librosa
import soundfile as sf
from scipy import signal
import numpy as np
import noisereduce as nr
from pydub import AudioSegment
import tempfile

def separate_tracks(input_path, output_dir, original_filename):
    try:
        # تحميل الملف الصوتي
        y, sr = librosa.load(input_path, sr=44100, mono=True)
        
        # 1. تطبيق فلاتر متقدمة لتحسين الجودة
        # تخفيض الضوضاء باستخدام noisereduce فقط
        y = nr.reduce_noise(y=y, sr=sr, stationary=True)
        
        # تحسين نطاق الترددات
        y = librosa.effects.preemphasis(y)
        
        # 2. فصل المسارات المتقدمة
        # تصميم المرشحات المتقدمة
        def butter_bandpass(lowcut, highcut, fs, order=5):
            nyq = 0.5 * fs
            low = lowcut / nyq
            high = highcut / nyq
            b, a = signal.butter(order, [low, high], btype='band')
            return b, a

        def butter_highpass(cutoff, fs, order=5):
            nyq = 0.5 * fs
            normal_cutoff = cutoff / nyq
            b, a = signal.butter(order, normal_cutoff, btype='high')
            return b, a

        def butter_lowpass(cutoff, fs, order=5):
            nyq = 0.5 * fs
            normal_cutoff = cutoff / nyq
            b, a = signal.butter(order, normal_cutoff, btype='low')
            return b, a

        # المسارات:
        # - الصوت البشري (80-5000 هرتز)
        b, a = butter_bandpass(80, 5000, sr)
        vocals = signal.lfilter(b, a, y)
        
        # - الآلات الموسيقية (100-10000 هرتز)
        b, a = butter_bandpass(100, 10000, sr)
        instruments = signal.lfilter(b, a, y)
        
        # - الأصوات الطبيعية (10-2000 هرتز)
        b, a = butter_bandpass(10, 2000, sr)
        nature = signal.lfilter(b, a, y)
        
        # - المؤثرات الصوتية (50-8000 هرتز)
        b, a = butter_bandpass(50, 8000, sr)
        effects = signal.lfilter(b, a, y)
        
        # 3. تنقية وتوازن المسارات
        vocals = nr.reduce_noise(y=vocals, sr=sr)
        instruments = apply_compressor(instruments, sr)
        nature = apply_eq(nature, sr, bass_boost=2.0)
        effects = apply_reverb(effects, sr, room_size=0.5)
        
        # 4. حفظ النتائج باسم معدل
        base_name = os.path.splitext(original_filename)[0] + " (معدله)"
        os.makedirs(output_dir, exist_ok=True)
        
        # إنشاء أسماء الملفات المعدلة
        sf.write(f"{output_dir}/{base_name} - صوت بشري.wav", vocals, sr)
        sf.write(f"{output_dir}/{base_name} - آلات موسيقية.wav", instruments, sr)
        sf.write(f"{output_dir}/{base_name} - أصوات طبيعية.wav", nature, sr)
        sf.write(f"{output_dir}/{base_name} - مؤثرات صوتية.wav", effects, sr)
        
        # إرجاع المسارات مع أسمائها المعدلة
        track_names = {
            "vocals": f"{base_name} - صوت بشري.wav",
            "instruments": f"{base_name} - آلات موسيقية.wav",
            "nature": f"{base_name} - أصوات طبيعية.wav",
            "effects": f"{base_name} - مؤثرات صوتية.wav"
        }
        
        return True, track_names
    except Exception as e:
        print(f"حدث خطأ أثناء الفصل: {str(e)}")
        return False, {}

# === وظائف معالجة إضافية ===
def apply_compressor(audio, sr, threshold=-20.0, ratio=4.0):
    """تطبيق ضاغط ديناميكي"""
    # حل بديل بسيط للضاغط
    audio = librosa.mu_compress(audio, mu=255)
    return audio

def apply_eq(audio, sr, bass_boost=1.0, treble_boost=1.0):
    """تطبيق معادل ترددي"""
    # تعزيز الترددات المنخفضة
    sos = signal.butter(4, 100, 'lowpass', fs=sr, output='sos')
    bass = signal.sosfilt(sos, audio) * bass_boost
    
    # تعزيز الترددات العالية
    sos = signal.butter(4, 5000, 'highpass', fs=sr, output='sos')
    treble = signal.sosfilt(sos, audio) * treble_boost
    
    return bass + treble

def apply_reverb(audio, sr, room_size=0.5):
    """تطبيق صدى صوتي"""
    # حل بديل بسيط للصدى
    D = int(room_size * sr)  # تأخير
    decay = 0.5
    delayed = np.zeros_like(audio)
    delayed[D:] = audio[:-D] * decay
    return audio + delayed