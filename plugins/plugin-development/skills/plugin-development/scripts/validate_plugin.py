#!/usr/bin/env python3
"""Validate a GitHub Copilot CLI plugin directory against the plugin specification.

Checks the ``plugin.json`` manifest plus every component the plugin ships:
agents, skills, hooks, MCP servers, LSP servers, and command directories.

Usage:
    validate_plugin.py [PLUGIN_DIR] [--json] [--quiet] [--warnings-as-errors]

Exit codes:
    0  no errors (warnings may be present)
    1  one or more errors
    2  the plugin directory or manifest could not be found / parsed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Specification constants
# --------------------------------------------------------------------------

# Checked in this order, per the plugin reference "File locations" table.
MANIFEST_LOCATIONS = (
    ".plugin/plugin.json",
    "plugin.json",
    ".github/plugin/plugin.json",
    ".claude-plugin/plugin.json",
)

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Open Plugin Spec plugins may also use dots, e.g. "acme.tools".
OPEN_SPEC_NAME_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024

KNOWN_MANIFEST_KEYS = {
    "$schema",
    "name",
    "description",
    "version",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "category",
    "tags",
    "agents",
    "skills",
    "commands",
    "hooks",
    "extensions",
    "mcpServers",
    "lspServers",
    "strict",
}

PATH_FIELDS = ("agents", "skills", "commands", "extensions")

# camelCase (native) hook events.
HOOK_EVENTS_CAMEL = {
    "agentStop",
    "errorOccurred",
    "notification",
    "permissionRequest",
    "postToolUse",
    "postToolUseFailure",
    "preCompact",
    "preToolUse",
    "sessionEnd",
    "sessionStart",
    "subagentStart",
    "subagentStop",
    "userPromptSubmitted",
    "userPromptTransformed",
}

# PascalCase (VS Code / Claude compatible) hook events.
HOOK_EVENTS_PASCAL = {
    "ErrorOccurred",
    "Notification",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "PreCompact",
    "PreToolUse",
    "SessionEnd",
    "SessionStart",
    "Stop",
    "SubagentStop",
    "UserPromptSubmit",
}

HOOK_EVENTS = HOOK_EVENTS_CAMEL | HOOK_EVENTS_PASCAL

# Events that honour a `matcher` regex on each entry.
MATCHER_EVENTS = {
    "notification",
    "permissionRequest",
    "postToolUse",
    "preCompact",
    "preToolUse",
    "subagentStart",
    "Notification",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PreToolUse",
}

# `prompt` hook entries are only supported on sessionStart.
PROMPT_HOOK_EVENTS = {"sessionStart", "SessionStart"}

MCP_TYPES = {"local", "stdio", "http", "sse", "streamable-http"}

CANONICAL_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

AGENT_FRONTMATTER_KEYS = {
    "name",
    "description",
    "target",
    "tools",
    "model",
    "disable-model-invocation",
    "user-invocable",
    "infer",
    "mcp-servers",
    "metadata",
    # Accepted for cross-tool compatibility; ignored by Copilot CLI.
    "argument-hint",
    "handoffs",
    "color",
    "license",
}

SKILL_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "argument-hint",
    "user-invocable",
    "disable-model-invocation",
    "allowed_tools",
    "version",
    "metadata",
    "compatible-clients",
}

MAX_AGENT_PROMPT_CHARS = 30_000

# Skill descriptions shorter than this rarely say *when* to use the skill.
MIN_SKILL_DESCRIPTION_LEN = 40
# Soft cap: long SKILL.md bodies should push detail into references/.
SKILL_BODY_SOFT_LIMIT_LINES = 500

DANGEROUS_ALLOWED_TOOLS = {"shell", "bash", "powershell", "execute"}


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------


def _parse_yaml(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a YAML mapping. Uses PyYAML when installed, else a mini parser."""
    try:
        import yaml
    except ImportError:
        return _parse_yaml_fallback(text)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - depends on user input
        return None, f"invalid YAML: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, "frontmatter must be a YAML mapping"
    return data, None


def _coerce_scalar(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_coerce_scalar(part) for part in inner.split(",")]
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~", ""):
        return None
    return raw


def _parse_yaml_fallback(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Best-effort parser for the flat YAML subset used in frontmatter."""
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            stripped = line.strip()
            if current_list_key and stripped.startswith("- "):
                data.setdefault(current_list_key, [])
                if isinstance(data[current_list_key], list):
                    data[current_list_key].append(_coerce_scalar(stripped[2:]))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = _coerce_scalar(value)
            current_list_key = None
    return data, None


def read_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str, str | None]:
    """Return (frontmatter, body, error) for a Markdown file with YAML frontmatter."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None, "", "file is not valid UTF-8"
    except OSError as exc:
        return None, "", f"cannot read file: {exc}"

    if raw.startswith("\ufeff"):
        return None, "", "file starts with a UTF-8 BOM; remove it so the `---` delimiter is recognized"
    if not raw.startswith("---"):
        return None, raw, "missing YAML frontmatter (file must start with `---`)"

    lines = raw.splitlines()
    if lines[0].strip() != "---":
        return None, raw, "the opening frontmatter delimiter must be exactly `---`"
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            fm_text = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            data, error = _parse_yaml(fm_text)
            return data, body, error
    return None, raw, "frontmatter block is never closed with `---`"


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


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

    print(f"Validating plugin: {target}")
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


# --------------------------------------------------------------------------
# Manifest validation
# --------------------------------------------------------------------------


def find_manifest(plugin_dir: Path) -> Path | None:
    for relative in MANIFEST_LOCATIONS:
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


def validate_manifest(report: Report, manifest: dict[str, Any], where: str) -> None:
    schema = manifest.get("$schema")
    open_spec = isinstance(schema, str) and "agent-plugins.org" in schema
    if open_spec and schema != CANONICAL_PLUGIN_SCHEMA:
        report.warn(
            where,
            f"`$schema` is `{schema}`; Open Plugin Spec mode is keyed to the canonical URL `{CANONICAL_PLUGIN_SCHEMA}`",
        )

    name = manifest.get("name")
    if name is None:
        report.error(where, "`name` is required")
    elif check_string(report, where, "name", name):
        pattern = OPEN_SPEC_NAME_RE if open_spec else NAME_RE
        if not pattern.match(name):
            hint = " (dots are allowed only for Open Plugin Spec plugins)" if not open_spec else ""
            report.error(
                where,
                f"`name` must be kebab-case (lowercase letters, digits, hyphens): got {name!r}{hint}",
            )
        if len(name) > MAX_NAME_LEN:
            report.error(where, f"`name` exceeds {MAX_NAME_LEN} characters ({len(name)})")

    description = manifest.get("description")
    if description is None:
        report.warn(where, "`description` is missing; marketplaces and `plugin list` show it to users")
    elif check_string(report, where, "description", description):
        if len(description) > MAX_DESCRIPTION_LEN:
            report.error(
                where,
                f"`description` exceeds {MAX_DESCRIPTION_LEN} characters ({len(description)})",
            )
        if len(description) < 20:
            report.warn(where, "`description` is very short; say what the plugin does and who it is for")

    version = manifest.get("version")
    if version is None:
        report.warn(where, "`version` is missing; marketplace installs and `plugin update` rely on it")
    elif check_string(report, where, "version", version) and not SEMVER_RE.match(version):
        report.error(where, f"`version` must be a semantic version such as 1.0.0: got {version!r}")

    author = manifest.get("author")
    if author is not None:
        if not isinstance(author, dict):
            report.error(where, "`author` must be an object with a `name` field")
        else:
            if "name" not in author:
                report.error(where, "`author.name` is required when `author` is present")
            for key in author:
                if key not in ("name", "email", "url"):
                    report.warn(where, f"`author.{key}` is not a recognized author field")

    for field in ("homepage", "repository", "license", "category"):
        if field in manifest:
            check_string(report, where, field, manifest[field])

    for field in ("keywords", "tags"):
        if field in manifest:
            check_string_array(report, where, field, manifest[field])

    if "strict" in manifest and not isinstance(manifest["strict"], bool):
        report.error(where, "`strict` must be a boolean")

    for key in manifest:
        if key not in KNOWN_MANIFEST_KEYS:
            report.warn(where, f"`{key}` is not a recognized plugin.json field and will be ignored")


def normalize_paths(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict) and isinstance(value.get("paths"), list):
        return [item for item in value["paths"] if isinstance(item, str)]
    return []


# --------------------------------------------------------------------------
# Component validation
# --------------------------------------------------------------------------


def validate_agent_file(report: Report, path: Path, rel: str) -> str | None:
    frontmatter, body, error = read_frontmatter(path)
    if error and frontmatter is None:
        report.error(rel, error)
        return None
    if error:
        report.warn(rel, error)
    frontmatter = frontmatter or {}

    description = frontmatter.get("description")
    if not description:
        report.error(rel, "`description` is required in agent frontmatter")
    elif not isinstance(description, str):
        report.error(rel, "`description` must be a string")
    elif len(description) < 25:
        report.warn(
            rel,
            "`description` is very short; state the agent's expertise AND when Copilot should delegate to it",
        )

    name = frontmatter.get("name")
    if name is not None and not isinstance(name, str):
        report.error(rel, "`name` must be a string")

    tools = frontmatter.get("tools")
    if tools is not None and not isinstance(tools, (list, str)):
        report.error(rel, "`tools` must be a list of strings or a comma-separated string")

    for boolean_field in ("disable-model-invocation", "user-invocable", "infer"):
        if boolean_field in frontmatter and not isinstance(frontmatter[boolean_field], bool):
            report.error(rel, f"`{boolean_field}` must be a boolean")

    if "infer" in frontmatter:
        report.warn(
            rel,
            "`infer` is retired; prefer `disable-model-invocation` and `user-invocable`",
        )

    if "mcp-servers" in frontmatter and not isinstance(frontmatter["mcp-servers"], dict):
        report.error(rel, "`mcp-servers` must be a mapping of server name to configuration")

    for key in frontmatter:
        if key not in AGENT_FRONTMATTER_KEYS:
            report.warn(rel, f"`{key}` is not a recognized agent frontmatter field")

    if not body.strip():
        report.error(rel, "agent body is empty; the body is the agent's system prompt")
    elif len(body) > MAX_AGENT_PROMPT_CHARS:
        report.error(
            rel,
            f"agent prompt exceeds the {MAX_AGENT_PROMPT_CHARS:,} character limit ({len(body):,})",
        )

    agent_id = path.name[: -len(".agent.md")] if path.name.endswith(".agent.md") else path.stem
    if not NAME_RE.match(agent_id):
        report.warn(
            rel,
            f"agent id {agent_id!r} (derived from the file name) should be kebab-case for `--agent` use",
        )
    return agent_id


def validate_agents_dir(report: Report, plugin_dir: Path, directory: Path) -> None:
    rel_dir = directory.relative_to(plugin_dir).as_posix()
    agent_files = sorted(directory.rglob("*.agent.md"))
    stray = [p for p in sorted(directory.rglob("*.md")) if not p.name.endswith(".agent.md")]
    for path in stray:
        report.warn(
            path.relative_to(plugin_dir).as_posix(),
            "Markdown file in an agents directory does not end in `.agent.md` and will not be loaded",
        )
    if not agent_files:
        report.warn(rel_dir, "agents directory contains no `*.agent.md` files")
        return

    seen: dict[str, str] = {}
    for path in agent_files:
        rel = path.relative_to(plugin_dir).as_posix()
        agent_id = validate_agent_file(report, path, rel)
        if agent_id:
            if agent_id in seen:
                report.error(rel, f"duplicate agent id {agent_id!r} (also defined by {seen[agent_id]})")
            else:
                seen[agent_id] = rel
    report.note(rel_dir, f"{len(agent_files)} agent(s): {', '.join(sorted(seen))}")


def validate_skill_dir(report: Report, plugin_dir: Path, skill_dir: Path) -> str | None:
    rel_dir = skill_dir.relative_to(plugin_dir).as_posix()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        wrong_case = [p for p in skill_dir.iterdir() if p.name.lower() == "skill.md"]
        if wrong_case:
            report.error(
                rel_dir,
                f"skill file must be named exactly `SKILL.md` (found {wrong_case[0].name!r})",
            )
        else:
            report.error(rel_dir, "missing `SKILL.md`")
        return None

    rel = skill_md.relative_to(plugin_dir).as_posix()
    frontmatter, body, error = read_frontmatter(skill_md)
    if error and frontmatter is None:
        report.error(rel, error)
        return None
    if error:
        report.warn(rel, error)
    frontmatter = frontmatter or {}

    name = frontmatter.get("name")
    if not name:
        report.error(rel, "`name` is required in SKILL.md frontmatter")
    elif not isinstance(name, str):
        report.error(rel, "`name` must be a string")
    else:
        if not SKILL_NAME_RE.match(name):
            report.error(
                rel,
                f"`name` must be lowercase with hyphens for spaces: got {name!r}",
            )
        if name != skill_dir.name:
            report.warn(
                rel,
                f"`name` ({name!r}) does not match the skill directory ({skill_dir.name!r}); "
                "keeping them identical avoids confusion when invoking `/NAME`",
            )
        if len(name) > MAX_NAME_LEN:
            report.error(rel, f"`name` exceeds {MAX_NAME_LEN} characters")

    description = frontmatter.get("description")
    if not description:
        report.error(rel, "`description` is required in SKILL.md frontmatter")
    elif not isinstance(description, str):
        report.error(rel, "`description` must be a string")
    else:
        if len(description) > MAX_DESCRIPTION_LEN:
            report.error(
                rel,
                f"`description` exceeds {MAX_DESCRIPTION_LEN} characters ({len(description)})",
            )
        if len(description) < MIN_SKILL_DESCRIPTION_LEN:
            report.warn(
                rel,
                "`description` is short; it is the ONLY text Copilot sees when deciding to load "
                "the skill, so state both what it does and when to use it",
            )
        lowered = description.lower()
        if "use " not in lowered and "when " not in lowered:
            report.warn(
                rel,
                "`description` has no explicit trigger phrasing; add 'Use when ...' so Copilot "
                "knows when to load the skill",
            )

    allowed = frontmatter.get("allowed-tools", frontmatter.get("allowed_tools"))
    if allowed is not None:
        tools = [allowed] if isinstance(allowed, str) else allowed
        if not isinstance(tools, list):
            report.error(rel, "`allowed-tools` must be a string or a list of strings")
        else:
            flat: list[str] = []
            for item in tools:
                if isinstance(item, str):
                    flat.extend(part.strip() for part in item.split(",") if part.strip())
            risky = sorted({t for t in flat if t.lower() in DANGEROUS_ALLOWED_TOOLS})
            if risky:
                report.warn(
                    rel,
                    f"`allowed-tools` pre-approves {', '.join(risky)}; this removes the confirmation "
                    "prompt for running commands. Only ship this if every bundled script is trusted",
                )

    for key in frontmatter:
        if key not in SKILL_FRONTMATTER_KEYS:
            report.warn(rel, f"`{key}` is not a recognized SKILL.md frontmatter field")

    body_lines = body.strip().splitlines()
    if not body_lines:
        report.error(rel, "SKILL.md body is empty; the body holds the actual instructions")
    elif len(body_lines) > SKILL_BODY_SOFT_LIMIT_LINES:
        report.warn(
            rel,
            f"SKILL.md body is {len(body_lines)} lines; move detail into `references/` files and "
            f"link to them so the loaded context stays small (soft limit {SKILL_BODY_SOFT_LIMIT_LINES})",
        )

    _check_skill_links(report, skill_dir, body, rel)
    _check_script_permissions(report, skill_dir, plugin_dir)
    return name if isinstance(name, str) else None


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BACKTICK_PATH_RE = re.compile(r"`((?:\./)?(?:references|examples|scripts|assets)/[^`\s]+)`")

# Fenced code blocks contain *illustrations* of paths and links, not real references. A
# skill that documents link syntax must not be told its own examples are broken.
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,}).*?^(?P=fence)\s*$", re.MULTILINE | re.DOTALL)


def _strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks while preserving line numbering."""

    def _blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return FENCE_RE.sub(_blank, text)


def _check_skill_links(report: Report, skill_dir: Path, body: str, rel: str) -> None:
    prose = _strip_fenced_blocks(body)
    candidates: set[str] = set()
    for match in LINK_RE.finditer(prose):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        candidates.add(target.split("#", 1)[0])

    for target in sorted(candidates):
        if not target:
            continue
        resolved = (skill_dir / target).resolve()
        try:
            resolved.relative_to(skill_dir.resolve())
        except ValueError:
            report.warn(
                rel,
                f"references {target!r} outside the skill directory; bundled files must live inside "
                "the skill folder so they ship with it",
            )
            continue
        if not resolved.exists():
            report.error(rel, f"references a bundled file that does not exist: {target}")


def _check_script_permissions(report: Report, skill_dir: Path, plugin_dir: Path) -> None:
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in (".sh", ".bash", ".py"):
            continue
        rel = path.relative_to(plugin_dir).as_posix()
        try:
            first = path.read_text(encoding="utf-8").splitlines()[:1]
        except (OSError, UnicodeDecodeError, IndexError):
            continue
        has_shebang = bool(first) and first[0].startswith("#!")
        executable = os.access(path, os.X_OK)
        if has_shebang and not executable:
            report.warn(rel, "script has a shebang but is not executable (`chmod +x`)")
        if executable and not has_shebang:
            report.warn(rel, "script is executable but has no shebang line")


def validate_skills_dir(report: Report, plugin_dir: Path, directory: Path, seen: dict[str, str]) -> None:
    rel_dir = directory.relative_to(plugin_dir).as_posix()
    if (directory / "SKILL.md").is_file():
        report.error(
            rel_dir,
            "a skills directory must contain one subdirectory per skill, not a top-level SKILL.md",
        )
        return

    skill_dirs = sorted(p for p in directory.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not skill_dirs:
        report.warn(rel_dir, "skills directory contains no skill subdirectories")
        return

    for skill_dir in skill_dirs:
        if not SKILL_NAME_RE.match(skill_dir.name):
            report.warn(
                skill_dir.relative_to(plugin_dir).as_posix(),
                "skill directory names should be lowercase with hyphens for spaces",
            )
        name = validate_skill_dir(report, plugin_dir, skill_dir)
        if name:
            if name in seen:
                report.error(
                    skill_dir.relative_to(plugin_dir).as_posix(),
                    f"duplicate skill name {name!r} (also defined by {seen[name]}); skills are "
                    "deduplicated by name and only the first one loads",
                )
            else:
                seen[name] = skill_dir.relative_to(plugin_dir).as_posix()
    report.note(rel_dir, f"{len(skill_dirs)} skill(s): {', '.join(sorted(seen))}")


def validate_hook_entry(report: Report, where: str, event: str, index: int, entry: Any) -> None:
    label = f"hooks.{event}[{index}]"
    if not isinstance(entry, dict):
        report.error(where, f"{label} must be an object")
        return

    entry_type = entry.get("type", "command")
    if entry_type not in ("command", "http", "prompt"):
        report.error(where, f"{label}.type must be 'command', 'http', or 'prompt'")
        return

    if entry_type == "command":
        if not any(key in entry for key in ("bash", "powershell", "command")):
            report.error(where, f"{label} needs one of `bash`, `powershell`, or `command`")
        if "bash" in entry and "powershell" not in entry and "command" not in entry:
            report.warn(
                where,
                f"{label} only defines `bash`; add `powershell` (or `command`) so the hook also runs on Windows",
            )
        if "powershell" in entry and "bash" not in entry and "command" not in entry:
            report.warn(
                where,
                f"{label} only defines `powershell`; add `bash` (or `command`) so the hook also runs on macOS/Linux",
            )
    elif entry_type == "http":
        url = entry.get("url")
        if not isinstance(url, str):
            report.error(where, f"{label}.url is required for http hooks")
        else:
            if not url.startswith(("http://", "https://")):
                report.error(where, f"{label}.url must use http: or https:")
            elif url.startswith("http://") and not url.startswith(("http://localhost", "http://127.", "http://[::1]")):
                report.error(
                    where,
                    f"{label}.url must use https:// (plain http is only allowed for localhost)",
                )
            elif event in ("preToolUse", "PreToolUse", "permissionRequest", "PermissionRequest") and not url.startswith(
                "https://"
            ):
                report.error(
                    where,
                    f"{label}.url must use https:// because {event} responses can grant tool permissions",
                )
        if "allowedEnvVars" in entry:
            if not isinstance(entry["allowedEnvVars"], list):
                report.error(where, f"{label}.allowedEnvVars must be an array of strings")
            elif isinstance(entry.get("url"), str) and not entry["url"].startswith("https://"):
                report.error(where, f"{label} sets allowedEnvVars, so `url` must use https://")
    elif entry_type == "prompt":
        if event not in PROMPT_HOOK_EVENTS:
            report.error(where, f"{label}: prompt hooks are only supported on sessionStart")
        if not isinstance(entry.get("prompt"), str):
            report.error(where, f"{label}.prompt is required for prompt hooks")

    for timeout_key in ("timeoutSec", "timeout"):
        if timeout_key in entry:
            value = entry[timeout_key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                report.error(where, f"{label}.{timeout_key} must be a positive number of seconds")
            elif value > 60:
                report.warn(
                    where,
                    f"{label}.{timeout_key} is {value}s; hooks run synchronously and block the "
                    "session, so keep them short",
                )

    if "env" in entry and not isinstance(entry["env"], dict):
        report.error(where, f"{label}.env must be an object of environment variables")

    if "matcher" in entry:
        if event not in MATCHER_EVENTS:
            report.warn(where, f"{label}.matcher is ignored for the {event} event")
        elif not isinstance(entry["matcher"], str):
            report.error(where, f"{label}.matcher must be a string")
        else:
            try:
                re.compile(entry["matcher"])
            except re.error as exc:
                report.error(where, f"{label}.matcher is not a valid regular expression: {exc}")


def validate_hooks_config(report: Report, config: Any, where: str) -> None:
    if not isinstance(config, dict):
        report.error(where, "hooks configuration must be a JSON object")
        return
    if config.get("version") != 1:
        report.error(where, 'hooks configuration must set `"version": 1`')
    if "disableAllHooks" in config and not isinstance(config["disableAllHooks"], bool):
        report.error(where, "`disableAllHooks` must be a boolean")

    hooks = config.get("hooks")
    if hooks is None:
        report.error(where, "hooks configuration must contain a `hooks` object")
        return
    if not isinstance(hooks, dict):
        report.error(where, "`hooks` must be an object keyed by event name")
        return

    mixed = bool(hooks.keys() & HOOK_EVENTS_CAMEL) and bool(hooks.keys() & HOOK_EVENTS_PASCAL)
    if mixed:
        report.warn(
            where,
            "mixes camelCase and PascalCase event names; payload field casing differs between the "
            "two formats, so pick one per file",
        )

    for event, entries in hooks.items():
        if event not in HOOK_EVENTS:
            report.error(where, f"unknown hook event {event!r}")
            continue
        if not isinstance(entries, list):
            report.error(where, f"hooks.{event} must be an array")
            continue
        if not entries:
            report.warn(where, f"hooks.{event} is an empty array")
        for index, entry in enumerate(entries):
            validate_hook_entry(report, where, event, index, entry)

    report.note(where, f"{sum(len(v) for v in hooks.values() if isinstance(v, list))} hook entr(ies)")


def validate_mcp_config(report: Report, config: Any, where: str) -> None:
    if not isinstance(config, dict):
        report.error(where, "MCP configuration must be a JSON object")
        return
    servers = config.get("mcpServers") if isinstance(config.get("mcpServers"), dict) else config
    if "servers" in config and "mcpServers" not in config:
        report.error(
            where,
            "top-level `servers` is the VS Code format and is not read by Copilot CLI; use `mcpServers`",
        )
        return
    if not servers:
        report.warn(where, "MCP configuration defines no servers")
        return

    for name, definition in servers.items():
        label = f"mcpServers.{name}"
        if not isinstance(definition, dict):
            report.error(where, f"{label} must be an object")
            continue
        server_type = definition.get("type")
        if server_type is not None and server_type not in MCP_TYPES:
            report.error(
                where,
                f"{label}.type must be one of {', '.join(sorted(MCP_TYPES))}",
            )
        remote = server_type in ("http", "sse") or "url" in definition
        if remote:
            if not isinstance(definition.get("url"), str):
                report.error(where, f"{label}.url is required for http/sse servers")
            if "command" in definition:
                report.error(where, f"{label} sets both `url` and `command`")
            if "headers" in definition and not isinstance(definition["headers"], dict):
                report.error(where, f"{label}.headers must be an object")
        else:
            if not isinstance(definition.get("command"), str):
                report.error(where, f"{label}.command is required for local/stdio servers")
            if "args" in definition and not isinstance(definition["args"], list):
                report.error(where, f"{label}.args must be an array of strings")
            if server_type is None:
                report.warn(where, f'{label} has no `type`; set "type": "local" explicitly')
        if "env" in definition and not isinstance(definition["env"], dict):
            report.error(where, f"{label}.env must be an object")
        if "tools" in definition and not isinstance(definition["tools"], (list, str)):
            report.error(where, f'{label}.tools must be an array (use ["*"] for all tools)')

        blob = json.dumps(definition)
        if re.search(r"(?i)(gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", blob):
            report.error(
                where,
                f"{label} appears to contain a hard-coded credential; use ${{ENV_VAR}} placeholders instead",
            )
    report.note(where, f"{len(servers)} MCP server(s): {', '.join(sorted(servers))}")


def validate_lsp_config(report: Report, config: Any, where: str) -> None:
    if not isinstance(config, dict):
        report.error(where, "LSP configuration must be a JSON object")
        return
    servers = config.get("lspServers") if isinstance(config.get("lspServers"), dict) else config
    if not servers:
        report.warn(where, "LSP configuration defines no servers")
        return
    for name, definition in servers.items():
        label = f"lspServers.{name}"
        if not isinstance(definition, dict):
            report.error(where, f"{label} must be an object")
            continue
        if not any(key in definition for key in ("command", "bash", "powershell")):
            report.error(where, f"{label} needs at least one of `command`, `bash`, or `powershell`")
        extensions = definition.get("fileExtensions")
        if not isinstance(extensions, dict) or not extensions:
            report.error(
                where,
                f'{label}.fileExtensions is required, e.g. {{".ts": "typescript"}}',
            )
        else:
            for extension in extensions:
                if not extension.startswith("."):
                    report.warn(where, f"{label}.fileExtensions key {extension!r} should start with a dot")
        if "args" in definition and not isinstance(definition["args"], list):
            report.error(where, f"{label}.args must be an array of strings")
        if "args" in definition and "command" not in definition:
            report.warn(where, f"{label}.args is ignored when using `bash`/`powershell`")
        if "env" in definition and not isinstance(definition["env"], dict):
            report.error(where, f"{label}.env must be an object")
    report.note(where, f"{len(servers)} LSP server(s): {', '.join(sorted(servers))}")


def load_json(report: Report, path: Path, rel: str) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error(rel, f"invalid JSON: {exc}")
    except OSError as exc:
        report.error(rel, f"cannot read file: {exc}")
    return None


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def validate_plugin(plugin_dir: Path) -> Report:
    report = Report()

    manifest_path = find_manifest(plugin_dir)
    if manifest_path is None:
        report.error(
            plugin_dir.name,
            "no plugin manifest found. Expected one of: " + ", ".join(MANIFEST_LOCATIONS),
        )
        return report

    manifest_rel = manifest_path.relative_to(plugin_dir).as_posix()
    manifest = load_json(report, manifest_path, manifest_rel)
    if manifest is None:
        return report
    if not isinstance(manifest, dict):
        report.error(manifest_rel, "plugin manifest must be a JSON object")
        return report

    validate_manifest(report, manifest, manifest_rel)

    # ---- agents -----------------------------------------------------------
    agent_paths = normalize_paths(manifest.get("agents", "agents/"))
    explicit_agents = "agents" in manifest
    for relative in agent_paths:
        directory = (plugin_dir / relative).resolve()
        if not directory.is_dir():
            if explicit_agents:
                report.error(manifest_rel, f"`agents` path does not exist: {relative}")
            continue
        validate_agents_dir(report, plugin_dir, directory)

    # ---- skills -----------------------------------------------------------
    skill_paths = normalize_paths(manifest.get("skills", "skills/"))
    explicit_skills = "skills" in manifest
    seen_skills: dict[str, str] = {}
    for relative in skill_paths:
        directory = (plugin_dir / relative).resolve()
        if not directory.is_dir():
            if explicit_skills:
                report.error(manifest_rel, f"`skills` path does not exist: {relative}")
            continue
        validate_skills_dir(report, plugin_dir, directory, seen_skills)

    # ---- commands / extensions -------------------------------------------
    for field in ("commands", "extensions"):
        if field not in manifest:
            continue
        value = manifest[field]
        if field == "extensions" and isinstance(value, dict):
            if "paths" not in value:
                report.error(manifest_rel, "`extensions` object form requires a `paths` array")
            if "exclusive" in value and not isinstance(value["exclusive"], bool):
                report.error(manifest_rel, "`extensions.exclusive` must be a boolean")
        for relative in normalize_paths(value):
            if not (plugin_dir / relative).exists():
                report.error(manifest_rel, f"`{field}` path does not exist: {relative}")

    # ---- hooks ------------------------------------------------------------
    hooks_field = manifest.get("hooks")
    if isinstance(hooks_field, dict):
        validate_hooks_config(report, hooks_field, f"{manifest_rel} (inline hooks)")
    else:
        hook_candidates = [hooks_field] if isinstance(hooks_field, str) else ["hooks.json", "hooks/hooks.json"]
        for relative in hook_candidates:
            path = plugin_dir / relative
            if path.is_file():
                config = load_json(report, path, relative)
                if config is not None:
                    validate_hooks_config(report, config, relative)
                break
        else:
            if isinstance(hooks_field, str):
                report.error(manifest_rel, f"`hooks` path does not exist: {hooks_field}")

    # ---- MCP --------------------------------------------------------------
    mcp_field = manifest.get("mcpServers")
    if isinstance(mcp_field, dict):
        validate_mcp_config(report, {"mcpServers": mcp_field}, f"{manifest_rel} (inline mcpServers)")
    else:
        mcp_candidates = [mcp_field] if isinstance(mcp_field, str) else [".mcp.json", ".github/mcp.json"]
        for relative in mcp_candidates:
            path = plugin_dir / relative
            if path.is_file():
                config = load_json(report, path, relative)
                if config is not None:
                    validate_mcp_config(report, config, relative)
                break
        else:
            if isinstance(mcp_field, str):
                report.error(manifest_rel, f"`mcpServers` path does not exist: {mcp_field}")

    # ---- LSP --------------------------------------------------------------
    lsp_field = manifest.get("lspServers")
    if isinstance(lsp_field, dict):
        validate_lsp_config(report, {"lspServers": lsp_field}, f"{manifest_rel} (inline lspServers)")
    else:
        lsp_candidates = (
            [lsp_field] if isinstance(lsp_field, str) else ["lsp.json", ".github/lsp.json", "lsp-config/servers.json"]
        )
        for relative in lsp_candidates:
            path = plugin_dir / relative
            if path.is_file():
                config = load_json(report, path, relative)
                if config is not None:
                    validate_lsp_config(report, config, relative)
                break
        else:
            if isinstance(lsp_field, str):
                report.error(manifest_rel, f"`lspServers` path does not exist: {lsp_field}")

    # ---- repository hygiene ----------------------------------------------
    has_component = bool(
        seen_skills
        or any((plugin_dir / p).is_dir() for p in agent_paths)
        or manifest.get("hooks")
        or manifest.get("mcpServers")
        or manifest.get("lspServers")
        or (plugin_dir / "hooks.json").is_file()
        or (plugin_dir / ".mcp.json").is_file()
    )
    if not has_component:
        report.warn(
            plugin_dir.name,
            "plugin ships no agents, skills, hooks, MCP servers, or LSP servers; it will do nothing",
        )
    if not any((plugin_dir / name).is_file() for name in ("README.md", "readme.md")):
        report.warn(plugin_dir.name, "no README.md; users browsing the repository have no documentation")
    if manifest.get("license") and not any(
        (plugin_dir / name).is_file() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt")
    ):
        report.note(plugin_dir.name, "manifest declares a license but no LICENSE file ships with the plugin")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a GitHub Copilot CLI plugin directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  validate_plugin.py .\n"
            "  validate_plugin.py plugins/my-plugin --warnings-as-errors\n"
            "  validate_plugin.py plugins/my-plugin --json | jq .\n"
        ),
    )
    parser.add_argument("plugin_dir", nargs="?", default=".", help="path to the plugin directory")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable JSON")
    parser.add_argument("--quiet", action="store_true", help="hide informational notes")
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="exit non-zero when warnings are present (recommended for CI)",
    )
    args = parser.parse_args(argv)

    plugin_dir = Path(args.plugin_dir).expanduser().resolve()
    if not plugin_dir.is_dir():
        print(f"error: not a directory: {plugin_dir}", file=sys.stderr)
        return 2

    report = validate_plugin(plugin_dir)

    if args.as_json:
        print(
            json.dumps(
                {
                    "plugin": str(plugin_dir),
                    "ok": report.ok,
                    "errors": [{"where": w, "message": m} for w, m in report.errors],
                    "warnings": [{"where": w, "message": m} for w, m in report.warnings],
                    "notes": [{"where": w, "message": m} for w, m in report.notes],
                },
                indent=2,
            )
        )
    else:
        render(report, plugin_dir, args.quiet)

    if report.errors:
        return 1
    if args.warnings_as_errors and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
