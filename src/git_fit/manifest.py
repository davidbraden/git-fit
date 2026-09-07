"""Persistent, human-readable archive state."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MANIFEST_VERSION = 1


class ManifestError(ValueError):
    """Raised when the manifest cannot safely be used."""


class Manifest:
    """An activity-ID keyed JSON manifest."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.activities: dict[str, dict[str, Any]] = {}

    @classmethod
    def load(cls, path: Path) -> Manifest:
        manifest = cls(path)
        if not path.exists():
            return manifest
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ManifestError(f"Cannot read manifest {path}: {error}") from error
        if not isinstance(raw, Mapping) or raw.get("version") != MANIFEST_VERSION:
            raise ManifestError(f"Unsupported manifest format in {path}")
        activities = raw.get("activities")
        if not isinstance(activities, dict):
            raise ManifestError(f"Manifest activities must be an object in {path}")
        manifest.activities = activities
        return manifest

    def is_complete(self, activity_id: str) -> bool:
        return self.activities.get(activity_id, {}).get("status") == "downloaded"

    def record_success(self, activity_id: str, entry: dict[str, Any]) -> None:
        self.activities[activity_id] = {"status": "downloaded", **entry}

    def record_failure(self, activity_id: str, entry: dict[str, Any]) -> None:
        self.activities[activity_id] = {"status": "failed", **entry}

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": MANIFEST_VERSION, "activities": self.activities},
            indent=2,
            sort_keys=True,
        ) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent, text=True
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

