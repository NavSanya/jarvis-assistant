import csv
from datetime import datetime
from pathlib import Path

from app.schemas import WellnessSampleOut


DEFAULT_WELLNESS_SAMPLE_PATH = Path("demo/wellness_signals.csv")


def _clean(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def _parse_timestamp(raw_value: str | None) -> datetime | None:
    value = _clean(raw_value)
    if value is None:
        return None
    return datetime.fromisoformat(value.replace(" ", "T"))


def _parse_int(raw_value: str | None) -> int | None:
    value = _clean(raw_value)
    if value is None:
        return None
    return int(value)


def _parse_float(raw_value: str | None) -> float | None:
    value = _clean(raw_value)
    if value is None:
        return None
    return float(value)


def load_wellness_samples(
    path: Path = DEFAULT_WELLNESS_SAMPLE_PATH,
) -> list[WellnessSampleOut]:
    if not path.exists():
        return []

    samples: list[WellnessSampleOut] = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):
            samples.append(
                WellnessSampleOut(
                    timestamp=_parse_timestamp(row.get("timestamp")),
                    heart_rate=_parse_int(row.get("heart_rate_bpm")),
                    hrv_rmssd_ms=_parse_int(row.get("heart_rate_variability_ms")),
                    skin_temperature_c=_parse_float(row.get("skin_temperature_C")),
                    stress_level=_clean(row.get("stress_score")),
                    source=f"{path.as_posix()}:{row_number}",
                    suggested_emotion=_clean(row.get("suggested_emotion")),
                )
            )
    return samples

