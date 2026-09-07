from __future__ import annotations

import stat
from pathlib import Path

from git_fit.garmin import secure_token_store


def test_token_store_permissions_are_owner_only(tmp_path: Path) -> None:
    token_file = tmp_path / "tokens" / "garmin_tokens.json"
    token_file.parent.mkdir()
    token_file.write_text("secret", encoding="utf-8")

    secure_token_store(token_file)

    assert stat.S_IMODE(token_file.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
