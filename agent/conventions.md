# Conventions

> Describe what the existing code already does - not aspirations. If the code is
> inconsistent, document the dominant pattern and note the exception.

## General principles

- Tunable values (tier/rank ordering, region maps) are module-level named constants in
  `utils/constants.py`, not inline literals.
- Cogs hold command/listener logic; Firestore access goes through
  `utils/db_service.DatabaseService`, not raw collection calls in cogs, and cogs pass
  plain values (ids, dicts) to it - never discord objects like `ctx`/`Guild`. Two
  documented exceptions still touch Firestore directly: the older `!update` in `bot.py`
  (predates the service) and `background.py`'s guarded `heartbeat_task` write (a health
  primitive, not a league operation).
- Riot API access is centralized in `utils/riot_api.py`; cogs call its functions rather
  than building HTTP requests themselves.

## Naming

- **Files:** `snake_case.py`
- **Types/Classes:** `PascalCase` (`MyBot`, `DatabaseService`, `MatchDetailsView`)
- **Functions:** `snake_case` verbs (`get_ranked_info`, `extract_match_info`)
- **Constants:** `ALL_CAPS_SNAKE` (`TRACKED_USERS_COLLECTION`, `REGION_CLUSTERS`)

## Error handling

- Domain errors use the `LiveLOLError` hierarchy in `utils/exceptions.py`
  (`RiotAPIError`, `RateLimitError`, `UserNotFoundError`, `DatabaseError`,
  `ServiceUnavailableError`, …). Raise the narrowest type.
- **Commands raise; they do not render their own error text.** A command that hits an
  error condition raises the narrowest `LiveLOLError` and lets `on_command_error` send
  the user-facing message. Commands don't catch-log-reraise (the service layer already
  logs) and don't `ctx.send` ad-hoc error strings. Input *validation* (bad region/Riot
  ID syntax) is the exception - it returns early with a guidance message.
- `cogs/management.py on_command_error` is the central handler mapping errors (and
  discord.py cooldown/permission errors) to user-facing messages.
- **The background task guards each user.** `background_update_task` wraps per-user
  processing in `try/except LiveLOLError` (log a warning, skip that user) and a broad
  `except Exception` (log with traceback), so one player's Riot/DB failure never aborts
  the whole update cycle. The rate-limit `asyncio.sleep(1.5)` pacing is preserved.
- Sentry captures `logger.error`/exceptions via `LoggingIntegration`
  (`utils/sentry_config.py`). Logging an error at ERROR level ships it to Sentry, and
  the same records mirror to the owned error sink (`utils/sink_config.py`, dual-run;
  Sentry is cut last). A record with exception info reaches the sink as unhandled.
- Prefer specific `except <Type>` over bare `except`; the codebase logs with emoji
  prefixes (✅/❌/🛑/⚠️) for scannable startup/shutdown logs.

## Testing

- Framework: `pytest` (+ `pytest-asyncio`). Tests live in `tests/`.
- Current coverage: `test_helpers.py` (parsing/diff helpers) and `test_riot_api.py`
  (Riot API client behavior, incl. rate-limit handling). Highest-value targets for new
  tests: `utils/helpers.py` diff logic and `utils/riot_api.py` error/backoff paths.
- Run: `uv run pytest`.

## Language idioms

- Async throughout: discord.py commands and Riot API calls are `async`; use `await`,
  not blocking I/O, on the bot loop.
- One shared `aiohttp.ClientSession` (`bot.session`) for all HTTP - do not create
  per-call sessions.
- Ruff enforces style (see `pyproject.toml`): line length 88, double quotes, Google
  docstring convention, import sorting.

## What to avoid

- Don't remove the Riot API pacing/backoff (rate-limit bans).
- Don't bypass `DatabaseService` for new Firestore access.
- Don't create new aiohttp sessions per request.
- Don't push to `main` casually - it deploys to production.
