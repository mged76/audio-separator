class FileUploader {
    constructor() {
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfo = document.getElementById('fileInfo');
        this.processBtn = document.getElementById('processBtn');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.progressPercent = document.getElementById('progressPercent');
        this.currentFile = null;

        this.initEventListeners();
    }

    initEventListeners() {
        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('dragover');
        });

        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('dragover');
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');
            this.handleFiles(e.dataTransfer.files);
        });

        this.fileInput.addEventListener('change', () => {
            this.handleFiles(this.fileInput.files);
        });

        this.processBtn.addEventListener('click', () => this.processFile());
    }

    handleFiles(files) {
        if (files.length > 0) {
            this.currentFile = files[0];
            this.showFileInfo(this.currentFile);
            this.processBtn.disabled = false;
            this.updateProgress(0, 'جاهز للفصل', '0%');
        }
    }

    showFileInfo(file) {
        this.fileInfo.innerHTML = `
            <div class="file-info-card">
                <i class="icon-file-audio"></i>
                <div class="file-details">
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${this.formatFileSize(file.size)}</span>
                </div>
            </div>
        `;
    }

    async processFile() {
        if (!this.currentFile) return;

        try {
            this.processBtn.disabled = true;
            this.processBtn.innerHTML = '<i class="icon-spinner"></i> جاري المعالجة...';

            this.updateProgress(20, 'جاري رفع الملف...', '20%');
            const uploadResponse = await this.uploadFile(this.currentFile);
            
            this.updateProgress(50, 'جاري فصل المسارات...', '50%');
            const processResponse = await this.processFileOnServer(uploadResponse.filename);
            
            this.updateProgress(100, 'اكتمل الفصل بنجاح!', '100%');
            
            setTimeout(() => {
                const videoParam = processResponse.video_url ? `video=${encodeURIComponent(processResponse.video_url)}` : '';
                const tracksParam = `tracks=${encodeURIComponent(JSON.stringify(processResponse.tracks))}`;
                window.location.href = `/results?${videoParam}&${tracksParam}`;
            }, 1000);
            
        } catch (error) {
            console.error('Error:', error);
            this.updateProgress(0, `حدث خطأ: ${error.message}`, '0%');
            this.processBtn.disabled = false;
            this.processBtn.innerHTML = '<i class="icon-cogs"></i> بدء فصل المسارات';
            alert(`حدث خطأ: ${error.message}`);
        }
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'فشل في رفع الملف');
        }

        return await response.json();
    }

    async processFileOnServer(filename) {
        const response = await fetch('/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'فشل في فصل المسارات');
        }

        return await response.json();
    }

    updateProgress(percent, text, percentText) {
        this.progressFill.style.width = `${percent}%`;
        this.progressText.textContent = text;
        this.progressPercent.textContent = percentText;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new FileUploader();
});