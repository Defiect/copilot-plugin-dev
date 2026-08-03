#!/usr/bin/env python3
"""postToolUse hook that runs a formatter over files the agent just wrote.

Cross-platform: run it from both the `bash` and `powershell` fields of a hook entry.

postToolUse runs after the tool has already succeeded, so this hook cannot and must not
try to block anything. It formats what it can, stays silent, and always exits 0 — a
formatter that is not installed is not an error.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

EDIT_TOOLS = {"edit", "create", "apply_patch", "str_replace_editor", "Edit", "Write"}

PATH_KEYS = ("file_path", "filepath", "path", "target_file", "filename")

FORMAT_TIMEOUT_SECONDS = 20

# Suffix -> (executable, argv template). The path is appended unless {path} appears.
FORMATTERS: dict[str, tuple[str, list[str]]] = {
    ".go": ("gofmt", ["-w"]),
    ".rs": ("rustfmt", []),
    ".py": ("ruff", ["format", "--quiet"]),
    ".js": ("prettier", ["--write"]),
    ".jsx": ("prettier", ["--write"]),
    ".ts": ("prettier", ["--write"]),
    ".tsx": ("prettier", ["--write"]),
    ".json": ("prettier", ["--write"]),
    ".css": ("prettier", ["--write"]),
    ".scss": ("prettier", ["--write"]),
    ".html": ("prettier", ["--write"]),
    ".md": ("prettier", ["--write"]),
    ".yaml": ("prettier", ["--write"]),
    ".yml": ("prettier", ["--write"]),
}


def collect_paths(args: object) -> list[str]:
    paths: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, str) and value and value not in paths:
            paths.append(value)

    if isinstance(args, dict):
        for key in PATH_KEYS:
            add(args.get(key))
        for value in args.values():
            if isinstance(value, dict):
                for key in PATH_KEYS:
                    add(value.get(key))
    return paths


def format_file(path: Path) -> None:
    entry = FORMATTERS.get(path.suffix.lower())
    if entry is None:
        return
    executable, flags = entry
    resolved = shutil.which(executable)
    if resolved is None:
        return
    try:
        subprocess.run(
            [resolved, *flags, str(path)],
            capture_output=True,
            timeout=FORMAT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    if not isinstance(payload, dict):
        return 0

    tool = payload.get("toolName") or payload.get("tool_name") or ""
    if tool not in EDIT_TOOLS:
        return 0

    args: object = payload.get("toolArgs", payload.get("tool_input", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return 0

    for candidate in collect_paths(args):
        path = Path(candidate)
        if path.is_file():
            format_file(path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
