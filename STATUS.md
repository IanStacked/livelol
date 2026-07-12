# leaguehelper (LiveLOL) - STATUS

<!-- everythingdev:auto-continuity (auto-managed - regenerated each session; edit the sections below, not here) -->
## Continuity (auto)
- Last active: 2026-07-12T00:34:05-07:00
- Branch: `main` @ `3df566e` "docs: update STATUS.md narrative after refactor PRs shipped"
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
- `lp-streaks` built + adversarial-review PASS on branch `feat/lp-streaks` (commit `e42a10f`,
  NOT pushed). Signed win/loss streak on the tracked-user doc, surfaced in the embed at |streak|>=3,
  guarded by `last_match_id` so a no-new-game LP change (dodge) doesn't double-count. Tests green
  (21 passed), ruff clean. Of the 3 feature TODOs the user descoped flex (`non-soloduo`) and deferred
  `dodge-update-type` for investigation - so only lp-streaks shipped this round.
- Awaiting go-ahead to open the PR (deploy-on-push to main → land via PR, not local merge).

## Next up
- On go-ahead: open PR for `feat/lp-streaks`, babysit CI (test → Docker build → EC2 deploy) to green,
  verify the streak line renders live. Rollback ready if the deploy drifts.
- Deferred features: `dodge-update-type` (needs investigation; `last_match_id` is now the hook for it)
  and `non-soloduo` (descoped - user doesn't want flex).
- Backlog bugs filed this session (TODO.md): `extract_match_info` UnboundLocalError, name-change log
  prints new->new, !update shows no streak. Plus earlier: untrack nested-key KeyError,
  UserNotFoundError-wrapped-as-DatabaseError, bot.py !update still raw Firestore.

## Blockers / needs me
- none
