from __future__ import annotations


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def parse_float(value, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def parse_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)
