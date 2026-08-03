#!/usr/bin/env python3
"""Add or update a plugin entry in a GitHub Copilot CLI marketplace manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PLUGIN_MANIFEST_LOCATIONS = (
    ".plugin/plugin.json",
    "plugin.json",
    ".github/plugin/plugin.json",
    ".claude-plugin/plugin.json",
)
COPY_FIELDS = (
    "name",
    "description",
    "version",
    "author",
    "license",
    "keywords",
    "category",
    "tags",
    "homepage",
    "repository",
)


def find_plugin_manifest(plugin_dir: Path) -> Path | None:
    for relative in PLUGIN_MANIFEST_LOCATIONS:
        candidate = plugin_dir / relative
        if candidate.is_file():
            return candidate
    return None


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def marketplace_root(manifest: Path) -> Path:
    parts = manifest.parts
    suffixes = (
        ((".github", "plugin", "marketplace.json"), 3),
        ((".plugin", "marketplace.json"), 2),
        ((".claude-plugin", "marketplace.json"), 2),
        (("marketplace.json",), 1),
    )
    for suffix, count in suffixes:
        if tuple(parts[-len(suffix) :]) == suffix:
            root = manifest
            for _ in range(count):
                root = root.parent
            return root
    return manifest.parent


def relative_source(root: Path, plugin_path: Path) -> str:
    rel = os.path.relpath(plugin_path.resolve(), root.resolve()).replace(os.sep, "/")
    if not rel.startswith("."):
        rel = "./" + rel
    return rel


def build_entry(plugin_manifest: dict[str, Any], source: str | dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    for field in COPY_FIELDS:
        if field in plugin_manifest:
            entry[field] = plugin_manifest[field]
    entry["source"] = source
    return entry


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add or update an entry in marketplace.json.")
    parser.add_argument("--marketplace", required=True, help="path to marketplace.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plugin-path", help="local plugin directory; source is written as a relative path")
    group.add_argument("--repo", help="GitHub OWNER/REPO for a source object")
    parser.add_argument("--ref", help="Git ref for --repo source objects")
    parser.add_argument("--path", help="plugin path inside --repo, or local metadata path when it exists")
    parser.add_argument("--force", action="store_true", help="overwrite an existing entry with the same name")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    marketplace_path = Path(args.marketplace).expanduser().resolve()
    if not marketplace_path.is_file():
        print(f"error: marketplace file not found: {marketplace_path}", file=sys.stderr)
        return 2

    try:
        marketplace = load_json(marketplace_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(marketplace, dict) or not isinstance(marketplace.get("plugins"), list):
        print("error: marketplace must be an object with a plugins array", file=sys.stderr)
        return 2

    root = marketplace_root(marketplace_path)
    try:
        if args.plugin_path:
            plugin_dir = Path(args.plugin_path).expanduser().resolve()
            plugin_manifest_path = find_plugin_manifest(plugin_dir)
            if plugin_manifest_path is None:
                print(f"error: no plugin.json found under {plugin_dir}", file=sys.stderr)
                return 2
            plugin_manifest = load_json(plugin_manifest_path)
            source: str | dict[str, Any] = relative_source(root, plugin_dir)
        else:
            metadata_dir = Path(args.path).expanduser().resolve() if args.path and Path(args.path).exists() else None
            if metadata_dir is None:
                print(
                    "error: --repo mode needs --path pointing at a local plugin directory "
                    "so plugin.json can populate metadata",
                    file=sys.stderr,
                )
                return 2
            plugin_manifest_path = find_plugin_manifest(metadata_dir)
            if plugin_manifest_path is None:
                print(f"error: no plugin.json found under {metadata_dir}", file=sys.stderr)
                return 2
            plugin_manifest = load_json(plugin_manifest_path)
            source_obj: dict[str, Any] = {"source": "github", "repo": args.repo}
            if args.ref:
                source_obj["ref"] = args.ref
            source_obj["path"] = plugin_manifest.get("name", ".") if args.path is None else args.path
            source = source_obj
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not isinstance(plugin_manifest, dict) or not isinstance(plugin_manifest.get("name"), str):
        print("error: plugin.json must be an object with a string name", file=sys.stderr)
        return 2

    entry = build_entry(plugin_manifest, source)
    name = entry["name"]
    plugins: list[Any] = marketplace["plugins"]
    for index, existing in enumerate(plugins):
        if isinstance(existing, dict) and existing.get("name") == name:
            if not args.force:
                print(f"error: entry {name!r} already exists; pass --force to replace it", file=sys.stderr)
                return 1
            plugins[index] = entry
            write_json(marketplace_path, marketplace)
            print(f"Updated {name} in {marketplace_path}")
            return 0

    plugins.append(entry)
    write_json(marketplace_path, marketplace)
    print(f"Added {name} to {marketplace_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
