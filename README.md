# git-fit

`git-fit` creates a local archive of the original activity files in a Garmin
Connect account. It is intended for a personal account and uses the unofficial
[`garminconnect`](https://github.com/cyberjunky/python-garminconnect) client.
Garmin can change those private endpoints without notice.

## Setup

Install [uv](https://docs.astral.sh/uv/), then run commands from this directory.
`uv` downloads the Python 3.12 runtime required by the Garmin client.

```sh
uv sync --group dev
export GARMIN_EMAIL='you@example.com'
uv run git-fit backfill
```

On the first run, the command prompts for a Garmin password and, when enabled,
an MFA code. Passwords are never written to disk or accepted as command-line
arguments. Garmin refresh tokens are stored locally in
`.git-fit/garmin_tokens.json`; treat this file like a password.

## Commands

```sh
uv run git-fit backfill
uv run git-fit sync
uv run git-fit status
```

`backfill` and `sync` are safe to re-run. Both list the account's activities;
they download only activities that are missing or previously failed. `sync` is
deliberately manual and does not install a background job.

Optional paths and email can be supplied explicitly:

```sh
uv run git-fit sync --data-dir /path/to/archive --token-file /path/to/tokens.json --email you@example.com
```

## Archive layout and recovery

```
garmin-data/
  activities/2026/2026-09-07T083000Z_123456789.fit
  manifest.json
```

`manifest.json` is the only sync state and is written atomically after every
completed activity. It records the Garmin ID, metadata, original format,
checksum, path, and download status. FIT files are validated before being marked
complete. If Garmin's original upload was GPX or TCX, that original is retained
and explicitly marked as non-FIT. A failed item is retried by the next command.

The archive directory and `.git-fit/` are ignored by Git. Back up
`garmin-data/`; do not share the token directory.

## Daily GitHub Actions sync

The included GitHub Actions workflow can archive the account daily at 06:00 UTC
and also supports manual runs from the Actions tab. It writes activity files and
`manifest.json` directly to the private
[`davidbraden/git-fit-data`](https://github.com/davidbraden/git-fit-data)
repository. It does not commit Garmin credentials, tokens, or archive data to
this public repository.

Before enabling the workflow, create the private `git-fit-data` repository and
create a dedicated deploy key for it:

```sh
ssh-keygen -t ed25519 -C git-fit-data-actions -f git-fit-data-actions
```

Add `git-fit-data-actions.pub` to the private repository under **Settings →
Deploy keys**, with **Allow write access** enabled. Then add these Actions
secrets to this public repository under **Settings → Secrets and variables →
Actions**:

- `DATA_REPO_DEPLOY_KEY`: the complete contents of `git-fit-data-actions`
- `GARMIN_EMAIL`: the Garmin account email address
- `GARMIN_PASSWORD`: the Garmin account password

The data repository may be empty: the first successful sync creates its `main`
branch and initial archive commit. The action logs in with the email and
password on every run; its saved Garmin token is temporary and discarded when
the runner exits.

## Development

```sh
uv run pytest
uv run ruff check .
uv run mypy src
```
