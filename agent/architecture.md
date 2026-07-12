# Architecture

## Overview

An always-on discord.py bot (a long-running service, not a pipeline). Command logic is
split into cogs loaded at startup; a background `tasks.loop` polls the Riot API and
pushes updates. Persistent state lives in Google Firestore. A single shared
`aiohttp.ClientSession` is used for all Riot API calls. The process runs in Docker on
AWS EC2 and is deployed by GitHub Actions.

## Component map

```
main.py
  └─ bot.py  (MyBot: intents, session, db_service)
       ├─ database.py ──────────► Firestore (tracked_users, guild_config)
       ├─ utils/sentry_config ──► Sentry.io (error/telemetry sink)
       └─ setup_hook loads cogs/:
            ├─ track.py        !track / !untrack        ─┐
            ├─ leaderboard.py  !leaderboard              │
            ├─ admin.py        !updateshere              ├─► utils/db_service (Firestore)
            ├─ background.py    background_update_task    │   utils/riot_api (Riot API)
            └─ management.py    on_command_error         ─┘   utils/ui_components (embeds/views)
```

Shared utils: `constants` (tier/rank order, region maps), `helpers` (parsing/diffing),
`ui_components` (embeds + interactive `MatchDetailsView`), `links` (op.gg/deeplol),
`logger_config`, `exceptions`.

## Data flow

Tracking a player and the live update loop:
1. User runs `!track <region> <riot_id>` → `cogs/track.py` parses region + Riot ID.
2. `utils/riot_api.get_puuid` / `get_summoner_info` / `get_ranked_info` resolve the
   player against the Riot API (platform routing for summoner, cluster for match-v5).
3. `utils/db_service.DatabaseService` writes the tracked-user doc to the
   `tracked_users` Firestore collection (keyed by PUUID, tagged with `guild_ids`).
4. `cogs/background.py background_update_task` loops: for each tracked user it fetches
   current ranked info, diffs against the stored tier/rank/LP (`utils/helpers`), and on
   a change fetches the most recent match (`get_recent_match_info`), updates the
   consecutive win/loss `streak` (only when the match id differs from the stored
   `last_match_id`, so a no-new-game LP change doesn't double-count), then writes the
   fresh tier/rank/LP + streak + last_match_id back to Firestore.
5. `utils/ui_components.MatchDetailsView` builds the embed (minimized rank delta ↔
   maximized role-sorted team breakdown) and posts it to the guild's configured
   updates channel (set via `!updateshere`, stored in `guild_config`).
6. `!leaderboard` reads `tracked_users` for the guild and renders them sorted by
   `TIER_ORDER` then `RANK_ORDER` then LP.

## Shared code

- **`utils/constants.py`** - `TIER_ORDER`, `RANK_ORDER`, `REGION_CLUSTERS`, and the
  region maps for external links. Ordering and region routing depend on it.
- **`utils/db_service.py`** - the only sanctioned Firestore access layer for league
  operations; cogs go through it rather than touching Firestore directly.
- **`utils/riot_api.py`** - all Riot API calls, with rate-limit / 429 handling and the
  typed exceptions in `utils/exceptions.py`.
- **`utils/exceptions.py`** - `LiveLOLError` hierarchy; `cogs/management.py` maps these
  to user-facing messages in `on_command_error`.

## Key constraints

- **Rate limiting is load-bearing.** `utils/riot_api.py` backs off on HTTP 429 and the
  update loops pace with `asyncio.sleep(1.5)`. Removing either risks Riot API bans.
- **Two-layer region routing.** Summoner/league endpoints use the platform (`na1`);
  match-v5 uses the regional cluster (`REGION_CLUSTERS[region]`, e.g. `americas`).
  Passing the wrong one 404s.
- **One shared aiohttp session**, created in `setup_hook` and closed in `close()`.
  Don't spin up per-request sessions.
- **Cogs are auto-discovered** from `./cogs/*.py` in `setup_hook`. A new command group
  is a new file exposing `async def setup(bot)`.

## Liveness / health

`cogs/background.py` runs a second `tasks.loop` (`heartbeat_task`, every 60s) that
writes `bot_health/heartbeat` to Firestore (`last_beat`, `connected`, `latency_ms`),
guarded so a write failure never disrupts the bot. `scripts/heartbeat_check.py` reads
that doc and maps freshness → the everythingdev §4 liveness word (green/degraded/down,
or unknown if it can't read); `scripts/health.sh` wraps it into the health JSON that
`/daily-report` and the chief-of-staff digest consume. The pure `classify_liveness`
threshold logic is unit-tested in `tests/test_heartbeat.py`.
