import sys
from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
import subprocess
import shutil
from datetime import datetime
import ffmpeg
import json
import traceback
from demucs import __version__ as demucs_version

app = Flask(__name__)
app.config.update({
    'UPLOAD_FOLDER': 'static/uploads',
    'SEPARATED_FOLDER': 'static/separated',
    'EXPORT_FOLDER': 'static/exports',
    'ALLOWED_EXTENSIONS': {'mp3', 'mp4', 'wav'},
    'ALLOWED_EXPORT_EXTENSIONS': {'mp4'},
    'MAX_CONTENT_LENGTH': 100 * 1024 * 1024,
    'MAX_EXPORT_DURATION': 3600,
    'SECRET_KEY': 'your-secret-key-here'
})

# Print Demucs version at startup
print(f"\n[INIT] Demucs version: {demucs_version}\n")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    try:
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': f"/static/uploads/{filename}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process', methods=['POST'])
def process_file():
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({"error": "Invalid request data"}), 400

        filename = data['filename']
        input_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        original_video_url = None
        
        print(f"\n[DEBUG] Processing file: {input_path}")
        print(f"[DEBUG] File exists: {os.path.exists(input_path)}")
        
        if not os.path.exists(input_path):
            return jsonify({"error": f"File not found at {input_path}"}), 404

        # Handle video files
        if filename.lower().endswith('.mp4'):
            try:
                # Create a copy of original video for playback
                original_video_filename = f"original_{filename}"
                original_video_path = os.path.join(app.config['UPLOAD_FOLDER'], original_video_filename)
                
                print(f"[DEBUG] Copying original video: {input_path} -> {original_video_path}")
                
                (
                    ffmpeg.input(input_path)
                    .output(original_video_path, vcodec='copy', acodec='copy')
                    .run(overwrite_output=True, quiet=True)
                )
                
                original_video_url = f"/static/uploads/{original_video_filename}"
                
                # Convert audio to WAV for processing
                wav_filename = f"{os.path.splitext(filename)[0]}.wav"
                wav_path = os.path.join(app.config['UPLOAD_FOLDER'], wav_filename)
                
                print(f"[DEBUG] Extracting audio to WAV: {input_path} -> {wav_path}")
                
                (
                    ffmpeg.input(input_path)
                    .output(wav_path, acodec='pcm_s16le', ac=2, ar='44100')
                    .run(overwrite_output=True, quiet=True)
                )
                input_path = wav_path
                filename = wav_filename
            except ffmpeg.Error as e:
                error_msg = e.stderr.decode('utf8') if e.stderr else str(e)
                print(f"[FFMPEG ERROR] {error_msg}")
                return jsonify({"error": f"Video processing failed: {error_msg}"}), 500
            except Exception as e:
                return jsonify({"error": f"Video processing failed: {str(e)}"}), 500

        track_name = os.path.splitext(filename)[0]
        output_base = os.path.abspath(app.config['SEPARATED_FOLDER'])
        
        print(f"[DEBUG] Output folder: {output_base}")
        print(f"[DEBUG] Track name: {track_name}")

        # Clean previous results
        model_path = os.path.join(output_base, 'htdemucs')
        if os.path.exists(model_path):
            print(f"[DEBUG] Cleaning folder: {model_path}")
            shutil.rmtree(model_path, ignore_errors=True)

        # Run Demucs command
        command = [
            "python", "-m", "demucs",
            "--two-stems=vocals",
            "--mp3",
            "--mp3-bitrate", "192",
            "-n", "htdemucs",
            "--out", output_base,
            input_path
        ]

        print(f"\n[DEBUG] Executing: {' '.join(command)}\n")
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=600
            )
            print("[DEBUG] Command output:")
            print(result.stdout)
            
            # Check if output files were created
            output_dir = os.path.join(model_path, track_name)
            if not os.path.exists(output_dir):
                raise Exception("Demucs failed to create output files")
                
        except subprocess.TimeoutExpired:
            return jsonify({"error": "Processing timed out (10 minutes)"}), 500
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed (return code {e.returncode}):\n{e.stderr}"
            print(f"[ERROR] {error_msg}")
            return jsonify({"error": error_msg}), 500
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return jsonify({"error": error_msg}), 500

        # Find output files
        output_files = {}
        stems = ['vocals', 'no_vocals']
        
        for stem in stems:
            audio_path = os.path.join(model_path, track_name, f"{stem}.mp3")
            if os.path.exists(audio_path):
                rel_path = os.path.relpath(audio_path, start=os.path.abspath('static'))
                output_files[stem] = "/static/" + rel_path.replace('\\', '/')
                print(f"[DEBUG] Found: {output_files[stem]}")
            else:
                print(f"[WARNING] Missing: {audio_path}")

        if not output_files:
            error_details = {
                "error": "No output files created",
                "command": ' '.join(command),
                "output_folder": output_base,
                "content": str(os.listdir(output_base))
            }
            return jsonify(error_details), 500

        response_data = {
            "success": True,
            "tracks": output_files,
            "video_url": original_video_url if original_video_url else f"/static/uploads/{filename}"
        }

        return jsonify(response_data)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ... (الاستيرادات تبقى كما هي)

@app.route('/export', methods=['POST'])
def export_video():
    try:
        # تسجيل بيانات الطلب الواردة لأغراض التصحيح
        print(f"\n[EXPORT] Received request with data: {request.data}")
        
        # التحقق من نوع المحتوى
        if request.content_type != 'application/json':
            return jsonify({"error": "Content-Type must be application/json"}), 400

        try:
            data = request.get_json()
        except Exception as e:
            print(f"[EXPORT ERROR] JSON parsing failed: {str(e)}")
            return jsonify({
                "error": "Invalid JSON data",
                "details": str(e)
            }), 400

        print(f"[EXPORT] Parsed data: {data}")

        # التحقق من الحقول المطلوبة
        required_fields = ['video_url', 'tracks']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # معالجة مسار الفيديو
        video_url = data['video_url']
        if not isinstance(video_url, str) or not video_url.startswith('/static/'):
            return jsonify({"error": "Invalid video URL format"}), 400
            
        video_path = os.path.abspath('.' + video_url)
        if not os.path.exists(video_path):
            return jsonify({"error": "Video file not found"}), 404

        # معالجة مسارات الصوت
        valid_tracks = {}
        for track_name, track_url in data['tracks'].items():
            # تطبيع المسار (إزالة النطاق إذا موجود)
            normalized_url = track_url.replace('http://localhost:5000', '') if 'http://localhost:5000' in track_url else track_url
            
            if not isinstance(normalized_url, str) or not normalized_url.startswith('/static/'):
                print(f"[EXPORT WARNING] Invalid track URL for {track_name}: {track_url}")
                continue
                
            track_path = os.path.abspath('.' + normalized_url)
            if os.path.exists(track_path):
                valid_tracks[track_name] = track_path
            else:
                print(f"[EXPORT WARNING] Track file not found: {track_path}")

        if not valid_tracks:
            return jsonify({"error": "No valid audio tracks found"}), 400

        # إعداد مجلد التصدير
        output_dir = os.path.abspath(app.config['EXPORT_FOLDER'])
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"export_{datetime.now().timestamp()}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        # معالجة مستويات الصوت
        audio_inputs = []
        volumes = data.get('volumes', {})
        
        for track_name, track_path in valid_tracks.items():
            try:
                volume = float(volumes.get(track_name, 1.0))
                audio_inputs.append(
                    ffmpeg.input(track_path).filter('volume', volume)
                )
                print(f"[EXPORT] Processing track: {track_name} with volume {volume}")
            except (ValueError, TypeError) as e:
                print(f"[EXPORT WARNING] Invalid volume for {track_name}, using default. Error: {str(e)}")
                audio_inputs.append(ffmpeg.input(track_path))

        # مزج المسارات الصوتية
        if len(audio_inputs) == 1:
            mixed_audio = audio_inputs[0]
        else:
            mixed_audio = ffmpeg.filter(audio_inputs, 'amix')

        # تطبيع الصوت
        mixed_audio = mixed_audio.filter('loudnorm')

        # تصدير الفيديو مع الصوت الجديد
        try:
            print(f"[EXPORT] Starting video export to {output_path}")
            (
                ffmpeg.input(video_path)
                .output(
                    mixed_audio,
                    output_path,
                    vcodec='copy',
                    acodec='aac',
                    audio_bitrate='192k',
                    preset='fast',
                    movflags='faststart'
                )
                .run(overwrite_output=True, quiet=True)
            )
            print("[EXPORT] Video export completed successfully")
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf8') if e.stderr else str(e)
            print(f"[EXPORT ERROR] FFmpeg failed: {error_msg}")
            return jsonify({
                "error": "Video export failed",
                "details": error_msg.splitlines()[0] if error_msg else "Unknown ffmpeg error"
            }), 500

        # التحقق من وجود الملف المصدر
        if not os.path.exists(output_path):
            error_msg = "Export failed - output file not created"
            print(f"[EXPORT ERROR] {error_msg}")
            return jsonify({"error": error_msg}), 500

        print(f"[EXPORT] Export successful. File size: {os.path.getsize(output_path)} bytes")
        return jsonify({
            "success": True,
            "download_url": f"/static/exports/{output_filename}",
            "file_size": os.path.getsize(output_path)
        })
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"[EXPORT CRITICAL ERROR] {error_msg}")
        traceback.print_exc()
        return jsonify({
            "error": "Internal server error",
            "details": error_msg
        }), 500

@app.route('/results')
def results():
    try:
        tracks = request.args.get('tracks', '{}')
        video_url = request.args.get('video', '')
        
        # Security check
        if video_url and (not isinstance(video_url, str) or not video_url.startswith('/static/')):
            video_url = ''
        
        try:
            tracks_data = json.loads(tracks)
            if not isinstance(tracks_data, dict):
                tracks_data = {}
        except json.JSONDecodeError:
            tracks_data = {}

        return render_template(
            'results.html',
            tracks=tracks_data,
            video_url=video_url if video_url != 'undefined' else None
        )
    except Exception as e:
        return jsonify({"error": f"Results processing failed: {str(e)}"}), 400

@app.route('/static/<path:filename>')
def static_files(filename):
    # Security check
    if '..' in filename or filename.startswith('/'):
        return jsonify({"error": "Invalid file path"}), 400
        
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # Create required directories
    for folder in ['UPLOAD_FOLDER', 'SEPARATED_FOLDER', 'EXPORT_FOLDER']:
        os.makedirs(app.config[folder], exist_ok=True)
        print(f"[INIT] Created directory: {app.config[folder]}")
    
    # Print system information
    print("\n[INIT] System check:")
    print(f"Python version: {sys.version}")
    try:
        ffmpeg_version = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        print(f"FFmpeg version: {ffmpeg_version.stdout.splitlines()[0] if ffmpeg_version.returncode == 0 else 'Not available'}")
    except Exception as e:
        print(f"FFmpeg version: Not available ({str(e)})")
    
    import os
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=True)
