# One-shot project onboarding prompt

After running `./init-project.sh <project> --agent` (which copies the `agent/` scaffold,
a `CLAUDE.md`, and a `STATUS.md` in), open that project in Claude Code and paste
**everything between the rule lines** below. It analyzes the repo and fills the scaffold
in one pass.

---

You are bootstrapping this repository's agent knowledge base. A scaffold was just copied
in: a `CLAUDE.md`, a `STATUS.md`, and an `agent/` directory (and possibly a project Stop
hook under `.claude/`). Turn the placeholders into an accurate, project-specific knowledge
base. Work from evidence in the codebase - never invent.

## Step 0 - Inventory
- Read `CLAUDE.md`, `STATUS.md`, and every file under `agent/`.
- Read any existing `README`, `package.json` / `pyproject.toml` / `go.mod` / `Cargo.toml`,
  and the top-level directory layout to understand the language, build, and shape.
- If `.claude/hooks/stop_hook.sh` exists, read it - you'll configure `WATCH_DIRS` in Step 2.

## Step 1 - Map the codebase before writing anything
- Identify the real source directories, the entry points, and the module/package boundaries.
- Trace the primary data/control flow end to end: input → processing stages → output.
- Note hard structural rules you can infer (layering, import directions, "X must not depend
  on Y"). These become the "hard constraints."
- Build this from the code. If something is genuinely ambiguous, leave a clearly-marked
  `<!-- TODO: confirm with maintainer -->` rather than inventing.

## Step 2 - Configure the project Stop hook (only if `.claude/hooks/stop_hook.sh` exists)
- Set `WATCH_DIRS` to the space-separated source dirs from Step 1 (e.g. `"src"` or `"src lib"`).
- Leave `KNOWLEDGE_DIR=agent` and `ENABLE_AUTOCOMMIT=false` unless the user asked otherwise.
- `chmod +x .claude/hooks/*`.
- Smoke-test it without tripping it from your own shell line - pipe a built payload, e.g.
  write a tiny temp file with a `{"tool_name":...}` JSON and feed it via stdin.

## Step 3 - Fill the knowledge base
Replace every `<PLACEHOLDER>` and every `<!-- guidance -->` comment. Match the template
structure exactly; it encodes the intended discipline. Leave the two `_template.md` files
(`decisions/decisions__template.md`, `packages/_template.md`) untouched.
- **`agent/INDEX.md`** - the router: a one-paragraph summary, a structure table, a
  **task→file routing table**, and the hard constraints from Step 1. It points at other
  files; it does not duplicate them.
- **`agent/domain.md`** - glossary (exact names from the code), core business rules, and an
  explicit "what this system is NOT responsible for" list.
- **`agent/architecture.md`** - component map, end-to-end data flow as numbered steps,
  shared code, and key structural constraints.
- **`agent/conventions.md`** - naming, error handling, testing, idioms. Describe what the
  code already does, not your preferences.
- **`agent/overview.md`** - one or two Mermaid diagrams. If diagrams add little, delete the
  file and remove its mentions from INDEX.md.
- **`agent/packages/<name>.md`** - copy `_template.md` once per significant package and fill it.

## Step 4 - Seed decisions sparingly
Leave `agent/decisions/_index.md` near-empty. Only write a decision file for a choice whose
rationale is genuinely non-obvious *and* visible in the code. Do not manufacture ADRs.

## Step 5 - Verify and report
- Confirm no `<PLACEHOLDER>` / guidance comments remain (except in the `_template.md` files).
- Grep to confirm any constraint you asserted is actually true (if you wrote "A must not
  import B," check it doesn't).
- Summarize: files filled, `WATCH_DIRS` chosen, any `TODO: confirm` markers, hook status.

Do not commit anything unless the user asks. Surface assumptions; flag anything you were
unsure about instead of silently guessing.

---
