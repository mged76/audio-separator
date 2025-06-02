import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

def merge_tracks(video_path, audio_tracks, output_dir):
    """
    دمج مسارات صوتية مع فيديو
    
    :param video_path: مسار ملف الفيديو
    :param audio_tracks: قائمة بمسارات الملفات الصوتية
    :param output_dir: مجلد الحفظ
    :return: مسار الملف الناتج
    """
    try:
        # تحميل الفيديو
        video = VideoFileClip(video_path)
        
        # تحميل المسارات الصوتية
        audio_clips = []
        for track_path in audio_tracks:
            if os.path.exists(track_path):
                audio_clips.append(AudioFileClip(track_path))
        
        if not audio_clips:
            raise ValueError("No valid audio tracks provided")
        
        # دمج المسارات الصوتية
        final_audio = CompositeAudioClip(audio_clips)
        
        # تطبيق الصوت على الفيديو
        video = video.set_audio(final_audio)
        
        # إنشاء مجلد الإخراج إذا لم يكن موجوداً
        os.makedirs(output_dir, exist_ok=True)
        
        # إنشاء اسم الملف الناتج
        output_filename = f"merged_{os.path.basename(video_path)}"
        output_path = os.path.join(output_dir, output_filename)
        
        # حفظ الفيديو النهائي
        video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset='fast',
            ffmpeg_params=['-crf', '23']
        )
        
        return output_path
        
    except Exception as e:
        print(f"Error merging tracks: {e}")
        raise