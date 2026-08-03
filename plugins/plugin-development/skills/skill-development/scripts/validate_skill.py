#!/usr/bin/env python3
"""Validate GitHub Copilot agent skills (SKILL.md files).

Usage:
    validate_skill.py SKILL_DIR [SKILL_DIR ...]
    validate_skill.py --recursive SKILLS_ROOT
    validate_skill.py --json --warnings-as-errors .github/skills/my-skill

Exit codes:
    0  no errors
    1  one or more errors (or warnings with --warnings-as-errors)
    2  bad invocation / path not found
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MIN_DESCRIPTION_LEN = 40
IDEAL_DESCRIPTION_RANGE = (100, 500)
BODY_LINE_LIMIT = 500
BODY_WORD_LIMIT = 5000
REFERENCE_TOC_LINE_THRESHOLD = 100

KNOWN_KEYS = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "argument-hint",
    "user-invocable",
    "disable-model-invocation",
    # Tolerated for cross-tool compatibility; ignored by Copilot CLI.
    "allowed_tools",
    "version",
    "metadata",
    "compatible-clients",
}

DANGEROUS_TOOLS = {"shell", "bash", "powershell", "execute"}

# Phrases that signal the description explains *when* to use the skill.
TRIGGER_HINTS = ("use when", "use this", "when the user", "when asked", "invoke when")

# Body headings that duplicate what belongs in the description.
BODY_TRIGGER_HEADING_RE = re.compile(
    r"^#{1,6}\s*(when to use|when to invoke|when should)", re.IGNORECASE | re.MULTILINE
)

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BACKTICK_PATH_RE = re.compile(r"`((?:\./)?(?:references|examples|scripts|assets)/[^`\s]+)`")
FORBIDDEN_FILES = {"readme.md", "changelog.md", "install.md", "quickstart.md", "contributing.md"}

# Fenced code blocks hold *illustrations* of links, not real ones. A skill that documents
# the link syntax should not be told its own examples are broken.
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,}).*?^(?P=fence)\s*$", re.MULTILINE | re.DOTALL)


def _strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks while preserving line numbering."""

    def _blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return FENCE_RE.sub(_blank, text)


TABLE_ROW_RE = re.compile(r"^\s*\|.*$", re.MULTILINE)
QUOTED_RE = re.compile(r"[\"“][^\"”]*[\"”]")


def _narrative(text: str) -> str:
    """Prose minus table rows and quoted strings.

    Style heuristics run against this so that a skill which *quotes* an anti-pattern —
    ``| ❌ | "You should use this." |`` — is not accused of committing it.
    """

    text = TABLE_ROW_RE.sub("", text)
    return QUOTED_RE.sub("", text)


# --------------------------------------------------------------------------


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
        return [_coerce(p) for p in inner.split(",")] if inner else []
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def _parse_yaml_fallback(text: str) -> tuple[dict[str, Any] | None, str | None]:
    data: dict[str, Any] = {}
    list_key: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            stripped = line.strip()
            if list_key and stripped.startswith("- "):
                data.setdefault(list_key, [])
                if isinstance(data[list_key], list):
                    data[list_key].append(_coerce(stripped[2:]))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            data[key] = []
            list_key = key
        else:
            data[key] = _coerce(value)
            list_key = None
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
        return None, raw, "missing YAML frontmatter (SKILL.md must start with a `---` line)"
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            data, error = _parse_yaml("\n".join(lines[1:index]))
            return data, "\n".join(lines[index + 1 :]), error
    return None, raw, "frontmatter block is never closed with `---`"


# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------


def validate_skill(skill_dir: Path) -> Report:
    report = Report(skill_dir.name)

    if not skill_dir.is_dir():
        report.error(f"not a directory: {skill_dir}")
        return report

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        misnamed = [p.name for p in skill_dir.iterdir() if p.name.lower() == "skill.md"]
        if misnamed:
            report.error(f"skill file must be named exactly `SKILL.md`, found {misnamed[0]!r}")
        else:
            report.error("no SKILL.md in this directory")
        return report

    if not NAME_RE.match(skill_dir.name):
        report.warn(f"directory name {skill_dir.name!r} should be lowercase with hyphens for spaces")

    frontmatter, body, error = read_frontmatter(skill_md)
    if frontmatter is None:
        report.error(error or "could not parse frontmatter")
        return report
    if error:
        report.warn(error)

    _check_name(report, frontmatter, skill_dir)
    _check_description(report, frontmatter)
    _check_allowed_tools(report, frontmatter)
    _check_invocation_flags(report, frontmatter)
    _check_unknown_keys(report, frontmatter)
    _check_body(report, body)
    _check_bundled_files(report, skill_dir, body)
    _check_scripts(report, skill_dir)
    _check_references(report, skill_dir)
    return report


def _check_name(report: Report, frontmatter: dict[str, Any], skill_dir: Path) -> None:
    name = frontmatter.get("name")
    if not name:
        report.error("`name` is required in frontmatter")
        return
    if not isinstance(name, str):
        report.error("`name` must be a string")
        return
    if not NAME_RE.match(name):
        report.error(f"`name` must be lowercase letters, digits and single hyphens: got {name!r}")
    if len(name) > MAX_NAME_LEN:
        report.error(f"`name` exceeds {MAX_NAME_LEN} characters ({len(name)})")
    if name != skill_dir.name:
        report.warn(
            f"`name` ({name!r}) differs from the directory name ({skill_dir.name!r}); "
            "keep them identical so `/{name}` matches the folder users see"
        )
    if name in ("skill", "helper", "assistant", "tool", "utils", "misc"):
        report.warn(f"`name` {name!r} is generic; use a task-specific name")


def _check_description(report: Report, frontmatter: dict[str, Any]) -> None:
    description = frontmatter.get("description")
    if not description:
        report.error("`description` is required in frontmatter")
        return
    if not isinstance(description, str):
        report.error("`description` must be a string")
        return

    length = len(description)
    if length > MAX_DESCRIPTION_LEN:
        report.error(f"`description` exceeds {MAX_DESCRIPTION_LEN} characters ({length})")
    if length < MIN_DESCRIPTION_LEN:
        report.error(
            f"`description` is {length} characters; it is the only text Copilot sees when "
            "deciding to load the skill, so state what it does AND when to use it"
        )
    elif length < IDEAL_DESCRIPTION_RANGE[0]:
        report.warn(
            f"`description` is short ({length} chars); aim for "
            f"{IDEAL_DESCRIPTION_RANGE[0]}-{IDEAL_DESCRIPTION_RANGE[1]} characters"
        )
    elif length > IDEAL_DESCRIPTION_RANGE[1]:
        report.note(f"`description` is long ({length} chars); acceptable, but check every clause earns its place")

    lowered = description.lower()
    if not any(hint in lowered for hint in TRIGGER_HINTS):
        report.warn(
            "`description` has no explicit trigger clause; add `Use when ...` so Copilot "
            "knows the situations that should load this skill"
        )
    if '"' not in description and "'" not in description:
        report.note(
            "`description` quotes no user phrasing; quoting 2-5 phrases a user would type "
            "measurably improves triggering"
        )
    if re.match(r"^\s*(you|i|we)\b", description, re.IGNORECASE):
        report.warn("`description` should be written in the third person, not addressed to the user")
    if "<" in description or ">" in description:
        report.warn("`description` contains angle brackets, which some clients reject; remove them")


def _check_allowed_tools(report: Report, frontmatter: dict[str, Any]) -> None:
    allowed = frontmatter.get("allowed-tools", frontmatter.get("allowed_tools"))
    if allowed is None:
        return
    items = [allowed] if isinstance(allowed, str) else allowed
    if not isinstance(items, list):
        report.error("`allowed-tools` must be a string or a list of strings")
        return
    flat: list[str] = []
    for item in items:
        if isinstance(item, str):
            flat.extend(part.strip() for part in item.split(",") if part.strip())
        else:
            report.error("`allowed-tools` entries must be strings")
    risky = sorted({t for t in flat if t.lower() in DANGEROUS_TOOLS})
    if risky:
        report.warn(
            f"`allowed-tools` pre-approves {', '.join(risky)}, which removes the confirmation "
            "prompt before running commands. Ship this only if every bundled script is reviewed and trusted"
        )


def _check_invocation_flags(report: Report, frontmatter: dict[str, Any]) -> None:
    for key in ("user-invocable", "disable-model-invocation"):
        value = frontmatter.get(key)
        if value is not None and not isinstance(value, bool):
            report.error(f"`{key}` must be a boolean")

    if frontmatter.get("user-invocable") is False and frontmatter.get("disable-model-invocation") is True:
        report.warn(
            "`user-invocable: false` and `disable-model-invocation: true` together make the "
            "skill unreachable: users cannot run /name and the agent cannot load it"
        )


def _check_unknown_keys(report: Report, frontmatter: dict[str, Any]) -> None:
    for key in frontmatter:
        if key not in KNOWN_KEYS:
            report.warn(f"`{key}` is not a recognized SKILL.md frontmatter field and is ignored")
    if "allowed_tools" in frontmatter:
        report.warn("use `allowed-tools` (hyphen), not `allowed_tools`")


def _check_body(report: Report, body: str) -> None:
    stripped = body.strip()
    if not stripped:
        report.error("SKILL.md body is empty; the body holds the instructions Copilot follows")
        return

    lines = stripped.splitlines()
    words = len(stripped.split())
    prose = _strip_fenced_blocks(stripped)
    if len(lines) > BODY_LINE_LIMIT:
        report.warn(
            f"body is {len(lines)} lines (soft limit {BODY_LINE_LIMIT}); move detail into "
            "`references/` and link to it so the loaded context stays small"
        )
    if words > BODY_WORD_LIMIT:
        report.warn(f"body is ~{words} words (soft limit {BODY_WORD_LIMIT}); split it into reference files")

    if BODY_TRIGGER_HEADING_RE.search(prose):
        report.warn(
            "body contains a 'When to use' section; the body loads only AFTER the skill "
            "triggers, so move that information into `description`"
        )

    second_person = len(re.findall(r"\byou (should|must|can|need to|will)\b", _narrative(prose), re.IGNORECASE))
    if second_person >= 3:
        report.note(
            f"body uses second-person phrasing {second_person} times; prefer imperative form "
            '("Run the script" rather than "You should run the script")'
        )

    if not re.search(r"^#{1,3}\s", stripped, re.MULTILINE):
        report.warn("body has no Markdown headings; add headings so Copilot can navigate it")


def _check_bundled_files(report: Report, skill_dir: Path, body: str) -> None:
    prose = _strip_fenced_blocks(body)
    targets: set[str] = set()
    for match in LINK_RE.finditer(prose):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        targets.add(target.split("#", 1)[0])
    # Backtick paths are counted as *mentions* only. Requiring them to exist produces false
    # positives whenever a skill quotes an illustrative path in prose.
    mentions = set(targets)
    for match in BACKTICK_PATH_RE.finditer(prose):
        mentions.add(match.group(1))

    root = skill_dir.resolve()
    for target in sorted(t for t in targets if t):
        resolved = (skill_dir / target).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            report.error(
                f"references {target!r}, which is outside the skill directory; bundled files "
                "must live inside the skill folder so the skill stays self-contained"
            )
            continue
        if not resolved.exists():
            report.error(f"references a bundled file that does not exist: {target}")

    # Files that exist but are never mentioned are dead weight. Mentions inside fenced
    # code blocks count here — a script invoked in a shell example is genuinely referenced.
    for sub in ("references", "examples", "scripts", "assets"):
        directory = skill_dir / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(skill_dir).as_posix()
            if rel in mentions or f"./{rel}" in mentions or rel in body:
                continue
            report.note(f"{rel} is bundled but never referenced from SKILL.md")

    for path in skill_dir.iterdir():
        if path.is_file() and path.name.lower() in FORBIDDEN_FILES:
            report.warn(
                f"{path.name} inside a skill directory duplicates SKILL.md and adds clutter; "
                "move that content to the plugin or repository README"
            )


def _check_scripts(report: Report, skill_dir: Path) -> None:
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.suffix not in (".sh", ".bash", ".py"):
            continue
        rel = path.relative_to(skill_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        first_line = text.splitlines()[0] if text.splitlines() else ""
        has_shebang = first_line.startswith("#!")
        executable = os.access(path, os.X_OK)
        if has_shebang and not executable:
            report.warn(f"{rel} has a shebang but is not executable; run `chmod +x {rel}`")
        if executable and not has_shebang:
            report.warn(f"{rel} is executable but has no shebang line")
        if path.suffix in (".sh", ".bash") and "set -euo pipefail" not in text:
            report.note(f"{rel} does not use `set -euo pipefail`; failures may pass silently")


def _check_references(report: Report, skill_dir: Path) -> None:
    directory = skill_dir / "references"
    if not directory.is_dir():
        return
    for path in sorted(directory.rglob("*.md")):
        rel = path.relative_to(skill_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        if len(lines) > REFERENCE_TOC_LINE_THRESHOLD:
            head = "\n".join(lines[:40]).lower()
            if "contents" not in head and "- [" not in head:
                report.note(
                    f"{rel} is {len(lines)} lines; add a table of contents at the top so Copilot "
                    "can jump to the relevant section"
                )


# --------------------------------------------------------------------------


def discover(root: Path) -> list[Path]:
    if (root / "SKILL.md").is_file():
        return [root]
    return sorted(p.parent for p in root.rglob("SKILL.md"))


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def render(reports: list[Report]) -> None:
    color = _supports_color()

    def paint(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

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

    errors = sum(len(r.errors) for r in reports)
    warnings = sum(len(r.warnings) for r in reports)
    print(f"\n{len(reports)} skill(s) checked: {errors} error(s), {warnings} warning(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate GitHub Copilot agent skills (SKILL.md).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  validate_skill.py .github/skills/my-skill\n"
            "  validate_skill.py --recursive .github/skills\n"
            "  validate_skill.py --recursive skills --warnings-as-errors\n"
        ),
    )
    parser.add_argument("paths", nargs="+", help="skill directories, or roots with --recursive")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="treat each path as a root and validate every SKILL.md beneath it",
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="emit JSON")
    parser.add_argument("--warnings-as-errors", action="store_true", help="exit non-zero on warnings (for CI)")
    args = parser.parse_args(argv)

    skill_dirs: list[Path] = []
    for raw in args.paths:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"error: path does not exist: {path}", file=sys.stderr)
            return 2
        skill_dirs.extend(discover(path) if args.recursive else [path])

    if not skill_dirs:
        print("error: no SKILL.md files found", file=sys.stderr)
        return 2

    reports = [validate_skill(path) for path in skill_dirs]

    # Skill names must be unique within a distribution unit.
    names: dict[str, str] = {}
    for path, report in zip(skill_dirs, reports, strict=False):
        frontmatter, _, _ = read_frontmatter(path / "SKILL.md") if (path / "SKILL.md").is_file() else (None, "", None)
        name = (frontmatter or {}).get("name")
        if isinstance(name, str):
            if name in names:
                report.error(f"duplicate skill name {name!r} (also used by {names[name]}); only the first loads")
            else:
                names[name] = str(path)

    if args.as_json:
        print(
            json.dumps(
                [
                    {
                        "skill": str(path),
                        "verdict": grade(report),
                        "errors": report.errors,
                        "warnings": report.warnings,
                        "notes": report.notes,
                    }
                    for path, report in zip(skill_dirs, reports, strict=False)
                ],
                indent=2,
            )
        )
    else:
        render(reports)

    if any(report.errors for report in reports):
        return 1
    if args.warnings_as_errors and any(report.warnings for report in reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
