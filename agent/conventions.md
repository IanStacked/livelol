# Conventions

> Describe what the existing code already does - not aspirations. If the code is
> inconsistent, document the dominant pattern and note the exception.

## General principles

- Tunable values (tier/rank ordering, region maps) are module-level named constants in
  `utils/constants.py`, not inline literals.
- Cogs hold command/listener logic; Firestore access goes through
  `utils/db_service.DatabaseService`, not raw collection calls in cogs (the older
  `!update` in `bot.py` predates this and still queries Firestore directly).
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
- `cogs/management.py on_command_error` is the central handler mapping errors (and
  discord.py cooldown/permission errors) to user-facing messages.
- Sentry captures `logger.error`/exceptions via `LoggingIntegration`
  (`utils/sentry_config.py`). Logging an error at ERROR level ships it to Sentry.
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
