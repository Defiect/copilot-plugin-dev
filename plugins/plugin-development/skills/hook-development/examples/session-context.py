#!/usr/bin/env python3
"""sessionStart hook that injects a short Git summary as additional context.

Cross-platform: run it from both the `bash` and `powershell` fields of a hook entry.

Keep sessionStart hooks fast and quiet. This one emits a handful of lines and exits, and
it degrades to a single line when the workspace is not a Git worktree.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RECENT_COMMIT_COUNT = 3
GIT_TIMEOUT_SECONDS = 5


def git(cwd: Path, *args: str) -> str:
    """Run a git command, returning stripped stdout or "" on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def resolve_cwd(payload: dict[str, object]) -> Path:
    candidate = payload.get("cwd")
    if isinstance(candidate, str) and Path(candidate).is_dir():
        return Path(candidate)
    return Path.cwd()


def build_context(cwd: Path) -> str:
    lines = ["Repository context:"]

    if git(cwd, "rev-parse", "--is-inside-work-tree") != "true":
        lines.append("- Not inside a Git worktree.")
        return "\n".join(lines)

    branch = git(cwd, "branch", "--show-current") or git(cwd, "rev-parse", "--short", "HEAD")
    lines.append(f"- Branch: {branch or 'unknown'}")

    commits = git(cwd, "log", "--oneline", f"-{RECENT_COMMIT_COUNT}")
    if commits:
        lines.append("- Recent commits:")
        lines.extend(f"  - {line}" for line in commits.splitlines() if line.strip())

    return "\n".join(lines)


def main() -> int:
    raw = sys.stdin.read()
    payload: dict[str, object] = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed

    json.dump({"additionalContext": build_context(resolve_cwd(payload))}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
