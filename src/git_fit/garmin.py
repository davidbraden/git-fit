"""Read-only adapter around the unofficial Garmin Connect client."""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Any


class GarminGateway:
    """Expose only the Garmin operations used by the archiver."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    def login(cls, email: str | None, token_file: Path) -> GarminGateway:
        """Authenticate with saved tokens when possible, otherwise prompt safely."""
        from garminconnect import Garmin  # type: ignore[import-untyped]

        account_email = email or os.environ.get("GARMIN_EMAIL") or input(
            "Garmin email: "
        ).strip()
        if not account_email:
            raise ValueError("A Garmin email is required")

        secure_token_store(token_file)

        def prompt_mfa() -> str:
            return input("Garmin MFA code: ").strip()

        def authenticate(password: str | None) -> Any:
            client = Garmin(account_email, password, prompt_mfa=prompt_mfa)
            client.login(str(token_file))
            secure_token_store(token_file)
            return client

        if token_file.exists():
            try:
                return cls(authenticate(None))
            except Exception as error:
                print(
                    "Saved Garmin tokens could not be used "
                    f"({error}); logging in again."
                )
        return cls(authenticate(getpass.getpass("Garmin password: ")))

    def list_activities(self) -> list[dict[str, Any]]:
        """Return every activity from Garmin's paginated endpoint."""
        activities: list[dict[str, Any]] = []
        start = 0
        page_size = 100
        while True:
            page = self._client.get_activities(start, page_size)
            if isinstance(page, dict):
                page = page.get("activityList", [])
            if not isinstance(page, list):
                raise RuntimeError("Garmin returned an unexpected activity list")
            activities.extend(item for item in page if isinstance(item, dict))
            if len(page) < page_size:
                return activities
            start += len(page)

    def download_original(self, activity_id: str) -> bytes:
        """Return Garmin's original activity download payload."""
        from garminconnect import Garmin

        content = self._client.download_activity(
            activity_id, Garmin.ActivityDownloadFormat.ORIGINAL
        )
        if not isinstance(content, bytes):
            raise RuntimeError("Garmin returned a non-binary activity download")
        return content


def secure_token_store(token_file: Path) -> None:
    """Ensure a local token path cannot be read by other users."""
    token_file.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(token_file.parent, 0o700)
    if token_file.exists():
        os.chmod(token_file, 0o600)
