#!/bin/bash
# OPT-IN project Stop hook - adversarial review GATE (deterministic, no LLM).
#
# Wire as a PROJECT Stop hook (init-project.sh --review). It refuses to let a turn
# end while there is uncommitted work that has not passed adversarial review, and
# feeds the author agent a reason telling it to dispatch the `adversarial-reviewer`
# subagent. It NEVER calls an LLM and NEVER commits - the reviewer subagent does
# both. This hook only ENFORCES that a review happened.
#
# Division of labour (keep it this way - it is what makes the loop flat, not nested):
#   - THIS hook: deterministic gate. Clean tree -> allow. Dirty tree -> block until a
#     PASS lands, or escalate to the human after MAX_ROUNDS failed rounds.
#   - reviewer subagent (.claude/agents/adversarial-reviewer.md): does the LLM work.
#     On PASS it commits (tree goes clean -> gate allows). On FAIL it bumps the round
#     counter in $STATE and hands file:line reasons back to the author to fix.
#
# Round counter lives in .claude/.review-state (gitignored). A clean tree clears it;
# a PASS commit clears it; delete it by hand to let the reviewer retry after an
# escalation.
#
# Mutually exclusive with the heuristic autocommit in stop_hook.sh: pick one Stop
# hook per project. Here the reviewer owns the commit, so its message is LLM-written.
# -- Per-project configuration -----------------------------------------------
MAX_ROUNDS=3
REVIEWER_AGENT="adversarial-reviewer"
# ----------------------------------------------------------------------------
set -uo pipefail

# Fail open: a broken gate must never wedge a session.
command -v python3 >/dev/null 2>&1 || { echo '{}'; exit 0; }

PROJ="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJ" 2>/dev/null || { echo '{}'; exit 0; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo '{}'; exit 0; }

STATE="$PROJ/.claude/.review-state"

# Nothing uncommitted (tracked edits + staged + untracked) -> nothing to review.
# A clean tree is the PASS/committed state, so allow and reset the counter.
DIRTY="$(git status --porcelain 2>/dev/null)"
if [ -z "$DIRTY" ]; then
    rm -f "$STATE" 2>/dev/null || true
    echo '{}'
    exit 0
fi

ROUND=0
[ -f "$STATE" ] && ROUND="$(tr -cd '0-9' < "$STATE" 2>/dev/null)"
[ -n "$ROUND" ] || ROUND=0

# Escalation: too many FAIL rounds without a PASS -> stop looping, hand to human.
# Do NOT clear $STATE here, so subsequent stops keep handing back instead of
# silently re-entering the loop.
if [ "$ROUND" -ge "$MAX_ROUNDS" ]; then
    python3 - "$MAX_ROUNDS" <<'PY'
import json, sys
print(json.dumps({"systemMessage": (
    "Adversarial review reached the %s-round cap without a PASS. Loop stopped - "
    "the diff is handed back to you to resolve manually (or delete "
    ".claude/.review-state to let the reviewer try again)." % sys.argv[1]
)}))
PY
    exit 0
fi

# Default: block the turn and tell the author to dispatch a fresh reviewer.
python3 - "$REVIEWER_AGENT" "$ROUND" "$MAX_ROUNDS" <<'PY'
import json, sys
agent, rnd, mx = sys.argv[1], int(sys.argv[2]), sys.argv[3]
print(json.dumps({"decision": "block", "reason": (
    "BLOCKED: uncommitted changes have not passed adversarial review.\n\n"
    "Dispatch the `%s` subagent (attempt %d of %s). Hand it the user's ORIGINAL "
    "request VERBATIM plus the diff. It must RUN the project's tests/build and then "
    "either:\n"
    "  - PASS: write a commit message and commit (a clean tree clears this gate), or\n"
    "  - FAIL: record file:line reasons for you to fix, then you re-run it.\n\n"
    "Do not commit these changes yourself, and do not let the reviewer edit code - "
    "it judges, you fix." % (agent, rnd + 1, mx)
)}))
PY
