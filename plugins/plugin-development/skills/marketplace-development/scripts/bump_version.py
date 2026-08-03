#!/usr/bin/env python3
"""Bump a plugin.json semver and matching marketplace entries."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def dumps(data: Any) -> str:
    return json.dumps(data, indent=2) + "\n"


def bump(version: str, args: argparse.Namespace) -> str:
    match = SEMVER_RE.match(version)
    if not match:
        raise ValueError(f"version must be plain semver X.Y.Z: {version!r}")
    major, minor, patch = [int(part) for part in match.groups()]
    if args.set_version:
        if not SEMVER_RE.match(args.set_version):
            raise ValueError(f"--set must be plain semver X.Y.Z: {args.set_version!r}")
        return args.set_version
    if args.major:
        return f"{major + 1}.0.0"
    if args.minor:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def print_diff(path: Path, before: str, after: str) -> None:
    if before == after:
        return
    for line in difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path),
    ):
        print(line, end="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump plugin.json and matching marketplace entry versions.")
    parser.add_argument("plugin_json", help="path to plugin.json")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--major", action="store_true", help="bump major and reset minor/patch")
    choice.add_argument("--minor", action="store_true", help="bump minor and reset patch")
    choice.add_argument("--patch", action="store_true", help="bump patch")
    choice.add_argument("--set", dest="set_version", help="set an exact X.Y.Z version")
    parser.add_argument("--marketplace", action="append", default=[], help="marketplace.json to update; repeatable")
    parser.add_argument("--dry-run", action="store_true", help="print unified diffs without writing")
    args = parser.parse_args(argv)

    plugin_path = Path(args.plugin_json).expanduser().resolve()
    if not plugin_path.is_file():
        print(f"error: plugin.json not found: {plugin_path}", file=sys.stderr)
        return 2

    try:
        plugin = load_json(plugin_path)
        # ValueError (not TypeError) is intentional: these guard parsed JSON content, not call
        # arguments, and the local handler below reports them alongside bump()'s ValueError.
        if not isinstance(plugin, dict) or not isinstance(plugin.get("name"), str):
            raise ValueError("plugin.json must be an object with a string name")  # noqa: TRY004
        if not isinstance(plugin.get("version"), str):
            raise ValueError("plugin.json must contain a string version")  # noqa: TRY004
        new_version = bump(plugin["version"], args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    changes: list[tuple[Path, str, str]] = []
    before = dumps(plugin)
    plugin["version"] = new_version
    changes.append((plugin_path, before, dumps(plugin)))

    for raw_marketplace in args.marketplace:
        marketplace_path = Path(raw_marketplace).expanduser().resolve()
        if not marketplace_path.is_file():
            print(f"error: marketplace not found: {marketplace_path}", file=sys.stderr)
            return 2
        try:
            marketplace = load_json(marketplace_path)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not isinstance(marketplace, dict) or not isinstance(marketplace.get("plugins"), list):
            print(f"error: marketplace must have a plugins array: {marketplace_path}", file=sys.stderr)
            return 2
        before_marketplace = dumps(marketplace)
        for entry in marketplace["plugins"]:
            if isinstance(entry, dict) and entry.get("name") == plugin["name"]:
                entry["version"] = new_version
        changes.append((marketplace_path, before_marketplace, dumps(marketplace)))

    if args.dry_run:
        for path, before_text, after_text in changes:
            print_diff(path, before_text, after_text)
    else:
        for path, _, after_text in changes:
            path.write_text(after_text, encoding="utf-8")
        print(f"Set {plugin['name']} to version {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
