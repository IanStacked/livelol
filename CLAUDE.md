# LiveLOL (leaguehelper) - project rules

> Inherits the workspace `CLAUDE.md`. Project-specific rules only.

## What this is
A Discord bot ("LiveLOL") that tracks League of Legends players' ranked progress in
real time. Users `!track` a Riot ID in their server; a background loop polls the Riot
API, writes rank/LP changes to Firestore, and posts live match-summary embeds. Runs
24/7 in Docker on AWS EC2; deployed by GitHub Actions on push to `main`.

## How to run / test
- Install toolchain: `mise install` (pins Python 3.12), then `uv sync`.
- Tests: `uv run pytest`
- Lint: `uv run ruff check` and `uv run ruff format --check`
- Run locally: `python main.py` (needs `.env` with `DISCORD_PUBLIC_KEY`,
  `RIOT_API_KEY`, `FIREBASE_CREDENTIALS_BASE64`, optional `SENTRY_DSN`, `ENV`).

## Toolchain
- Pinned in `mise.toml` (run `mise install` on a fresh checkout). Deps recorded in
  `pyproject.toml` + `uv.lock` - never install without recording (`uv add <pkg>`).

## Rules
- **Deploy on push:** pushing/merging to `main` triggers `.github/workflows/ci.yml`,
  which builds a Docker image and deploys to EC2. Do not push to `main` without an
  explicit go-ahead - land work on a branch first.
- **Secrets are gitignored and must stay that way:** `.env`, `league_bot_key.pem`,
  `serviceAccountKey.json`. Never read, print, or commit them.
- **Riot API rate limits are load-bearing:** the `await asyncio.sleep(1.5)` in the
  update loops and the 429 backoff in `utils/riot_api.py` keep the bot under Riot's
  rate curve. Don't remove them without a replacement rate strategy.
- Health check: `./scripts/health.sh` (see `PROJECT.yaml`). Error path is Sentry
  (`utils/sentry_config.py`); the everythingdev error-sink is wired dormant
  (`error_sink.kind: none`).

Always read `agent/INDEX.md` before doing anything in this repo.
