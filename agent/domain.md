# Domain & Terminology

> Use these exact terms in code, comments, and commits. Consistency reduces confusion.

## Glossary

| Term | Definition |
|------|------------|
| **Riot ID** | A player's `gameName#tagLine` handle (replaced the old summoner name). Input to `!track`. |
| **PUUID** | Riot's stable, region-agnostic player ID. The primary key for a tracked user in Firestore. |
| **Region / platform** | The platform shard a summoner lives on (e.g. `na1`, `euw1`). Used for summoner/league endpoints. |
| **Cluster** | The regional routing value for match-v5 (e.g. `americas`, `europe`, `asia`). `REGION_CLUSTERS[region]`. |
| **Tier** | Ranked band: IRON … CHALLENGER (plus UNRANKED). Ordered by `TIER_ORDER`. |
| **Rank / division** | The sub-band within a tier: I–IV. Ordered by `RANK_ORDER`. |
| **LP** | League Points within a division. The finest-grained progress signal. |
| **Tracked user** | A player registered for updates in one or more guilds; a doc in `tracked_users`. |
| **Guild** | A Discord server. Guild-scoped config (updates channel) lives in `guild_config`. |
| **Cog** | A discord.py module grouping related commands/listeners (`cogs/*.py`). |
| **Heartbeat** | A `bot_health/heartbeat` Firestore doc the bot rewrites every 60s (`last_beat`, `connected`, `latency_ms`). The liveness source for `scripts/health.sh`. |

## Core business rules

- A tracked user is identified by **PUUID**; the same player tracked in multiple
  servers is one doc with multiple `guild_ids`, not duplicates.
- An update is only posted when tier, rank, **or** LP actually changed since the last
  stored value - unchanged users are skipped (see `!update` and `background_update_task`).
- Leaderboard order is **`TIER_ORDER` → `RANK_ORDER` → LP**, descending. UNRANKED sorts
  last (`TIER_ORDER = -1`).
- Live updates only post if the guild has set an updates channel with `!updateshere`;
  without it, the bot tracks silently and posts nothing automatically.
- Riot API calls must stay under rate limits: pace update loops and back off on 429.

## What this system is NOT responsible for

- Managing Riot accounts or authenticating players - it reads the public Riot API.
- Historical match analytics or coaching - it reports the most recent match summary,
  and links out to op.gg / deeplol for deep dives.
- Anything outside League of Legends ranked Solo/Duo tracking.
