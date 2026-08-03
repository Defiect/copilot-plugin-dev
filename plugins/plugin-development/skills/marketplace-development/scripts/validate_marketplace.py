#!/usr/bin/env python3
"""Validate a GitHub Copilot CLI marketplace manifest.

Accepts either a marketplace.json file path or a repository root. Repository roots are
searched using Copilot CLI's marketplace discovery order.

Exit codes:
    0  no errors (warnings may be present)
    1  one or more errors, or warnings with --warnings-as-errors
    2  the path or manifest could not be found or parsed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

MANIFEST_LOCATIONS = (
    "marketplace.json",
    ".plugin/marketplace.json",
    ".github/plugin/marketplace.json",
    ".claude-plugin/marketplace.json",
)
PLUGIN_MANIFEST_LOCATIONS = (
    ".plugin/plugin.json",
    "plugin.json",
    ".github/plugin/plugin.json",
    ".claude-plugin/plugin.json",
)

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+].*)?$")

KNOWN_TOP_KEYS = {"name", "owner", "plugins", "metadata"}
KNOWN_OWNER_KEYS = {"name", "email"}
KNOWN_METADATA_KEYS = {"description", "version", "pluginRoot"}
KNOWN_ENTRY_KEYS = {
    "name",
    "source",
    "description",
    "version",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "category",
    "tags",
    "commands",
    "agents",
    "skills",
    "hooks",
    "mcpServers",
    "lspServers",
    "strict",
}
KNOWN_SOURCE_KEYS = {"source", "repo", "url", "ref", "path", "sha"}
KNOWN_AUTHOR_KEYS = {"name", "email", "url"}
BRANCH_REFS = {"main", "master"}


class Report:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []
        self.notes: list[tuple[str, str]] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append((where, message))

    def warn(self, where: str, message: str) -> None:
        self.warnings.append((where, message))

    def note(self, where: str, message: str) -> None:
        self.notes.append((where, message))

    @property
    def ok(self) -> bool:
        return not self.errors


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def render(report: Report, target: Path, quiet: bool) -> None:
    color = _supports_color()

    def paint(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

    print(f"Validating marketplace: {target}")
    for where, message in report.errors:
        print(f"  {paint('ERROR', '31;1')}  {where}: {message}")
    for where, message in report.warnings:
        print(f"  {paint('WARN ', '33;1')}  {where}: {message}")
    if not quiet:
        for where, message in report.notes:
            print(f"  {paint('note ', '36')}  {where}: {message}")

    print()
    summary = f"{len(report.errors)} error(s), {len(report.warnings)} warning(s), {len(report.notes)} note(s)"
    if report.ok and not report.warnings:
        print(paint(f"PASS  {summary}", "32;1"))
    elif report.ok:
        print(paint(f"PASS with warnings  {summary}", "33;1"))
    else:
        print(paint(f"FAIL  {summary}", "31;1"))


def find_marketplace(path: Path) -> tuple[Path | None, Path | None]:
    """Return (manifest_path, repository_root)."""
    if path.is_file():
        manifest = path.resolve()
        root = _root_for_manifest(manifest)
        return manifest, root
    if path.is_dir():
        root = path.resolve()
        for relative in MANIFEST_LOCATIONS:
            candidate = root / relative
            if candidate.is_file():
                return candidate, root
    return None, None


def _root_for_manifest(manifest: Path) -> Path:
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


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except OSError as exc:
        return None, f"cannot read file: {exc}"


def find_plugin_manifest(plugin_dir: Path) -> Path | None:
    for relative in PLUGIN_MANIFEST_LOCATIONS:
        candidate = plugin_dir / relative
        if candidate.is_file():
            return candidate
    return None


def check_string(report: Report, where: str, field: str, value: Any) -> bool:
    if not isinstance(value, str):
        report.error(where, f"`{field}` must be a string, got {type(value).__name__}")
        return False
    return True


def check_string_array(report: Report, where: str, field: str, value: Any) -> None:
    if not isinstance(value, list):
        report.error(where, f"`{field}` must be an array of strings")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str):
            report.error(where, f"`{field}[{index}]` must be a string")


def validate_marketplace(manifest_path: Path, repo_root: Path) -> Report:
    report = Report()
    raw, error = load_json(manifest_path)
    manifest_rel = _display_path(manifest_path, repo_root)
    if error:
        report.error(manifest_rel, error)
        return report
    if not isinstance(raw, dict):
        report.error(manifest_rel, "marketplace manifest must be a JSON object")
        return report

    manifest = raw
    for key in manifest:
        if key not in KNOWN_TOP_KEYS:
            report.warn(manifest_rel, f"`{key}` is not a recognized marketplace.json field")

    _validate_top_level(report, manifest, manifest_rel, repo_root)
    return report


def _validate_top_level(report: Report, manifest: dict[str, Any], where: str, repo_root: Path) -> None:
    name = manifest.get("name")
    if name is None:
        report.error(where, "`name` is required")
    elif check_string(report, where, "name", name):
        if not NAME_RE.match(name):
            report.error(where, f"`name` must be kebab-case: got {name!r}")
        if len(name) > 64:
            report.error(where, f"`name` exceeds 64 characters ({len(name)})")

    owner = manifest.get("owner")
    if owner is None:
        report.error(where, "`owner` is required")
    elif not isinstance(owner, dict):
        report.error(where, "`owner` must be an object")
    else:
        for key in owner:
            if key not in KNOWN_OWNER_KEYS:
                report.warn(where, f"`owner.{key}` is not a recognized owner field")
        if "name" not in owner:
            report.error(where, "`owner.name` is required")
        elif check_string(report, where, "owner.name", owner["name"]) and not owner["name"].strip():
            report.error(where, "`owner.name` must not be empty")
        if "email" in owner:
            check_string(report, where, "owner.email", owner["email"])

    metadata = manifest.get("metadata")
    if metadata is not None:
        _validate_metadata(report, metadata, where, repo_root)

    plugins = manifest.get("plugins")
    if plugins is None:
        report.error(where, "`plugins` is required")
    elif not isinstance(plugins, list):
        report.error(where, "`plugins` must be an array")
    else:
        seen: dict[str, str] = {}
        for index, entry in enumerate(plugins):
            entry_where = f"plugins[{index}]"
            if not isinstance(entry, dict):
                report.error(entry_where, "plugin entry must be an object")
                continue
            _validate_entry(report, entry, entry_where, repo_root, seen)
        report.note(where, f"{len(plugins)} plugin entr(ies)")


def _validate_metadata(report: Report, metadata: Any, where: str, repo_root: Path) -> None:
    if not isinstance(metadata, dict):
        report.error(where, "`metadata` must be an object")
        return
    for key in metadata:
        if key not in KNOWN_METADATA_KEYS:
            report.warn(where, f"`metadata.{key}` is not a recognized metadata field")
    for field in ("description", "version", "pluginRoot"):
        if field in metadata and not isinstance(metadata[field], str):
            report.error(where, f"`metadata.{field}` must be a string")
    if isinstance(metadata.get("version"), str) and not SEMVER_RE.match(metadata["version"]):
        report.warn(where, f"`metadata.version` is not semver: {metadata['version']!r}")
    plugin_root = metadata.get("pluginRoot")
    if isinstance(plugin_root, str):
        resolved = (repo_root / plugin_root).resolve()
        if not _inside_or_equal(repo_root, resolved):
            report.error(where, "`metadata.pluginRoot` must stay inside the marketplace repository")
        elif not resolved.is_dir():
            report.warn(where, f"`metadata.pluginRoot` does not resolve to a directory: {plugin_root}")
        else:
            report.note(where, f"metadata.pluginRoot resolves to {resolved.relative_to(repo_root).as_posix()}")


def _validate_entry(
    report: Report,
    entry: dict[Any, Any],
    where: str,
    repo_root: Path,
    seen: dict[str, str],
) -> None:
    for key in entry:
        if key not in KNOWN_ENTRY_KEYS:
            report.warn(where, f"`{key}` is not a recognized plugin entry field")

    name = entry.get("name")
    if name is None:
        report.error(where, "`name` is required")
    elif check_string(report, where, "name", name):
        if not NAME_RE.match(name):
            report.error(where, f"`name` must be kebab-case: got {name!r}")
        if name in seen:
            report.error(where, f"duplicate plugin name {name!r} (also defined by {seen[name]})")
        else:
            seen[name] = where

    if "description" not in entry:
        report.warn(where, "`description` is missing; users see it when browsing the marketplace")
    elif check_string(report, where, "description", entry["description"]) and len(entry["description"]) > 1024:
        report.error(where, f"`description` exceeds 1024 characters ({len(entry['description'])})")

    if "version" not in entry:
        report.warn(where, "`version` is missing; users cannot reason about releases")
    elif check_string(report, where, "version", entry["version"]) and not SEMVER_RE.match(entry["version"]):
        report.warn(where, f"`version` is not semver: {entry['version']!r}")

    _validate_optional_entry_fields(report, entry, where)

    source = entry.get("source")
    if source is None:
        report.error(where, "`source` is required")
        return
    plugin_manifest = _validate_source(report, source, where, repo_root)
    if plugin_manifest is not None:
        _compare_plugin_metadata(report, entry, where, plugin_manifest)


def _validate_optional_entry_fields(report: Report, entry: dict[str, Any], where: str) -> None:
    for field in ("homepage", "repository", "license", "category"):
        if field in entry:
            check_string(report, where, field, entry[field])
    for field in ("keywords", "tags"):
        if field in entry:
            check_string_array(report, where, field, entry[field])
    if "author" in entry:
        author = entry["author"]
        if not isinstance(author, dict):
            report.error(where, "`author` must be an object")
        else:
            if "name" not in author:
                report.error(where, "`author.name` is required when `author` is present")
            for key in author:
                if key not in KNOWN_AUTHOR_KEYS:
                    report.warn(where, f"`author.{key}` is not a recognized author field")
    if "strict" in entry and not isinstance(entry["strict"], bool):
        report.error(where, "`strict` must be a boolean")


def _validate_source(report: Report, source: Any, where: str, repo_root: Path) -> Path | None:
    if isinstance(source, str):
        return _validate_relative_source(report, source, where, repo_root)
    if not isinstance(source, dict):
        report.error(where, "`source` must be a relative path string or an object")
        return None

    for key in source:
        if key not in KNOWN_SOURCE_KEYS:
            report.warn(where, f"`source.{key}` is not a recognized source field")

    source_type = source.get("source")
    if source_type not in ("github", "url"):
        report.error(where, "`source.source` must be `github` or `url`")
        return None

    if source_type == "github" and (not isinstance(source.get("repo"), str) or "/" not in source.get("repo", "")):
        report.error(where, "GitHub source requires `repo` as `OWNER/REPO`")
    if source_type == "url" and not isinstance(source.get("url"), str):
        report.error(where, "URL source requires `url`")

    ref = source.get("ref")
    if ref is not None:
        if not isinstance(ref, str):
            report.error(where, "`source.ref` must be a string")
        elif ref in BRANCH_REFS:
            report.warn(where, f"`source.ref` is {ref!r}; branch refs move under users")

    path = source.get("path")
    if path is not None and not isinstance(path, str):
        report.error(where, "`source.path` must be a string")

    sha = source.get("sha")
    if sha is not None and (not isinstance(sha, str) or not SHA_RE.match(sha)):
        report.error(where, "`source.sha` must be exactly 40 hexadecimal characters")
    return None


def _validate_relative_source(report: Report, source: str, where: str, repo_root: Path) -> Path | None:
    plugin_dir = (repo_root / source).resolve()
    if not _inside_or_equal(repo_root, plugin_dir):
        report.error(where, f"relative `source` escapes the marketplace repository: {source}")
        return None
    if not plugin_dir.is_dir():
        report.error(where, f"relative `source` does not resolve to a directory: {source}")
        return None
    plugin_manifest = find_plugin_manifest(plugin_dir)
    if plugin_manifest is None:
        report.error(
            where,
            "relative `source` directory contains no discoverable plugin.json "
            f"({', '.join(PLUGIN_MANIFEST_LOCATIONS)})",
        )
        return None
    report.note(where, f"relative source resolves to {_display_path(plugin_dir, repo_root)}")
    return plugin_manifest


def _compare_plugin_metadata(report: Report, entry: dict[str, Any], where: str, plugin_manifest: Path) -> None:
    raw, error = load_json(plugin_manifest)
    label = f"{where} ({_display_path(plugin_manifest, plugin_manifest.parents[1])})"
    if error:
        report.error(where, f"cannot read referenced plugin manifest: {error}")
        return
    if not isinstance(raw, dict):
        report.error(where, "referenced plugin manifest is not a JSON object")
        return
    plugin = raw

    if isinstance(entry.get("name"), str) and isinstance(plugin.get("name"), str) and entry["name"] != plugin["name"]:
        report.warn(where, f"entry name {entry['name']!r} differs from plugin.json name {plugin['name']!r}")
    for field in ("version", "description"):
        if (
            field in entry
            and field in plugin
            and isinstance(entry[field], str)
            and isinstance(plugin[field], str)
            and entry[field] != plugin[field]
        ):
            report.warn(
                where,
                f"entry `{field}` {entry[field]!r} differs from plugin.json `{field}` {plugin[field]!r}",
            )
    report.note(label, "referenced plugin manifest parsed")


def _inside_or_equal(root: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    else:
        return True


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a GitHub Copilot CLI marketplace manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  validate_marketplace.py .\n"
            "  validate_marketplace.py .github/plugin/marketplace.json\n"
            "  validate_marketplace.py marketplace.json --warnings-as-errors\n"
        ),
    )
    parser.add_argument("path", nargs="?", default=".", help="marketplace file or repository root")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable JSON")
    parser.add_argument("--quiet", action="store_true", help="hide informational notes")
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="exit non-zero when warnings are present (recommended for CI)",
    )
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser()
    if not target.exists():
        print(f"error: path does not exist: {target}", file=sys.stderr)
        return 2

    manifest_path, repo_root = find_marketplace(target)
    if manifest_path is None or repo_root is None:
        print(
            "error: no marketplace manifest found. Expected one of: " + ", ".join(MANIFEST_LOCATIONS),
            file=sys.stderr,
        )
        return 2

    report = validate_marketplace(manifest_path, repo_root)

    if args.as_json:
        print(
            json.dumps(
                {
                    "marketplace": str(manifest_path),
                    "root": str(repo_root),
                    "ok": report.ok,
                    "errors": [{"where": w, "message": m} for w, m in report.errors],
                    "warnings": [{"where": w, "message": m} for w, m in report.warnings],
                    "notes": [{"where": w, "message": m} for w, m in report.notes],
                },
                indent=2,
            )
        )
    else:
        render(report, manifest_path, args.quiet)

    if report.errors:
        return 1
    if args.warnings_as_errors and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
