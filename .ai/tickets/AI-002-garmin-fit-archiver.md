# AI-002 — Garmin FIT archiver

## Asked
- Build a personal Garmin Connect archiver that backfills activity originals and
  downloads new activities on later manual runs.

## Decisions
- Use Python 3.12, `uv`, and the unofficial read-only `garminconnect` client;
  Garmin does not offer a self-service personal download API.
- Keep state in a small atomic JSON manifest rather than SQLite because the
  expected archive contains fewer than 1,000 activities.
- Retain non-FIT original uploads such as TCX and GPX, while identifying them
  clearly in the manifest.
- Store persistent Garmin tokens locally with owner-only permissions; never
  save the Garmin password.

## Changed
- Added the `git-fit` CLI with `backfill`, `sync`, and `status` commands.
- Added archive, authentication, FIT validation, manifest, and mocked test
  coverage plus reproducible `uv` project tooling.
- Added setup and recovery documentation and ignored personal archive/token data.
