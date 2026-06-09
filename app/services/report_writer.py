from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


OBJECT_COLUMNS = [
    "label",
    "category",
    "tracking_id",
    "object_number",
    "first_frame",
    "last_frame",
    "first_second",
    "last_second",
    "frames_seen",
    "avg_confidence",
    "max_confidence",
]


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def write_reports(job_id: str, result: dict, report_folder: Path) -> dict[str, str]:
    report_folder.mkdir(parents=True, exist_ok=True)

    json_path = report_folder / f"{job_id}_detection_report.json"
    csv_path = report_folder / f"{job_id}_object_tracks.csv"
    stats_path = report_folder / f"{job_id}_summary.txt"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    objects = result.get("objects", [])
    dataframe = pd.DataFrame(objects)
    if dataframe.empty:
        dataframe = pd.DataFrame(columns=OBJECT_COLUMNS)
    dataframe.to_csv(csv_path, index=False)

    lines = [
        "Object Detection Summary",
        "",
        f"Source Video: {result.get('source_filename', 'Unknown')}",
        f"Model: {result.get('model_name', 'Unknown')}",
        f"Tracker: {result.get('tracker', 'Unknown')}",
        "",
        "Total Unique Objects Detected",
        "",
    ]

    counts = result.get("counts", {})
    for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"{category.title()}: {count}")

    lines.extend(
        [
            "",
            f"Total Unique Objects: {result.get('total_unique_objects', 0)}",
            f"Average Confidence: {result.get('average_confidence', 0):.1f}%",
            f"Processing Time: {format_duration(result.get('processing_time_seconds', 0))}",
            f"Video Duration: {format_duration(result.get('video_duration_seconds', 0))}",
            f"Total Frames Processed: {result.get('total_frames_processed', 0)}",
        ]
    )

    stats_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "stats": str(stats_path),
    }
