from __future__ import annotations

from pathlib import Path

import pytest

from git_fit.manifest import Manifest, ManifestError


def test_invalid_manifest_does_not_replace_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ManifestError):
        Manifest.load(path)
    assert path.read_text(encoding="utf-8") == "{invalid"


def test_manifest_write_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    manifest = Manifest.load(path)
    manifest.record_success("1", {"format": "fit"})
    manifest.write()
    assert Manifest.load(path).activities["1"]["status"] == "downloaded"

