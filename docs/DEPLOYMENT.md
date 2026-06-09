# Deployment Guide

VisionTrack AI can run on CPU-only hosts with the default fast model. For larger accuracy-first models such as YOLO11x or YOLOv8x, use a GPU VPS or GPU-enabled container platform when possible.

## Environment Variables

```text
SECRET_KEY=replace-with-a-long-random-secret
MAX_UPLOAD_MB=512
YOLO_MODEL=yolo11n.pt
YOLO_DEVICE=
YOLO_TRACKER=bytetrack.yaml
YOLO_MAX_DETECTIONS=200
DEFAULT_CONFIDENCE=0.4
DEFAULT_IOU=0.5
DEFAULT_IMAGE_SIZE=640
```

Set `YOLO_DEVICE=0` for the first CUDA GPU. Leave it empty for automatic selection or CPU fallback.

## Render

1. Push the project to GitHub.
2. Create a new Render Web Service.
3. Use Python as the runtime.
4. Set the build command:

```bash
pip install -r requirements.txt
```

5. Set the start command:

```bash
gunicorn run:app --bind 0.0.0.0:$PORT --timeout 1200 --workers 1 --threads 4
```

6. Add the environment variables above.
7. Use a persistent disk for `storage/` if you need artifacts to survive restarts.

Render CPU instances will process large videos slowly. Keep `MAX_UPLOAD_MB` conservative unless you attach persistent storage and increase timeouts.

## Railway

1. Create a Railway project from the GitHub repository.
2. Railway can use the included `Procfile`.
3. Add the environment variables in Railway Variables.
4. Configure a volume mounted at the project `storage/` directory if processed artifacts must persist.
5. Increase service timeout limits if your plan supports it.

Recommended start command if overriding the `Procfile`:

```bash
gunicorn run:app --bind 0.0.0.0:$PORT --timeout 1200 --workers 1 --threads 4
```

## VPS

Install system packages:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg nginx
```

Create the app environment:

```bash
git clone <your-repo-url> visiontrack-ai
cd visiontrack-ai
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Run Gunicorn:

```bash
gunicorn run:app --bind 127.0.0.1:8000 --timeout 1200 --workers 1 --threads 4
```

Example systemd service:

```ini
[Unit]
Description=VisionTrack AI
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/visiontrack-ai
EnvironmentFile=/opt/visiontrack-ai/.env
ExecStart=/opt/visiontrack-ai/.venv/bin/gunicorn run:app --bind 127.0.0.1:8000 --timeout 1200 --workers 1 --threads 4
Restart=always

[Install]
WantedBy=multi-user.target
```

Example Nginx reverse proxy:

```nginx
server {
    listen 80;
    server_name example.com;

    client_max_body_size 512M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 1200;
        proxy_send_timeout 1200;
    }
}
```

## GPU Deployment Notes

For NVIDIA GPU hosts, install a CUDA-compatible PyTorch build before `ultralytics` if the default package selection does not detect CUDA:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

Then set:

```text
YOLO_DEVICE=0
```

## Scaling Roadmap

For production workloads with many simultaneous users:

- Replace in-memory job storage with Redis or PostgreSQL.
- Move processing into Celery, RQ, or a dedicated worker service.
- Store videos and reports in S3-compatible object storage.
- Add authenticated users and per-user artifact access.
- Add cleanup jobs for old uploads and reports.
- Fine-tune YOLO on domain-specific footage for stronger precision and recall.
