from __future__ import annotations

from pathlib import Path
from threading import Thread
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from app.utils.validation import allowed_file, parse_float, parse_int


bp = Blueprint("main", __name__)


@bp.app_errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    return jsonify({"error": "The uploaded video is larger than the configured maximum size."}), 413


@bp.get("/")
def index():
    return render_template(
        "index.html",
        max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
        allowed_extensions=sorted(current_app.config["ALLOWED_EXTENSIONS"]),
        default_confidence=current_app.config["DEFAULT_CONFIDENCE"],
        default_iou=current_app.config["DEFAULT_IOU"],
        default_image_size=current_app.config["DEFAULT_IMAGE_SIZE"],
        yolo_model=current_app.config["YOLO_MODEL"],
    )


@bp.post("/api/upload")
def upload_video():
    file = request.files.get("video")
    if not file or not file.filename:
        return jsonify({"error": "Upload a video file first."}), 400

    if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        return jsonify({"error": "Unsupported file type. Use MP4, AVI, MOV, or MKV."}), 400

    filename = secure_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    job_id = uuid4().hex
    stored_filename = f"{job_id}{suffix}"
    input_path = current_app.config["UPLOAD_FOLDER"] / stored_filename
    file.save(input_path)

    options = {
        "confidence": parse_float(
            request.form.get("confidence"),
            current_app.config["DEFAULT_CONFIDENCE"],
            0.05,
            0.95,
        ),
        "iou": parse_float(request.form.get("iou"), current_app.config["DEFAULT_IOU"], 0.1, 0.9),
        "image_size": parse_int(
            request.form.get("image_size"),
            current_app.config["DEFAULT_IMAGE_SIZE"],
            640,
            1920,
        ),
    }

    job_store = current_app.extensions["job_store"]
    processor = current_app.extensions["video_processor"]
    job_store.create(
        job_id=job_id,
        original_filename=filename,
        input_path=input_path,
        file_size=input_path.stat().st_size,
        options=options,
    )

    thread = Thread(
        target=processor.process,
        args=(job_id, input_path, filename, options),
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "job_id": job_id,
            "status_url": url_for("main.job_status", job_id=job_id),
            "message": "Upload complete. Processing has started.",
        }
    )


@bp.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    job_store = current_app.extensions["job_store"]
    payload = job_store.serialize_public(job_id)
    if payload is None:
        return jsonify({"error": "Job not found."}), 404

    if payload["status"] == "completed":
        payload["downloads"] = {
            "video": url_for("main.download_artifact", job_id=job_id, artifact="video"),
            "csv": url_for("main.download_artifact", job_id=job_id, artifact="csv"),
            "json": url_for("main.download_artifact", job_id=job_id, artifact="json"),
            "stats": url_for("main.download_artifact", job_id=job_id, artifact="stats"),
        }
        payload["processed_video_url"] = url_for("main.processed_video", job_id=job_id)

    return jsonify(payload)


@bp.get("/video/<job_id>")
def processed_video(job_id: str):
    job = current_app.extensions["job_store"].get(job_id)
    if job is None or job.status != "completed" or not job.output_video_path:
        abort(404)
    return send_file(job.output_video_path, mimetype="video/mp4", conditional=True)


@bp.get("/download/<job_id>/<artifact>")
def download_artifact(job_id: str, artifact: str):
    job = current_app.extensions["job_store"].get(job_id)
    if job is None or job.status != "completed":
        abort(404)

    artifact_paths = {
        "video": job.output_video_path,
        "csv": job.report_paths.get("csv"),
        "json": job.report_paths.get("json"),
        "stats": job.report_paths.get("stats"),
    }
    file_path = artifact_paths.get(artifact)
    if not file_path or not Path(file_path).exists():
        abort(404)

    return send_file(file_path, as_attachment=True, download_name=Path(file_path).name)
