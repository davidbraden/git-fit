"""Command-line interface for git-fit."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .archive import Archive
from .garmin import GarminGateway
from .manifest import ManifestError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive original Garmin activity files."
    )
    parser.add_argument(
        "command", choices=("backfill", "sync", "status"), help="operation to run"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("garmin-data"))
    parser.add_argument(
        "--token-file", type=Path, default=Path(".git-fit/garmin_tokens.json")
    )
    parser.add_argument("--email", help="Garmin email; defaults to GARMIN_EMAIL")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "status":
            archive = Archive(args.data_dir, gateway=_UnusedGateway())
            counts = archive.status()
            if not counts:
                print("No archived activities.")
            for label, count in sorted(counts.items()):
                print(f"{label}: {count}")
            return 0
        gateway = GarminGateway.login(args.email, args.token_file)
        archive = Archive(args.data_dir, gateway)
        downloaded, failures = archive.run()
        print(f"Downloaded: {downloaded}; failed: {failures}")
        return 1 if failures else 0
    except (ManifestError, OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}")
        return 1


class _UnusedGateway:
    """Prevent status from accidentally making network calls."""

    def list_activities(self) -> list[dict[str, object]]:
        raise AssertionError("status must not list activities")

    def download_original(self, activity_id: str) -> bytes:
        raise AssertionError("status must not download activities")


if __name__ == "__main__":
    raise SystemExit(main())
