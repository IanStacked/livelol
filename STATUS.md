# leaguehelper (LiveLOL) - STATUS

<!-- everythingdev:auto-continuity (auto-managed - regenerated each session; edit the sections below, not here) -->
## Continuity (auto)
- Last active: 2026-07-11T23:24:39-07:00
- Branch: `chore/complete-todos-2026-07-11` @ `2f0c14f` "docs: update STATUS.md narrative after complete-todos sweep"
- Working tree: clean
<!-- /everythingdev:auto-continuity -->
**Phase:** Live / maintenance · **2026-07-11** · health: 🟢

## Last run
- Merged everythingdev onboarding + the liveness heartbeat to `main` (squash `80375f6`)
  and deployed. CI pipeline green: test -> Docker build/push -> EC2 deploy, bot booted
  and connected as LiveLOL. Adversarial-review PASS (proposer tier T1) before merge.
- Verified live post-deploy: `scripts/health.sh` reports `liveness: green` (bot beating,
  connected ~54s ago). The heartbeat loop end-to-end works: bot writes
  `bot_health/heartbeat` to Firestore every 60s; health.sh reads it via
  `scripts/heartbeat_check.py`.

## Now / in progress
- Both refactor TODOs shipped to prod. Merged + deployed green (bot live): PR #3 cog type
  hints, PR #4 db_service SoC + raw-Firestore migration out of cogs, PR #5 standardized cog
  error handling. Also fixed 3 real bugs (silent !updateshere no-op, Sentry double-log, one
  bad player aborting the whole update cycle). Local main synced/clean.
- User asked to HOLD before starting any feature work.

## Next up
- On go-ahead, start the 3 remaining feature TODOs, `lp-streaks` first (most self-contained):
  plan a design + confirm decisions before coding. Then `dodge-update-type` (author flagged:
  no cheap impl) and `non-soloduo-matches`.
- Also filed for later: `untrack` nested-key KeyError, UserNotFoundError-wrapped-as-DatabaseError,
  bot.py !update still raw Firestore (see TODO.md).

## Blockers / needs me
- none
