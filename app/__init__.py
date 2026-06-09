from flask import Flask

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    for folder in (
        app.config["UPLOAD_FOLDER"],
        app.config["OUTPUT_FOLDER"],
        app.config["REPORT_FOLDER"],
    ):
        folder.mkdir(parents=True, exist_ok=True)

    from app.job_store import JobStore
    from app.services.video_processor import VideoProcessor

    job_store = JobStore()
    app.extensions["job_store"] = job_store
    app.extensions["video_processor"] = VideoProcessor(
        job_store=job_store,
        output_folder=app.config["OUTPUT_FOLDER"],
        report_folder=app.config["REPORT_FOLDER"],
        model_name=app.config["YOLO_MODEL"],
        device=app.config["YOLO_DEVICE"],
        tracker=app.config["YOLO_TRACKER"],
        max_detections=app.config["YOLO_MAX_DETECTIONS"],
    )

    from app.routes import bp

    app.register_blueprint(bp)
    return app
