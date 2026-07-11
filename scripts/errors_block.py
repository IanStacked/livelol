#!/usr/bin/env python3
"""Fill the SPEC-project-manifest §4 `errors` block from the sink's Query 1.

This is the seam SPEC-error-sink §9 describes: a project's `health.sh` calls
`GET /stats?project=<identity>&window=<W>` and copies `unhandled` / `handled_with_fix`
into the §4 health object. Kept as its own stdlib helper so any `health.sh` (bash) can
shell out to it without embedding curl+JSON reshaping.

Degrade, don't fail: the sink is NOT a hard dependency (SPEC §1.4). If the ref is
missing or the sink is unreachable, emit the block with `null` counts - exactly the
shape a `kind: none` project emits - so a sink outage degrades visibility without
breaking a project's health check.

    errors_block.py --project everythingdev --window 24h \
        --ref https://sink.example --token-env SINK_TOKEN
      -> {"window": "24h", "unhandled": 3, "handled_with_fix": 1}

If --ref is omitted (a `kind: none` project) or the query fails, unhandled /
handled_with_fix are null.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch_stats(
    ref: str,
    token: str,
    project: str,
    window: str,
    timeout: float = 3.0,
) -> dict:
    query = urllib.parse.urlencode({"project": project, "window": window})
    url = f"{ref.rstrip('/')}/stats?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def errors_block(project: str, window: str, ref: str | None, token: str | None) -> dict:
    block = {"window": window, "unhandled": None, "handled_with_fix": None}
    if not ref or not token:
        return block  # kind: none (or no token) -> nulls, a valid §4 object
    try:
        stats = fetch_stats(ref, token, project, window)
        block["unhandled"] = stats.get("unhandled")
        block["handled_with_fix"] = stats.get("handled_with_fix")
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        pass  # sink down -> nulls; visibility degrades, health check still succeeds
    return block


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="emit the §4 errors block from the sink")
    p.add_argument("--project", required=True)
    p.add_argument("--window", default="24h")
    p.add_argument("--ref", default=None, help="sink base URL (omit for kind: none)")
    p.add_argument(
        "--token-env",
        default="SINK_TOKEN",
        help="env var holding the bearer token",
    )
    args = p.parse_args(argv)
    token = os.environ.get(args.token_env)
    print(json.dumps(errors_block(args.project, args.window, args.ref, token)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
