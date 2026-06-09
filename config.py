import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")

    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "512"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}

    UPLOAD_FOLDER = BASE_DIR / "storage" / "uploads"
    OUTPUT_FOLDER = BASE_DIR / "storage" / "outputs"
    REPORT_FOLDER = BASE_DIR / "storage" / "reports"

    YOLO_MODEL = os.getenv("YOLO_MODEL", "yolo11n.pt")
    YOLO_DEVICE = os.getenv("YOLO_DEVICE") or None
    YOLO_TRACKER = os.getenv("YOLO_TRACKER", "bytetrack.yaml")
    YOLO_MAX_DETECTIONS = int(os.getenv("YOLO_MAX_DETECTIONS", "200"))

    DEFAULT_CONFIDENCE = float(os.getenv("DEFAULT_CONFIDENCE", "0.4"))
    DEFAULT_IOU = float(os.getenv("DEFAULT_IOU", "0.5"))
    DEFAULT_IMAGE_SIZE = int(os.getenv("DEFAULT_IMAGE_SIZE", "640"))

    JOB_RETENTION_HOURS = int(os.getenv("JOB_RETENTION_HOURS", "24"))
