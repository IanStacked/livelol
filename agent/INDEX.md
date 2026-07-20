# Agent Index

> Read this file first. Pull only the files relevant to your current task -
> do not read everything upfront.

## What this project does

LiveLOL is a Discord bot that tracks League of Legends players' ranked progress in
real time for a Discord server ("guild"). A server member registers a player with
`!track <region> <riot_id>`; a background loop polls the Riot API on an interval,
detects rank/LP changes, persists them to Firestore, and posts a match-summary embed
(with a toggle between a minimized rank update and a full role-sorted team breakdown)
to the guild's configured updates channel. It also serves an on-demand
`!leaderboard`. Runs 24/7 in Docker on AWS EC2.

## Project structure

| Path | Purpose |
|------|---------|
| `bot.py` | Bot bootstrap: `MyBot`, env/Sentry/DB init, cog loader, the `!update` command |
| `main.py` | Entrypoint - calls `bot_startup()` |
| `database.py` | Firebase/Firestore init; collection-name constants |
| `cogs/` | discord.py command groups: `track`, `leaderboard`, `admin`, `background`, `management` |
| `utils/` | Riot API client, DB service, helpers, UI components, constants, logging, Sentry, exceptions, external links |
| `tests/` | pytest suite (`test_helpers.py`, `test_riot_api.py`) |
| `scripts/health.sh` | everythingdev health check (health JSON); see `PROJECT.yaml` |
| `.github/workflows/` | CI (pytest) + deploy (Docker build → EC2) + Ruff lint |

## Task routing - read only what your task needs

| Task | Read |
|------|------|
| Understand the data flow end-to-end | `architecture.md` |
| Fix a bug in ranked tracking / match display | `domain.md` → `architecture.md` |
| Add or modify a command | `architecture.md` (cog pattern) → `conventions.md` |
| Change Riot API handling / rate limiting | `domain.md` → `architecture.md` (Key constraints) |
| Write or review code style | `conventions.md` |
| Unsure what a term means (PUUID, cluster, tier) | `domain.md` |
| Wondering why something was built a certain way | `decisions/_index.md` |

## Hard constraints - know these before touching any code

- **Secrets are gitignored - never commit them:** `.env`, `league_bot_key.pem`,
  `serviceAccountKey.json`. Credentials reach the bot via environment variables only.
- **Push to `main` deploys to production.** `ci.yml` builds a Docker image and
  redeploys the EC2 container on every push to `main`. Branch first.
- **Respect Riot API rate limits.** The `asyncio.sleep(1.5)` pacing in the update
  loops and the 429 backoff in `utils/riot_api.py` are load-bearing, not optional.
- **Region is two-layered:** platform routing (e.g. `na1`) vs. regional cluster
  (e.g. `americas`) - see `utils/constants.py` `REGION_CLUSTERS`. Use the right one
  per Riot endpoint or calls 404.
- Update the relevant files in the `agent/` directory after task completion.
