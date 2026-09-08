from __future__ import annotations

import stat
from pathlib import Path

import pytest

from git_fit import garmin
from git_fit.garmin import secure_token_store


def test_token_store_permissions_are_owner_only(tmp_path: Path) -> None:
    token_file = tmp_path / "tokens" / "garmin_tokens.json"
    token_file.parent.mkdir()
    token_file.write_text("secret", encoding="utf-8")

    secure_token_store(token_file)

    assert stat.S_IMODE(token_file.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600


def test_password_environment_variable_avoids_interactive_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GARMIN_PASSWORD", "from-environment")
    monkeypatch.setattr(
        garmin.getpass,
        "getpass",
        lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
    )

    assert garmin._password_for_login() == "from-environment"


def test_password_prompts_when_environment_variable_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    monkeypatch.setattr(garmin.getpass, "getpass", lambda prompt: "interactive")

    assert garmin._password_for_login() == "interactive"
