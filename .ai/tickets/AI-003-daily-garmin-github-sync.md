# AI-003 — Daily Garmin GitHub sync

## Asked

- Run the Garmin archive sync daily with GitHub Actions while keeping archive
  data in the separate private `git-fit-data` repository.

## Decisions

- Authenticate non-interactively with Garmin email and password secrets; no
  MFA is configured for the account.
- Use a dedicated write-enabled SSH deploy key scoped to the private data
  repository rather than granting this public repository's token broader access.
- Support an empty data repository by creating `main` only after the first
  archive change.

## Changed

- Added environment-based Garmin password authentication and its tests.
- Added the daily/manual sync workflow, secure temporary credential cleanup,
  private data-repository push, and serialization of concurrent runs.
- Initialized temporary runner paths at step runtime because GitHub does not
  expose the `runner` context to a job-level environment map.
- Documented Actions secrets and deploy-key setup.
