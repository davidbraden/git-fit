from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from git_fit.archive import Archive


class FakeGateway:
    def __init__(
        self, activities: list[dict[str, object]], downloads: dict[str, object]
    ) -> None:
        self.activities = activities
        self.downloads = downloads
        self.downloaded_ids: list[str] = []

    def list_activities(self) -> list[dict[str, object]]:
        return self.activities

    def download_original(self, activity_id: str) -> bytes:
        self.downloaded_ids.append(activity_id)
        value = self.downloads[activity_id]
        if isinstance(value, Exception):
            raise value
        assert isinstance(value, bytes)
        return value


def activity(
    activity_id: str, start: str = "2026-09-07T08:30:00.000"
) -> dict[str, object]:
    return {
        "activityId": activity_id,
        "startTimeGMT": start,
        "activityType": {"typeKey": "running"},
    }


def zipped(name: str, payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, payload)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def validate_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Archive, "_validate_fit", staticmethod(lambda payload: None))


def test_backfill_writes_manifest_and_is_idempotent(tmp_path: Path) -> None:
    gateway = FakeGateway(
        [activity("1"), activity("2", "2025-02-01T12:00:00.000")],
        {
            "1": zipped("activity.fit", b"fit-one"),
            "2": zipped("activity.fit", b"fit-two"),
        },
    )
    archive = Archive(tmp_path, gateway)

    assert archive.run() == (2, 0)
    assert gateway.downloaded_ids == ["1", "2"]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["activities"]["1"]["status"] == "downloaded"
    assert (tmp_path / manifest["activities"]["1"]["file"]).read_bytes() == b"fit-one"

    assert Archive(tmp_path, gateway).run() == (0, 0)
    assert gateway.downloaded_ids == ["1", "2"]


def test_sync_downloads_only_new_activity(tmp_path: Path) -> None:
    first = FakeGateway([activity("1")], {"1": zipped("a.fit", b"one")})
    Archive(tmp_path, first).run()
    second = FakeGateway(
        [activity("1"), activity("2")],
        {"1": zipped("a.fit", b"one"), "2": zipped("b.fit", b"two")},
    )

    assert Archive(tmp_path, second).run() == (1, 0)
    assert second.downloaded_ids == ["2"]


def test_non_fit_original_is_preserved_and_flagged(tmp_path: Path) -> None:
    gateway = FakeGateway(
        [activity("1")], {"1": zipped("a.tcx", b"<TrainingCenterDatabase/>")}
    )
    archive = Archive(tmp_path, gateway)

    assert archive.run() == (1, 0)
    entry = archive.manifest.activities["1"]
    assert entry["format"] == "tcx"
    assert (tmp_path / entry["file"]).suffix == ".tcx"


def test_failed_activity_is_recorded_and_retried(tmp_path: Path) -> None:
    failed = FakeGateway([activity("1")], {"1": RuntimeError("offline")})
    assert Archive(tmp_path, failed).run() == (0, 1)
    assert Archive(tmp_path, failed).manifest.activities["1"]["status"] == "failed"

    recovered = FakeGateway([activity("1")], {"1": zipped("a.fit", b"ok")})
    assert Archive(tmp_path, recovered).run() == (1, 0)
    assert recovered.downloaded_ids == ["1"]


def test_malformed_activity_does_not_stop_later_downloads(tmp_path: Path) -> None:
    malformed = {"activityId": "1", "activityType": {"typeKey": "running"}}
    gateway = FakeGateway(
        [malformed, activity("2")],
        {"1": zipped("a.fit", b"one"), "2": zipped("b.fit", b"two")},
    )

    assert Archive(tmp_path, gateway).run() == (1, 1)
    assert gateway.downloaded_ids == ["1", "2"]


def test_unsafe_zip_entry_is_rejected(tmp_path: Path) -> None:
    gateway = FakeGateway([activity("1")], {"1": zipped("../activity.fit", b"bad")})
    assert Archive(tmp_path, gateway).run() == (0, 1)
    activity_dir = tmp_path / "activities"
    assert not activity_dir.exists() or not list(activity_dir.rglob("*"))


def test_status_groups_entries_by_status_and_format(tmp_path: Path) -> None:
    gateway = FakeGateway([activity("1")], {"1": zipped("a.gpx", b"gpx")})
    archive = Archive(tmp_path, gateway)
    archive.run()
    assert Archive(tmp_path, gateway).status() == {"downloaded:gpx": 1}
