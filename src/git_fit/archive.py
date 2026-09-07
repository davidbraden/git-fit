"""Download, validate, and persist Garmin activity originals."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .manifest import Manifest

SUPPORTED_EXTENSIONS = {".fit", ".tcx", ".gpx"}


class Gateway(Protocol):
    def list_activities(self) -> list[dict[str, Any]]: ...

    def download_original(self, activity_id: str) -> bytes: ...


class Archive:
    """A local original-file archive backed by a JSON manifest."""

    def __init__(self, data_dir: Path, gateway: Gateway) -> None:
        self.data_dir = data_dir
        self.gateway = gateway
        self.manifest = Manifest.load(data_dir / "manifest.json")

    def run(self) -> tuple[int, int]:
        """Download incomplete activities and return (downloaded, failures)."""
        downloaded = 0
        failures = 0
        for activity in self.gateway.list_activities():
            activity_id = self._activity_id(activity)
            if activity_id is None or self.manifest.is_complete(activity_id):
                continue
            try:
                self._archive_activity(activity_id, activity)
                downloaded += 1
            except Exception as error:
                failures += 1
                self.manifest.record_failure(
                    activity_id,
                    {
                        **self._failure_metadata(activity),
                        "error": str(error),
                        "last_attempt_at": self._now(),
                    },
                )
                self.manifest.write()
                print(f"Failed {activity_id}: {error}")
        return downloaded, failures

    def status(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for entry in self.manifest.activities.values():
            status = str(entry.get("status", "unknown"))
            file_format = str(entry.get("format", "unknown"))
            key = f"{status}:{file_format}"
            result[key] = result.get(key, 0) + 1
        return result

    def _archive_activity(self, activity_id: str, activity: dict[str, Any]) -> None:
        content = self.gateway.download_original(activity_id)
        extension, payload = self._extract_original(content)
        if extension == ".fit":
            self._validate_fit(payload)
        destination = self._destination(activity_id, activity, extension)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        self.manifest.record_success(
            activity_id,
            {
                **self._metadata(activity),
                "file": str(destination.relative_to(self.data_dir)),
                "format": extension.removeprefix("."),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "downloaded_at": self._now(),
            },
        )
        self.manifest.write()

    @staticmethod
    def _extract_original(content: bytes) -> tuple[str, bytes]:
        """Extract a known activity file or preserve an unrecognised response."""
        if zipfile.is_zipfile(io.BytesIO(content)):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                files = [
                    item
                    for item in archive.infolist()
                    if not item.is_dir()
                    and Path(item.filename).suffix.lower() in SUPPORTED_EXTENSIONS
                ]
                if len(files) == 1:
                    item = files[0]
                    item_path = Path(item.filename)
                    if item_path.is_absolute() or ".." in item_path.parts:
                        raise ValueError("Unsafe path in Garmin download archive")
                    return item_path.suffix.lower(), archive.read(item)
                if len(files) > 1:
                    raise ValueError(
                        "Garmin download archive contains multiple activity files"
                    )
            return ".zip", content
        if content[:12].find(b".FIT") >= 0:
            return ".fit", content
        return ".zip", content

    @staticmethod
    def _validate_fit(payload: bytes) -> None:
        from garmin_fit_sdk import Decoder, Stream

        messages, errors = Decoder(Stream.from_byte_array(bytearray(payload))).read()
        if errors or not messages:
            raise ValueError(f"Invalid FIT file ({len(errors)} decoder errors)")

    def _destination(
        self, activity_id: str, activity: dict[str, Any], extension: str
    ) -> Path:
        started_at = self._start_time(activity)
        filename = f"{started_at.strftime('%Y-%m-%dT%H%M%SZ')}_{activity_id}{extension}"
        return self.data_dir / "activities" / str(started_at.year) / filename

    @staticmethod
    def _activity_id(activity: dict[str, Any]) -> str | None:
        raw_id = activity.get("activityId") or activity.get("activity_id")
        return str(raw_id) if raw_id is not None else None

    def _metadata(self, activity: dict[str, Any]) -> dict[str, Any]:
        return {
            "start_time": self._start_time(activity).isoformat().replace("+00:00", "Z"),
            "activity_type": self._activity_type(activity),
        }

    def _failure_metadata(self, activity: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._metadata(activity)
        except ValueError:
            return {"start_time": None, "activity_type": self._activity_type(activity)}

    @staticmethod
    def _activity_type(activity: dict[str, Any]) -> str:
        detail = activity.get("activityType")
        if isinstance(detail, dict):
            type_key = detail.get("typeKey")
            if isinstance(type_key, str):
                return type_key
        return str(activity.get("activityType", "unknown"))

    @staticmethod
    def _start_time(activity: dict[str, Any]) -> datetime:
        raw = activity.get("startTimeGMT") or activity.get("startTimeLocal")
        if not isinstance(raw, str):
            raise ValueError("Activity has no start time")
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
