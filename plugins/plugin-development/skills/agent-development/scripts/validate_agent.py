#!/usr/bin/env python3
"""Validate GitHub Copilot custom agent profiles (*.agent.md files).

Usage:
    validate_agent.py agents/reviewer.agent.md
    validate_agent.py agents/
    validate_agent.py --recursive path/to/plugin
    validate_agent.py --json --warnings-as-errors agents/

Exit codes:
    0  no errors
    1  one or more errors (or warnings with --warnings-as-errors)
    2  bad invocation / path not found / no agent files found
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_ID_LEN = 64
MIN_DESCRIPTION_LEN = 40
MAX_DESCRIPTION_WARN = 1024
BODY_HARD_LIMIT = 30_000
BODY_WARN_LIMIT = 25_000

KNOWN_KEYS = {
    "description",
    "name",
    "target",
    "tools",
    "model",
    "disable-model-invocation",
    "user-invocable",
    "mcp-servers",
    "metadata",
}

PRIMARY_TOOL_ALIASES = {"execute", "read", "edit", "search", "agent", "web", "todo"}
COMPATIBLE_TOOL_ALIASES = {
    "shell": "execute",
    "bash": "execute",
    "powershell": "execute",
    "notebookread": "read",
    "notebookedit": "edit",
    "multiedit": "edit",
    "write": "edit",
    "grep": "search",
    "glob": "search",
    "custom-agent": "agent",
    "task": "agent",
    "websearch": "web",
    "webfetch": "web",
    "todowrite": "todo",
}
VALID_TOOL_TEXT = "agent, edit, execute, read, search, todo, web"
BUILT_IN_AGENT_IDS = {
    "explore",
    "task",
    "general-purpose",
    "code-review",
    "research",
    "rubber-duck",
    "security-review",
}
GENERIC_IDS = {"agent", "assistant", "helper", "misc", "reviewer", "tool", "utils"}
TRIGGER_RE = re.compile(
    r"\b(use when|when the user|when asked|for\s+[a-z0-9-]+ing|use this agent when)\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
OUTPUT_HEADING_RE = re.compile(r"^#{1,6}\s+.*\b(output|report|format|deliverable)s?\b", re.IGNORECASE | re.MULTILINE)
NUMBERED_PROCESS_RE = re.compile(
    r"^#{1,6}\s+.*\b(process|steps|workflow|procedure)\b[\s\S]*?^\s*1\.\s+",
    re.IGNORECASE | re.MULTILINE,
)
SECOND_PERSON_RE = re.compile(r"\b(you|your|yours)\b", re.IGNORECASE)
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,}).*?^(?P=fence)\s*$", re.MULTILINE | re.DOTALL)


def _strip_fenced_blocks(text: str) -> str:
    def _blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return FENCE_RE.sub(_blank, text)


def _parse_yaml(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        import yaml
    except ImportError:
        return _parse_yaml_fallback(text)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover
        return None, f"invalid YAML: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, "frontmatter must be a YAML mapping of key: value pairs"
    return data, None


def _coerce(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_coerce(part) for part in inner.split(",")] if inner else []
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def _parse_yaml_fallback(text: str) -> tuple[dict[str, Any] | None, str | None]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    current_map_key: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            stripped = line.strip()
            if current_list_key and stripped.startswith("- "):
                data.setdefault(current_list_key, [])
                if isinstance(data[current_list_key], list):
                    data[current_list_key].append(_coerce(stripped[2:]))
            elif current_map_key and ":" in stripped:
                child_key, _, child_value = stripped.partition(":")
                data.setdefault(current_map_key, {})
                if isinstance(data[current_map_key], dict):
                    data[current_map_key][child_key.strip()] = _coerce(child_value.strip())
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
            current_map_key = key
        else:
            data[key] = _coerce(value)
            current_list_key = None
            current_map_key = None
    return data, None


def read_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None, "", "file is not valid UTF-8"
    except OSError as exc:
        return None, "", f"cannot read file: {exc}"
    if raw.startswith("\ufeff"):
        return None, "", "file starts with a UTF-8 BOM; remove it so `---` is recognized"
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, raw, "missing YAML frontmatter (`*.agent.md` must start with a `---` line)"
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            data, error = _parse_yaml("\n".join(lines[1:index]))
            return data, "\n".join(lines[index + 1 :]), error
    return None, raw, "frontmatter block is never closed with `---`"


class Report:
    def __init__(self, label: str) -> None:
        self.label = label
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def grade(report: Report) -> str:
    if report.errors:
        return "NEEDS MAJOR REVISION"
    if len(report.warnings) > 3:
        return "NEEDS IMPROVEMENT"
    if report.warnings:
        return "PASS WITH NOTES"
    return "PASS"


def validate_agent(path: Path) -> Report:
    report = Report(str(path))

    if not path.is_file():
        report.error(f"not a file: {path}")
        return report

    _check_filename(report, path)
    frontmatter, body, error = read_frontmatter(path)
    if frontmatter is None:
        report.error(error or "could not parse frontmatter")
        return report
    if error:
        report.error(error)
        return report

    _check_frontmatter(report, frontmatter)
    _check_body(report, body)
    return report


def _check_filename(report: Report, path: Path) -> None:
    if not path.name.endswith(".agent.md"):
        report.error(f"filename must end in `.agent.md`: {path.name}")
        return
    agent_id = path.name[: -len(".agent.md")]
    if not ID_RE.match(agent_id):
        report.error(f"derived ID {agent_id!r} must be kebab-case lowercase letters, digits, and single hyphens")
    if len(agent_id) > MAX_ID_LEN:
        report.error(f"derived ID exceeds {MAX_ID_LEN} characters ({len(agent_id)})")
    if agent_id in BUILT_IN_AGENT_IDS:
        report.warn(f"derived ID {agent_id!r} collides with a well-known built-in agent name; rename it")
    if agent_id in GENERIC_IDS:
        report.warn(f"derived ID {agent_id!r} is generic; use a task-specific namespaced ID")


def _check_frontmatter(report: Report, frontmatter: dict[str, Any]) -> None:
    for key in sorted(frontmatter):
        if key == "infer":
            report.error("`infer` is retired; use `disable-model-invocation` and `user-invocable` instead")
        elif key == "allowed-tools":
            report.error("`allowed-tools` is a SKILL.md field; custom agents use `tools`")
        elif key not in KNOWN_KEYS:
            report.warn(f"`{key}` is not a recognized custom agent frontmatter field")

    _check_description(report, frontmatter)
    _check_tools(report, frontmatter)
    _check_simple_types(report, frontmatter)

    disabled = frontmatter.get("disable-model-invocation")
    invocable = frontmatter.get("user-invocable")
    if disabled is True and invocable is False:
        report.error("`disable-model-invocation: true` with `user-invocable: false` makes the agent unreachable")


def _check_description(report: Report, frontmatter: dict[str, Any]) -> None:
    description = frontmatter.get("description")
    if not description:
        report.error("`description` is required in frontmatter")
        return
    if not isinstance(description, str):
        report.error("`description` must be a string")
        return
    length = len(description)
    if length < MIN_DESCRIPTION_LEN:
        report.error(f"`description` is {length} characters; state what the agent does and when to delegate")
    if length > MAX_DESCRIPTION_WARN:
        report.warn(f"`description` is {length} characters; over {MAX_DESCRIPTION_WARN} can dilute delegation signals")
    if not TRIGGER_RE.search(description):
        report.warn(
            "`description` does not clearly describe when to delegate; add trigger phrasing "
            "such as `Use when`, `when the user`, or `for ...ing`"
        )
    if '"' not in description and "'" not in description:
        report.note("`description` quotes no user phrasing; quoted trigger phrases improve delegation")


def _tool_items(value: Any) -> tuple[list[str], str | None]:
    if value is None:
        return [], None
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()], None
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return [], "`tools` entries must be strings"
            items.append(item.strip())
        return items, None
    return [], "`tools` must be a comma-separated string or a list of strings"


def _is_known_tool(item: str) -> bool:
    lowered = item.lower()
    if lowered in PRIMARY_TOOL_ALIASES or lowered in COMPATIBLE_TOOL_ALIASES:
        return True
    if "/" in item:
        server, _, tool = item.partition("/")
        return bool(server and tool)
    return False


def _check_tools(report: Report, frontmatter: dict[str, Any]) -> None:
    if "tools" not in frontmatter:
        return
    items, error = _tool_items(frontmatter.get("tools"))
    if error:
        report.error(error)
        return
    if not items:
        report.note("`tools` is an empty list; the agent will have no tools")
        return
    if any(item == "*" for item in items):
        report.warn('`tools: ["*"]` grants all tools; prefer least-privilege aliases')
    unknown = sorted({item for item in items if item != "*" and not _is_known_tool(item)})
    if unknown:
        report.warn(f"unknown tool alias(es): {', '.join(unknown)}; valid aliases: {VALID_TOOL_TEXT}")


def _check_simple_types(report: Report, frontmatter: dict[str, Any]) -> None:
    for key in ("name", "target", "model"):
        if key in frontmatter and not isinstance(frontmatter[key], str):
            report.error(f"`{key}` must be a string")
    for key in ("disable-model-invocation", "user-invocable"):
        if key in frontmatter and not isinstance(frontmatter[key], bool):
            report.error(f"`{key}` must be a boolean")
    if "mcp-servers" in frontmatter and not isinstance(frontmatter["mcp-servers"], dict):
        report.warn("`mcp-servers` should be a YAML mapping")
    if "metadata" in frontmatter:
        metadata = frontmatter["metadata"]
        if not isinstance(metadata, dict):
            report.warn("`metadata` should be a YAML mapping of string key/value pairs")
        elif any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()):
            report.warn("`metadata` should contain only string keys and string values")


def _check_body(report: Report, body: str) -> None:
    stripped = body.strip()
    if not stripped:
        report.error("agent prompt body is empty")
        return
    char_count = len(stripped)
    if char_count > BODY_HARD_LIMIT:
        report.error(f"agent prompt body is {char_count} characters; the hard limit is {BODY_HARD_LIMIT}")
    elif char_count > BODY_WARN_LIMIT:
        report.warn(f"agent prompt body is {char_count} characters; approaching the {BODY_HARD_LIMIT} character cap")

    prose = _strip_fenced_blocks(stripped)
    if not HEADING_RE.search(prose):
        report.warn("body has no Markdown headings; add sections for responsibilities, process, and output")
    if not OUTPUT_HEADING_RE.search(prose):
        report.warn("body has no explicit output/report/format/deliverable section")
    if not NUMBERED_PROCESS_RE.search(prose):
        report.warn("body has no numbered process/steps/workflow section")

    second_person = len(SECOND_PERSON_RE.findall(prose))
    if second_person >= 20:
        report.note(
            f"body uses second-person phrasing {second_person} times; keep agent prompts direct "
            "and avoid repetitive `you must` wording"
        )


def discover(path: Path, recursive: bool = False) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []

    roots: list[Path]
    roots = [path / "agents"] if (path / "agents").is_dir() else [path]

    files: list[Path] = []
    for root in roots:
        pattern = "**/*.agent.md" if recursive else "*.agent.md"
        files.extend(sorted(root.glob(pattern)))
    return sorted(dict.fromkeys(files))


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def render(reports: list[Report], quiet: bool = False) -> None:
    color = _supports_color()

    def paint(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

    if not quiet:
        for report in reports:
            verdict = grade(report)
            code = {"PASS": "32;1", "PASS WITH NOTES": "32", "NEEDS IMPROVEMENT": "33;1"}.get(verdict, "31;1")
            print(f"\n{paint(verdict, code)}  {report.label}")
            for message in report.errors:
                print(f"  {paint('ERROR', '31;1')}  {message}")
            for message in report.warnings:
                print(f"  {paint('WARN ', '33;1')}  {message}")
            for message in report.notes:
                print(f"  {paint('note ', '36')}  {message}")

    errors = sum(len(report.errors) for report in reports)
    warnings = sum(len(report.warnings) for report in reports)
    print(f"\n{len(reports)} agent file(s) checked: {errors} error(s), {warnings} warning(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate GitHub Copilot custom agent profiles (*.agent.md).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  validate_agent.py .github/agents/reviewer.agent.md\n"
            "  validate_agent.py agents/\n"
            "  validate_agent.py --recursive path/to/plugin --warnings-as-errors\n"
        ),
    )
    parser.add_argument("paths", nargs="+", help="agent files, agent directories, or plugin roots")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="validate agent files recursively beneath each agent directory or plugin agents/ directory",
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="emit JSON")
    parser.add_argument("--quiet", action="store_true", help="suppress per-file details")
    parser.add_argument("--warnings-as-errors", action="store_true", help="exit non-zero on warnings (for CI)")
    args = parser.parse_args(argv)

    agent_files: list[Path] = []
    for raw in args.paths:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"error: path does not exist: {path}", file=sys.stderr)
            return 2
        agent_files.extend(discover(path, args.recursive))

    agent_files = sorted(dict.fromkeys(agent_files))
    if not agent_files:
        print("error: no *.agent.md files found", file=sys.stderr)
        return 2

    reports = [validate_agent(path) for path in agent_files]

    if args.as_json:
        print(
            json.dumps(
                [
                    {
                        "agent": str(path),
                        "verdict": grade(report),
                        "errors": report.errors,
                        "warnings": report.warnings,
                        "notes": report.notes,
                    }
                    for path, report in zip(agent_files, reports, strict=False)
                ],
                indent=2,
            )
        )
    else:
        render(reports, quiet=args.quiet)

    if any(report.errors for report in reports):
        return 1
    if args.warnings_as_errors and any(report.warnings for report in reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
