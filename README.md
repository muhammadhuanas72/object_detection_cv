# VisionTrack AI

Full-stack computer vision web app for uploaded-video object detection, object tracking, unique object counting, and annotated video previews.

The app uses Flask, OpenCV, Ultralytics YOLO, ByteTrack, Pandas, and Tailwind CSS.

## Features

- Drag-and-drop video upload for MP4, AVI, MOV, and MKV.
- Server-side maximum file size validation.
- YOLO object detection with simple fast defaults.
- ByteTrack object tracking to preserve identities across frames.
- Unique object counting by category using `(class, tracking_id)` pairs.
- Annotated MP4 output with bounding boxes, class labels, confidence scores, and IDs.
- Live processing progress and partial counts while the video is analyzed.
- Simple live count panel with total unique objects and per-category counts.
- Backend-generated processed video, CSV, JSON, and text reports remain available through the API, while the website stays focused on upload, status, preview, and counts.
- Light responsive UI.

## Project Structure

```text
.
├── app/
│   ├── routes.py
│   ├── job_store.py
│   ├── services/
│   │   ├── detector.py
│   │   ├── report_writer.py
│   │   └── video_processor.py
│   └── utils/
│       └── validation.py
├── static/
│   ├── css/styles.css
│   └── js/app.js
├── templates/index.html
├── storage/
│   ├── uploads/
│   ├── outputs/
│   └── reports/
├── config.py
├── run.py
├── requirements.txt
└── docs/DEPLOYMENT.md
```

## Installation

Use Python 3.10 or 3.11. A GPU environment is recommended for larger YOLO models, but the default setup uses a faster model for easier local testing.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy the example environment file and edit values as needed:

```powershell
Copy-Item .env.example .env
```

Run the app:

```powershell
python run.py
```

Open `http://127.0.0.1:5000`.

The first detection run may download the configured YOLO weights, such as `yolo11n.pt`. If your environment cannot download model weights at runtime, place the model file in the project root and set `YOLO_MODEL` to that local path.

## Accuracy Settings

The default configuration prioritizes faster local testing:

- `YOLO_MODEL=yolo11n.pt`
- `DEFAULT_CONFIDENCE=0.4`
- `DEFAULT_IOU=0.5`
- `DEFAULT_IMAGE_SIZE=640`
- `YOLO_TRACKER=bytetrack.yaml`

For higher accuracy, use a larger model:

```text
YOLO_MODEL=yolo11x.pt
DEFAULT_IMAGE_SIZE=1280
```

Actual accuracy depends on camera angle, resolution, lighting, motion blur, object size, occlusion, and whether the objects are well represented in the model's training data. For domain-specific surveillance, retail, traffic, or crowd-counting deployments, fine-tuning on representative labeled footage is the best path to consistently exceed 90 percent precision/recall.

## API

Upload and start processing:

```http
POST /api/upload
```

Form fields:

- `video`: uploaded file
- `confidence`: optional float between `0.05` and `0.95`
- `iou`: optional float between `0.10` and `0.90`
- `image_size`: optional integer between `640` and `1920`

Poll status:

```http
GET /api/jobs/<job_id>
```

Download artifacts:

```http
GET /download/<job_id>/video
GET /download/<job_id>/csv
GET /download/<job_id>/json
GET /download/<job_id>/stats
```

## Production Notes

This implementation is intentionally modular and production-oriented, but background threads and local disk storage are best for single-instance deployments. For high-volume production workloads, move processing to a queue such as Celery/RQ, store artifacts in S3-compatible object storage, and persist job records in PostgreSQL or Redis.

Use one Gunicorn worker unless you add a shared queue and model pool. Multiple workers each load their own YOLO model, which can exhaust memory quickly.
