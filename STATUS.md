# leaguehelper (LiveLOL) - STATUS

<!-- everythingdev:auto-continuity (auto-managed - regenerated each session; edit the sections below, not here) -->
## Continuity (auto)
- Last active: 2026-07-12T01:20:39-07:00
- Branch: `main` @ `72ced3c` "docs: update STATUS.md continuity after lp-streaks shipped to prod"
- Working tree: clean
<!-- /everythingdev:auto-continuity -->
**Phase:** Live / maintenance · **2026-07-11** · health: 🟢

## Last run
- Shipped `lp-streaks` to prod. PR #6 squash-merged to `main` (`c48bd8d`); CI pipeline green:
  test -> Docker build/push -> EC2 deploy, all 12 startup-log steps verified (bot connected as
  LiveLOL, background loop started). Adversarial-review PASS before merge.
- Verified live post-deploy: `scripts/health.sh` reports `liveness: green` (bot beating,
  connected ~27s ago).
- Merge hiccup (resolved): `gh pr merge --squash` merged on GitHub fine but couldn't fast-forward
  local `main` (it carried unpushed STATUS.md continuity commits from prior sessions), which made
  the working tree look reverted. No loss - verified `origin/main` had the code, `git reset --hard
  origin/main` re-synced. Prior sessions' local continuity commits never reaching origin is a
  recurring papercut worth watching.

## Now / in progress
- lp-streaks is live: signed win/loss streak on the tracked-user doc (from match `win`), surfaced
  in the embed as 🔥/❄️ at |streak|>=3, guarded by `last_match_id` so a no-new-game LP change (dodge)
  doesn't double-count. Of the 3 feature TODOs, flex (`non-soloduo`) was descoped and
  `dodge-update-type` deferred per user - only lp-streaks shipped.
- Nothing in progress; clean stopping point.

## Next up
- Optional: watch the next real background cycle in prod to see a 🔥/❄️ line render on a live
  update (streaks only appear once a tracked player reaches a 3-game run).
- Deferred features: `dodge-update-type` (needs investigation; `last_match_id` is now the hook for it)
  and `non-soloduo` (descoped - user doesn't want flex).
- Backlog bugs filed this session (TODO.md): `extract_match_info` UnboundLocalError, name-change log
  prints new->new, !update shows no streak. Plus earlier: untrack nested-key KeyError,
  UserNotFoundError-wrapped-as-DatabaseError, bot.py !update still raw Firestore.

## Blockers / needs me
- none
