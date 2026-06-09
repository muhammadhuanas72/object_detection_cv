from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from app.services.detector import YOLOModelProvider
from app.services.report_writer import write_reports

try:
    import cv2
except ImportError:
    cv2 = None


class VideoProcessor:
    def __init__(
        self,
        job_store,
        output_folder: Path,
        report_folder: Path,
        model_name: str,
        device: str | None,
        tracker: str,
        max_detections: int,
    ):
        self.job_store = job_store
        self.output_folder = output_folder
        self.report_folder = report_folder
        self.model_name = model_name
        self.device = device
        self.tracker = tracker
        self.max_detections = max_detections
        self.model_provider = YOLOModelProvider(model_name=model_name, device=device)

    def process(self, job_id: str, input_path: Path, original_filename: str, options: dict[str, Any]):
        start_time = time.perf_counter()
        self.job_store.update(
            job_id,
            status="processing",
            progress=1,
            message="Loading detection model",
        )

        try:
            if cv2 is None:
                raise RuntimeError("OpenCV is not installed. Run `pip install -r requirements.txt` first.")

            model = self.model_provider.get_model()
            metadata = self._read_video_metadata(input_path)
            fps = metadata["fps"]
            total_frames = metadata["frame_count"]
            video_duration = metadata["duration_seconds"]

            output_path = self.output_folder / f"{job_id}_annotated.mp4"
            raw_output_path = self.output_folder / f"{job_id}_annotated_raw.mp4"
            writer = None

            track_registry: dict[str, dict[str, Any]] = {}
            category_sequence = defaultdict(int)
            timeline_buckets = defaultdict(lambda: defaultdict(set))
            detection_confidence_sum = 0.0
            detection_events = 0

            conf_threshold = options["confidence"]
            iou_threshold = options["iou"]
            image_size = options["image_size"]

            print(f"Processing started: {job_id}")

            stream = model.track(
                source=str(input_path),
                stream=True,
                tracker=self.tracker,
                conf=conf_threshold,
                iou=iou_threshold,
                imgsz=image_size,
                max_det=self.max_detections,
                device=self.device,
                persist=False,
                verbose=False,
            )

            frames_processed = frame_index

            if frame_index % 50 == 0:
                print(f"Processed {frame_index} frames")

            for frame_index, result in enumerate(stream, start=1):
                frame = result.orig_img.copy()

                if writer is None:
                    height, width = frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(str(raw_output_path), fourcc, fps, (width, height))
                    if not writer.isOpened():
                        raise RuntimeError("Could not initialize video writer for annotated output.")

                boxes = result.boxes
                if boxes is not None and len(boxes) > 0:
                    xyxy = boxes.xyxy.cpu().numpy()
                    class_ids = boxes.cls.cpu().numpy().astype(int)
                    confidences = boxes.conf.cpu().numpy()
                    track_ids = self._extract_track_ids(boxes, len(xyxy))

                    for box, class_id, confidence, track_id in zip(
                        xyxy, class_ids, confidences, track_ids
                    ):
                        class_name = self._class_name(result.names, class_id)
                        confidence_value = float(confidence)
                        label = self._register_detection(
                            registry=track_registry,
                            category_sequence=category_sequence,
                            timeline_buckets=timeline_buckets,
                            class_name=class_name,
                            track_id=track_id,
                            confidence=confidence_value,
                            frame_index=frame_index,
                            fps=fps,
                        )

                        if label:
                            detection_confidence_sum += confidence_value
                            detection_events += 1
                            label_text = f"{label} {confidence_value * 100:.1f}%"
                        else:
                            label_text = f"{class_name.title()} {confidence_value * 100:.1f}%"

                        self._draw_detection(frame, box, label_text, class_name)

                writer.write(frame)
                frames_processed = frame_index

                if total_frames and (frame_index == total_frames or frame_index % 5 == 0):
                    progress = min(95, 5 + int((frame_index / total_frames) * 90))
                    partial_result = self._build_partial_result(
                        job_id=job_id,
                        original_filename=original_filename,
                        metadata=metadata,
                        frames_processed=frame_index,
                        track_registry=track_registry,
                        average_confidence=(
                            detection_confidence_sum / detection_events * 100
                            if detection_events
                            else 0.0
                        ),
                        processing_time_seconds=time.perf_counter() - start_time,
                    )
                    print(f"Completed processing job {job_id}")
                    self.job_store.update(
                        job_id,
                        progress=progress,
                        message=f"Processing frame {frame_index:,} of {total_frames:,}",
                        result=partial_result,
                    )

            if writer is None:
                raise RuntimeError("No frames were found in the uploaded video.")
            writer.release()
            writer = None

            self.job_store.update(
                job_id,
                progress=97,
                message="Preparing video preview",
            )
            browser_video_path = self._prepare_browser_video(raw_output_path, output_path)

            result = self._build_result(
                job_id=job_id,
                original_filename=original_filename,
                options=options,
                metadata=metadata,
                frames_processed=frames_processed,
                track_registry=track_registry,
                timeline_buckets=timeline_buckets,
                average_confidence=(
                    detection_confidence_sum / detection_events * 100
                    if detection_events
                    else 0.0
                ),
                processing_time_seconds=time.perf_counter() - start_time,
            )
            report_paths = write_reports(job_id, result, self.report_folder)

            self.job_store.update(
                job_id,
                status="completed",
                progress=100,
                message="Processing complete",
                output_video_path=str(browser_video_path),
                report_paths=report_paths,
                result=result,
            )
            
        except Exception as exc:
            traceback.print_exc()

            if "writer" in locals() and writer is not None:
               writer.release()

            self.job_store.update(
                job_id,
                status="failed",
                progress=100,
                message="Processing failed",
                error=f"{type(exc).__name__}: {exc}",
            )

    def _prepare_browser_video(self, raw_output_path: Path, output_path: Path) -> Path:
        ffmpeg_path = self._find_ffmpeg()
        if ffmpeg_path is None:
            if raw_output_path != output_path:
                shutil.copyfile(raw_output_path, output_path)
            return output_path

        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(raw_output_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(output_path),
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                return output_path
        except (OSError, subprocess.CalledProcessError):
            pass

        if raw_output_path != output_path:
            shutil.copyfile(raw_output_path, output_path)
        return output_path

    def _find_ffmpeg(self) -> str | None:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path

        try:
            import imageio_ffmpeg
        except ImportError:
            return None

        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    def _read_video_metadata(self, input_path: Path) -> dict[str, Any]:
        capture = cv2.VideoCapture(str(input_path))
        if not capture.isOpened():
            raise RuntimeError("Could not open the uploaded video.")

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        capture.release()

        if fps <= 0:
            fps = 30.0

        return {
            "frame_count": frame_count,
            "fps": fps,
            "width": width,
            "height": height,
            "duration_seconds": frame_count / fps if frame_count else 0.0,
        }

    def _extract_track_ids(self, boxes, count: int) -> list[int | None]:
        if boxes.id is None:
            return [None] * count
        ids = boxes.id.cpu().numpy()
        return [int(track_id) if track_id is not None and track_id >= 0 else None for track_id in ids]

    def _class_name(self, names: dict[int, str] | list[str], class_id: int) -> str:
        if isinstance(names, dict):
            return str(names.get(class_id, class_id)).replace("_", " ")
        if 0 <= class_id < len(names):
            return str(names[class_id]).replace("_", " ")
        return str(class_id)

    def _register_detection(
        self,
        registry: dict[str, dict[str, Any]],
        category_sequence,
        timeline_buckets,
        class_name: str,
        track_id: int | None,
        confidence: float,
        frame_index: int,
        fps: float,
    ) -> str | None:
        if track_id is None:
            return None

        key = f"{class_name}:{track_id}"
        if key not in registry:
            category_sequence[class_name] += 1
            object_number = category_sequence[class_name]
            registry[key] = {
                "label": f"{class_name.title()} #{object_number}",
                "category": class_name,
                "tracking_id": track_id,
                "object_number": object_number,
                "first_frame": frame_index,
                "last_frame": frame_index,
                "first_second": round((frame_index - 1) / fps, 2),
                "last_second": round((frame_index - 1) / fps, 2),
                "frames_seen": 0,
                "confidence_sum": 0.0,
                "max_confidence": 0.0,
            }

        object_record = registry[key]
        object_record["last_frame"] = frame_index
        object_record["last_second"] = round((frame_index - 1) / fps, 2)
        object_record["frames_seen"] += 1
        object_record["confidence_sum"] += confidence
        object_record["max_confidence"] = max(object_record["max_confidence"], confidence)

        bucket = int((frame_index - 1) / fps)
        timeline_buckets[bucket][class_name].add(object_record["label"])
        return object_record["label"]

    def _build_result(
        self,
        job_id: str,
        original_filename: str,
        options: dict[str, Any],
        metadata: dict[str, Any],
        frames_processed: int,
        track_registry: dict[str, dict[str, Any]],
        timeline_buckets,
        average_confidence: float,
        processing_time_seconds: float,
    ) -> dict[str, Any]:
        objects = []
        for record in track_registry.values():
            frames_seen = max(record["frames_seen"], 1)
            objects.append(
                {
                    "label": record["label"],
                    "category": record["category"],
                    "tracking_id": record["tracking_id"],
                    "object_number": record["object_number"],
                    "first_frame": record["first_frame"],
                    "last_frame": record["last_frame"],
                    "first_second": record["first_second"],
                    "last_second": record["last_second"],
                    "frames_seen": record["frames_seen"],
                    "avg_confidence": round(record["confidence_sum"] / frames_seen * 100, 2),
                    "max_confidence": round(record["max_confidence"] * 100, 2),
                }
            )

        objects.sort(key=lambda item: (item["category"], item["object_number"]))
        counts = Counter(item["category"] for item in objects)
        most_frequent = {"category": None, "count": 0}
        if counts:
            category, count = counts.most_common(1)[0]
            most_frequent = {"category": category, "count": count}

        timeline = self._serialize_timeline(
            timeline_buckets=timeline_buckets,
            categories=sorted(counts.keys()),
            duration_seconds=metadata["duration_seconds"],
        )

        return {
            "job_id": job_id,
            "source_filename": original_filename,
            "model_name": self.model_name,
            "tracker": self.tracker,
            "options": options,
            "counts": dict(sorted(counts.items())),
            "total_unique_objects": sum(counts.values()),
            "most_frequent_object": most_frequent,
            "average_confidence": round(average_confidence, 2),
            "processing_time_seconds": round(processing_time_seconds, 2),
            "video_duration_seconds": round(metadata["duration_seconds"], 2),
            "fps": round(metadata["fps"], 2),
            "video_width": metadata["width"],
            "video_height": metadata["height"],
            "total_frames_processed": frames_processed,
            "timeline": timeline,
            "objects": objects,
        }

    def _build_partial_result(
        self,
        job_id: str,
        original_filename: str,
        metadata: dict[str, Any],
        frames_processed: int,
        track_registry: dict[str, dict[str, Any]],
        average_confidence: float,
        processing_time_seconds: float,
    ) -> dict[str, Any]:
        counts = Counter(record["category"] for record in track_registry.values())
        most_frequent = {"category": None, "count": 0}
        if counts:
            category, count = counts.most_common(1)[0]
            most_frequent = {"category": category, "count": count}
        return {
            "job_id": job_id,
            "source_filename": original_filename,
            "counts": dict(sorted(counts.items())),
            "total_unique_objects": sum(counts.values()),
            "most_frequent_object": most_frequent,
            "average_confidence": round(average_confidence, 2),
            "processing_time_seconds": round(processing_time_seconds, 2),
            "video_duration_seconds": round(metadata["duration_seconds"], 2),
            "total_frames_processed": frames_processed,
            "timeline": [],
            "objects": [],
            "is_partial": True,
        }

    def _serialize_timeline(self, timeline_buckets, categories: list[str], duration_seconds: float):
        last_bucket = max(timeline_buckets.keys(), default=-1)
        expected_buckets = max(last_bucket + 1, math.ceil(duration_seconds))
        timeline = []
        for second in range(expected_buckets):
            row = {"second": second, "total": 0}
            for category in categories:
                count = len(timeline_buckets[second].get(category, set()))
                row[category] = count
                row["total"] += count
            timeline.append(row)
        return timeline

    def _draw_detection(self, frame, box, label: str, class_name: str):
        x1, y1, x2, y2 = [int(value) for value in box]
        height, width = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width - 1, x2), min(height - 1, y2)

        color = self._color_for_class(class_name)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        label_y = y1 - 8 if y1 - text_height - 12 > 0 else y1 + text_height + 12
        background_top = max(0, label_y - text_height - 8)
        background_bottom = min(height - 1, label_y + baseline - 2)
        background_right = min(width - 1, x1 + text_width + 12)

        cv2.rectangle(
            frame,
            (x1, background_top),
            (background_right, background_bottom),
            color,
            -1,
        )
        cv2.putText(frame, label, (x1 + 6, label_y - 4), font, font_scale, (255, 255, 255), thickness)

    def _color_for_class(self, class_name: str) -> tuple[int, int, int]:
        digest = hashlib.sha256(class_name.encode("utf-8")).digest()
        return (
            70 + digest[0] % 150,
            70 + digest[1] % 150,
            70 + digest[2] % 150,
        )
