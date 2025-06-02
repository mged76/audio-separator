
export class AudioEditor {
    constructor() {
        this.video = document.getElementById('mainVideo');
        this.tracks = {};
        this.initTracks();
        this.setupEventListeners();
    }

    initTracks() {
        document.querySelectorAll('.track').forEach(trackElement => {
            const trackName = trackElement.dataset.track;
            const trackUrl = trackElement.dataset.src ||
                `/static/separated/${trackName}.mp3`;

            this.tracks[trackName] = {
                element: new Audio(trackUrl),
                muteBtn: trackElement.querySelector('.mute-btn'),
                volumeSlider: trackElement.querySelector('.volume-slider'),
                isMuted: false
            };
        });
    }

    setupEventListeners() {
        // أحداث الفيديو
        this.video.addEventListener('play', () => this.syncPlayback());
        this.video.addEventListener('pause', () => this.pauseAll());
        this.video.addEventListener('seeked', () => this.syncTime());
        this.video.addEventListener('timeupdate', () => this.syncTime());

        // أحداث التحكم في المسارات
        Object.keys(this.tracks).forEach(trackName => {
            const track = this.tracks[trackName];

            track.muteBtn.addEventListener('click', () => {
                this.toggleMute(trackName);
            });

            track.volumeSlider.addEventListener('input', (e) => {
                this.setVolume(trackName, e.target.value);
            });

            track.element.addEventListener('error', () => {
                this.handleTrackError(trackName);
            });
        });

        // زر التصدير
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportVideo();
        });
    }

    syncPlayback() {
        this.syncTime();
        Object.values(this.tracks).forEach(track => {
            track.element.play().catch(e => console.error('Play error:', e));
        });
    }

    pauseAll() {
        Object.values(this.tracks).forEach(track => {
            track.element.pause();
        });
    }

    syncTime() {
        const currentTime = this.video.currentTime;
        Object.values(this.tracks).forEach(track => {
            if (Math.abs(track.element.currentTime - currentTime) > 0.1) {
                track.element.currentTime = currentTime;
            }
        });
    }

    toggleMute(trackName) {
        const track = this.tracks[trackName];
        track.isMuted = !track.isMuted;
        track.element.muted = track.isMuted;

        const icon = track.muteBtn.querySelector('i');
        if (track.isMuted) {
            icon.classList.remove('icon-volume-high');
            icon.classList.add('icon-volume-mute');
            track.muteBtn.classList.add('active');
        } else {
            icon.classList.remove('icon-volume-mute');
            icon.classList.add('icon-volume-high');
            track.muteBtn.classList.remove('active');
        }
    }

    setVolume(trackName, volume) {
        this.tracks[trackName].element.volume = volume;
    }

    handleTrackError(trackName) {
        console.error(`Error loading track: ${trackName}`);
        const trackElement = document.querySelector(`.track[data-track="${trackName}"]`);
        if (trackElement) {
            trackElement.style.opacity = '0.5';
            trackElement.querySelector('.mute-btn').disabled = true;
            trackElement.querySelector('.volume-slider').disabled = true;
        }
    }

    async exportVideo() {
        const exportBtn = document.getElementById('exportBtn');
        exportBtn.disabled = true;
        exportBtn.innerHTML = '<i class="icon-spinner"></i> جاري التصدير...';

        try {
            // إنشاء كائن يحتوي على جميع المسارات ومستويات الصوت
            const tracksData = {};
            Object.keys(this.tracks).forEach(trackName => {
                // الحصول على المسار النسبي فقط (إزالة النطاق إذا موجود)
                let trackUrl = this.tracks[trackName].element.src;
                if (trackUrl.includes(window.location.origin)) {
                    trackUrl = trackUrl.replace(window.location.origin, '');
                }

                tracksData[trackName] = trackUrl;
            });

            // إنشاء كائن مستويات الصوت
            const volumesData = {};
            Object.keys(this.tracks).forEach(trackName => {
                volumesData[trackName] = this.tracks[trackName].element.volume;
            });

            // الحصول على مسار الفيديو (إزالة النطاق إذا موجود)
            let videoUrl = this.video.querySelector('source').src;
            if (videoUrl.includes(window.location.origin)) {
                videoUrl = videoUrl.replace(window.location.origin, '');
            }

            const response = await fetch('/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_url: videoUrl,
                    tracks: tracksData,
                    volumes: volumesData
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'فشل في التصدير');
            }

            if (result.success) {
                // تنزيل الملف
                const a = document.createElement('a');
                a.href = result.download_url;
                a.download = `فيديو_مخصص_${new Date().toLocaleDateString()}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } else {
                throw new Error(result.error || 'فشل في التصدير');
            }
        } catch (error) {
            console.error('Export error:', error);
            alert(`حدث خطأ أثناء التصدير: ${error.message}`);
        } finally {
            exportBtn.disabled = false;
            exportBtn.innerHTML = '<i class="icon-download"></i> تصدير الفيديو المخصص';
        }
    }

    document; addEventListener() { }
}