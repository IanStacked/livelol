# TODO - leaguehelper

Backlog for the notice -> record -> auto-complete pipeline. Line format:
`- [ ] (id) desc <!-- where:file:line found:DATE by:who -->`
`/complete-todos` sweeps this and auto-clears only trivial (T0/T1) items.

## Open

- [ ] (cog-error-handling) Fix/standardize error handling across all cogs <!-- where:cogs/ found:2026-07-11 by:user -->
- [ ] (mgmt-error-return-type) on_command_error annotated `-> None` but has `return await ctx.send(...)` paths returning discord.Message; make it `discord.Message | None` if a mypy/pyright/ruff-ANN tier is ever added <!-- where:cogs/management.py:17 found:2026-07-11 by:adversarial-reviewer -->
- [ ] (db-migrate-update-cmd) bot.py `!update` still queries Firestore directly (raw stream + doc.reference.update); migrate it through db_service like the cogs now do <!-- where:bot.py:109 found:2026-07-12 by:claude -->
- [ ] (untrack-del-nested-key) untrack_user/untrack_all_users do `del data["server_info.<gid>"]` on a to_dict() result, but Firestore stores that dotted path as a NESTED dict, so the flat key does not exist -> KeyError on multi-guild untrack, swallowed into a generic DatabaseError <!-- where:utils/db_service.py:102 found:2026-07-12 by:claude -->
- [ ] (untrack-usernotfound-wrapped) UserNotFoundError raised inside untrack_user is caught by the broad `except Exception` and re-wrapped as DatabaseError, so "not being tracked" surfaces as a generic DB write failure to the user <!-- where:utils/db_service.py:138 found:2026-07-12 by:claude -->
- [ ] (lp-streaks) Add LP gain streak / LP lose streak tracking <!-- where:cogs/background.py found:2026-07-11 by:user -->
- [ ] (dodge-update-type) New ranked-update type for dodges: after an LP change, check whether the match's gameStartTimestamp/gameEndTimestamp (InfoDto in MatchDto) lines up with the change; won't catch games played at 0 LP, no cheap fix that keeps API calls reasonable <!-- where:cogs/background.py found:2026-07-11 by:user -->
- [ ] (non-soloduo-matches) Handle non-solo/duo ranked matches <!-- where:cogs/background.py found:2026-07-11 by:user -->

## Done

- [x] (db-service-soc) Separation-of-concerns: db_service takes plain ids/dicts, never discord ctx/Guild objects <!-- where:utils/db_service.py found:2026-07-11 by:user done:2026-07-12 pr:refactor/db-service-soc disposition:refactor-pr -->
- [x] (db-migrate-admin) admin.py set_guild_config now goes through db_service (also fixed a latent self.bot.db / missing-await bug that silently no-op'd !updateshere) <!-- where:cogs/admin.py found:2026-07-11 by:user done:2026-07-12 pr:refactor/db-service-soc disposition:refactor-pr -->
- [x] (db-migrate-background) background.py update loop reads via get_all_tracked_users and writes via update_ranked_data; leaderboard.py read migrated too <!-- where:cogs/background.py found:2026-07-11 by:user done:2026-07-12 pr:refactor/db-service-soc disposition:refactor-pr -->
- [x] (command-type-hints) Add type hints ("typing flairs") to all commands <!-- where:cogs/ found:2026-07-11 by:user done:2026-07-11 commit:86d4fbf disposition:auto-digest -->
- [x] (remote-slug) Repoint git remote + PROJECT.yaml repo: to canonical IanStacked/livelol slug; old league-draft-prep-helper only redirects <!-- where:PROJECT.yaml:6 found:2026-07-10 by:daily-brief done:2026-07-10 disposition:auto-silent -->
- [x] (status-stale-heartbeat) Remove stale STATUS.md Next-up #1 (add Heartbeat check to ci.yml); the check already exists in the deploy log-verification <!-- where:.github/workflows/ci.yml:109 found:2026-07-10 by:daily-brief done:2026-07-10 disposition:auto-silent -->
