#!/usr/bin/env python3
"""Validate a GitHub Copilot hooks JSON configuration file.

Checks schema version, top-level keys, event names, entry types, command/http/prompt
requirements, matcher support and regex syntax, timeout values, hardcoded paths, and
obvious embedded secrets.

Exit codes:
    0  no errors, or warnings only without --warnings-as-errors
    1  validation errors, or warnings with --warnings-as-errors
    2  usage error or unreadable input
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CAMEL_EVENTS = {
    "sessionStart",
    "sessionEnd",
    "userPromptSubmitted",
    "userPromptTransformed",
    "preToolUse",
    "postToolUse",
    "postToolUseFailure",
    "agentStop",
    "subagentStart",
    "subagentStop",
    "errorOccurred",
    "preCompact",
    "notification",
    "permissionRequest",
}

PASCAL_ALIASES = {
    "SessionStart": "sessionStart",
    "SessionEnd": "sessionEnd",
    "UserPromptSubmit": "userPromptSubmitted",
    "PreToolUse": "preToolUse",
    "PostToolUse": "postToolUse",
    "PostToolUseFailure": "postToolUseFailure",
    "Stop": "agentStop",
    "SubagentStop": "subagentStop",
    "ErrorOccurred": "errorOccurred",
    "PreCompact": "preCompact",
    "Notification": "notification",
    "PermissionRequest": "permissionRequest",
}

MATCHER_EVENTS = {
    "notification",
    "permissionRequest",
    "postToolUse",
    "preCompact",
    "preToolUse",
    "subagentStart",
}

ENTRY_TYPES = {"command", "http", "prompt"}
COMMAND_FIELDS = {"bash", "powershell", "command"}
TOP_LEVEL_KEYS = {"version", "disableAllHooks", "hooks"}
SECRET_KEY_RE = re.compile(r"(?:password|token|secret)", re.IGNORECASE)
TOKEN_RE = re.compile(r"(?:ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})")
HEX_RE = re.compile(r"\b[0-9a-fA-F]{40,}\b")
BASE64_RE = re.compile(r"\b[A-Za-z0-9+/]{48,}={0,2}\b")
ABS_PATH_RE = re.compile(r"(^|\s)(?:/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|[A-Za-z]:\\Users\\[^\s]+)")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warn(self, path: str, message: str) -> None:
        self.warnings.append(f"{path}: {message}")

    def note(self, path: str, message: str) -> None:
        self.notes.append(f"{path}: {message}")


def event_base(name: str) -> str | None:
    if name in CAMEL_EVENTS:
        return name
    return PASCAL_ALIASES.get(name)


def is_pascal(name: str) -> bool:
    return name in PASCAL_ALIASES


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}"


def validate(data: Any) -> Report:
    report = Report()
    if not isinstance(data, dict):
        report.error("$", "top-level value must be an object")
        return report

    for key in data:
        if key not in TOP_LEVEL_KEYS:
            report.error(f"$.{key}", "unknown top-level key")

    if data.get("version") != 1:
        report.error("$.version", "must be 1")

    if "disableAllHooks" in data and not isinstance(data["disableAllHooks"], bool):
        report.error("$.disableAllHooks", "must be a boolean")

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        report.error("$.hooks", "must be an object mapping event names to arrays")
        return report

    styles = set()
    for event_name, entries in hooks.items():
        base = event_base(event_name)
        if base is None:
            report.error(f"$.hooks.{event_name}", "unknown event name")
            continue
        styles.add("PascalCase" if is_pascal(event_name) else "camelCase")
        if not isinstance(entries, list):
            report.error(f"$.hooks.{event_name}", "event value must be an array")
            continue
        for index, entry in enumerate(entries):
            validate_entry(report, f"$.hooks.{event_name}[{index}]", event_name, base, entry)

    if len(styles) > 1:
        report.warn("$.hooks", "mixes camelCase and PascalCase event names in one file")

    scan_value(report, "$", data, parent_key="")
    return report


def validate_entry(report: Report, path: str, event_name: str, base_event: str, entry: Any) -> None:
    if not isinstance(entry, dict):
        report.error(path, "entry must be an object")
        return

    entry_type = entry.get("type", "command")
    if entry_type not in ENTRY_TYPES:
        report.error(f"{path}.type", f"unknown entry type {entry_type!r}")
        return

    if "matcher" in entry:
        if base_event not in MATCHER_EVENTS:
            report.error(f"{path}.matcher", f"matcher is not supported on {event_name}")
        elif not isinstance(entry["matcher"], str):
            report.error(f"{path}.matcher", "must be a string")
        else:
            matcher = entry["matcher"]
            if not (event_name in {"PreToolUse", "PermissionRequest"} and matcher in {"", "*", "**"}):
                try:
                    re.compile(f"^(?:{matcher})$")
                except re.error as exc:
                    report.error(f"{path}.matcher", f"regex does not compile: {exc}")

    timeout = entry.get("timeoutSec", entry.get("timeout"))
    if timeout is not None:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            report.error(f"{path}.timeoutSec", "must be a positive number")
        elif timeout > 60:
            report.warn(f"{path}.timeoutSec", "timeout over 60 seconds; hooks should stay fast")

    if entry_type == "command":
        present = [field for field in COMMAND_FIELDS if field in entry]
        if not present:
            report.error(path, "command entries require at least one of bash, powershell, or command")
        elif "command" in entry and len(present) > 1:
            report.warn(
                path,
                "`command` is a cross-platform fallback copied to both shells; an explicit "
                "`bash` or `powershell` in the same entry takes precedence over it",
            )
    elif entry_type == "prompt":
        if base_event != "sessionStart":
            report.error(path, "prompt entries are only valid under sessionStart")
        if not isinstance(entry.get("prompt"), str) or not entry.get("prompt"):
            report.error(f"{path}.prompt", "prompt entries require a non-empty prompt string")
    elif entry_type == "http":
        url = entry.get("url")
        if not isinstance(url, str) or not url:
            report.error(f"{path}.url", "http entries require a URL")
        else:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                report.error(f"{path}.url", "URL must use http or https")
            if base_event in {"preToolUse", "permissionRequest"} and parsed.scheme != "https":
                report.error(f"{path}.url", "HTTPS is required for preToolUse and permissionRequest http hooks")


def looks_like_env_reference(value: str) -> bool:
    return "${" in value or value.startswith("$") or (value.startswith("%") and value.endswith("%"))


def is_probable_base64(value: str) -> bool:
    stripped = value.strip()
    if not BASE64_RE.fullmatch(stripped):
        return False
    try:
        base64.b64decode(stripped + "=" * (-len(stripped) % 4), validate=True)
    except ValueError:
        return False
    return True


def scan_value(report: Report, path: str, value: Any, parent_key: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
            if (
                SECRET_KEY_RE.search(str(key))
                and isinstance(child, str)
                and child
                and not looks_like_env_reference(child)
            ):
                report.error(child_path, "secret-like key has a literal value; read secrets from the environment")
            scan_value(report, child_path, child, str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_value(report, f"{path}[{index}]", child, parent_key)
    elif isinstance(value, str):
        if TOKEN_RE.search(value):
            report.error(path, "contains an obvious access token or access key")
        if HEX_RE.search(value) and not looks_like_env_reference(value):
            report.error(path, "contains a long hex string that looks like an embedded secret")
        if is_probable_base64(value) and not looks_like_env_reference(value):
            report.error(path, "contains a long base64 string that looks like an embedded secret")
        if "${PLUGIN_ROOT}" not in value and "${COPILOT_PLUGIN_DATA}" not in value and ABS_PATH_RE.search(value):
            report.warn(path, "contains a suspicious hardcoded absolute path")


def render_text(report: Report, quiet: bool) -> None:
    if quiet and not report.errors:
        return
    for message in report.errors:
        print(f"ERROR {message}")
    for message in report.warnings:
        print(f"WARN {message}")
    if not quiet:
        for message in report.notes:
            print(f"note {message}")
        if not report.errors and not report.warnings:
            print("note hooks configuration passed validation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a GitHub Copilot hooks JSON file.")
    parser.add_argument("path", help="path to hooks.json")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit a JSON report")
    parser.add_argument("--quiet", action="store_true", help="suppress notes and clean output")
    parser.add_argument("--warnings-as-errors", action="store_true", help="exit 1 when warnings are present")
    args = parser.parse_args(argv)

    path = Path(args.path)
    data, error = load_json(path)
    if error:
        if args.as_json:
            print(json.dumps({"errors": [error], "warnings": [], "notes": []}, indent=2))
        else:
            print(f"ERROR {path}: {error}")
        return 2

    report = validate(data)
    if args.as_json:
        print(json.dumps({"errors": report.errors, "warnings": report.warnings, "notes": report.notes}, indent=2))
    else:
        render_text(report, args.quiet)

    if report.errors or (args.warnings_as_errors and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
