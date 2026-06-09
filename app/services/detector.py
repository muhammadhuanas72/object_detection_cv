from __future__ import annotations

from threading import Lock


class YOLOModelProvider:
    def __init__(self, model_name: str, device: str | None = None):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._lock = Lock()

    def get_model(self):
        with self._lock:
            if self._model is None:
                try:
                    from ultralytics import YOLO
                except ImportError as exc:
                    raise RuntimeError(
                        "Ultralytics is not installed. Run `pip install -r requirements.txt` first."
                    ) from exc
                self._model = YOLO(self.model_name)
            return self._model
