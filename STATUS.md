# leaguehelper (LiveLOL) - STATUS

**Phase:** Live / maintenance · **2026-07-10** · health: 🟢

## Last run
- Onboarded the repo to everythingdev standards (STATUS.md, project CLAUDE.md,
  mise.toml, agent/ knowledge base, adversarial-review Stop-hook gate, PROJECT.yaml +
  scripts/health.sh, daily-reports/ + bubble-ups/). Error handling unchanged - Sentry
  stays the live path; the error-sink is wired dormant (`kind: none`). Work is on
  branch `chore/everythingdev-onboarding`, not yet pushed (push to main deploys).

## Now / in progress
- Onboarding branch ready for review. A real liveness heartbeat is now wired: the bot
  writes `bot_health/heartbeat` to Firestore every 60s (`cogs/background.py`), and
  `scripts/health.sh` reads it via `scripts/heartbeat_check.py`. Verified live against
  Firestore - reports `down` today because the *deployed* bot predates this code; it
  flips to `green` once the branch is deployed.

## Next up
1. Review the onboarding branch, then merge to `main` when ready (this triggers the
   EC2 deploy pipeline - merge deliberately). After deploy, health flips to green.

## Blockers / needs me
- Merge-to-main is a live production deploy; hold until you explicitly want to ship.
