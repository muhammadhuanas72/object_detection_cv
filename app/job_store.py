from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    original_filename: str
    input_path: str
    file_size: int
    options: dict[str, Any]
    status: str = "queued"
    progress: int = 0
    message: str = "Queued for processing"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    output_video_path: str | None = None
    report_paths: dict[str, str] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    def __init__(self):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def create(
        self,
        job_id: str,
        original_filename: str,
        input_path: Path,
        file_size: int,
        options: dict[str, Any],
    ) -> JobRecord:
        job = JobRecord(
            job_id=job_id,
            original_filename=original_filename,
            input_path=str(input_path),
            file_size=file_size,
            options=options,
        )
        with self._lock:
            self._jobs[job_id] = job
        return deepcopy(job)

    def update(self, job_id: str, **changes: Any) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in changes.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = utc_now()
            return deepcopy(job)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def serialize_public(self, job_id: str) -> dict[str, Any] | None:
        job = self.get(job_id)
        if job is None:
            return None
        payload = asdict(job)
        payload.pop("input_path", None)
        payload.pop("output_video_path", None)
        payload.pop("report_paths", None)
        return payload
