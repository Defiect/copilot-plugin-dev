#!/usr/bin/env python3
"""Scaffold a new GitHub Copilot CLI plugin.

Creates a plugin directory with a valid ``plugin.json`` and, optionally, stubs for each
component type. Every generated file is valid and passes ``validate_plugin.py`` before any
placeholder is filled in, so the first validation run reports content problems rather than
structural ones.

Usage:
    init_plugin.py --name NAME [--path DIR] [options]

Examples:
    init_plugin.py --name acme-conventions
    init_plugin.py --name acme-platform --path plugins --with-skill deployment --with-agent reviewer
    init_plugin.py --name acme-guardrails --with-hooks --with-mcp --with-lsp --author "Acme Team"

Exit codes:
    0  plugin created
    1  invalid arguments, or the target exists without --force
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path

MAX_NAME_LEN = 64
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MANIFEST_LOCATIONS = {
    "root": "plugin.json",
    "dot-plugin": ".plugin/plugin.json",
    "github": ".github/plugin/plugin.json",
}

MIT_LICENSE = """MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

SKILL_TEMPLATE = """---
name: {skill_name}
description: TODO write one sentence describing what this does in the third person, then "Use when the user asks to ..." with the exact phrases a user would type. Aim for 100-500 characters.
license: {license}
---

# {skill_title}

TODO: one or two sentences on what this skill does and why it exists. State the failure it
prevents.

## Workflow

1. **TODO: first step.** State the exact command or edit.
2. **TODO: second step.** Include the expected output so a deviation is noticeable.
3. **Verify.** TODO: the command that proves the work succeeded.

## Rules

- TODO: a rule, with the reason it exists in one clause.
- TODO: another rule.

## When something fails

| Symptom | Cause | Fix |
| --- | --- | --- |
| TODO | TODO | TODO |
"""

AGENT_TEMPLATE = """---
description: TODO describe what this agent does and, critically, WHEN to delegate to it. This text is what makes automatic delegation fire. 100-500 characters.
name: {agent_title}
tools: [read, search]
---

You are TODO: a one-sentence persona that establishes the standard this agent holds.

## Core responsibilities

1. TODO: an outcome this agent is accountable for.
2. TODO: another outcome.
3. TODO: another outcome.

## Process

1. TODO: the first thing to do, stated as a command or a concrete action.
2. TODO: the next step.
3. TODO: what to do when a step cannot be completed.
4. Produce the report in the format below. Never skip it.

## Quality standards

- TODO: a testable assertion, not an aspiration.
- TODO: another.

## Output format

```text
## TODO: report title

**Verdict:** TODO | TODO | TODO

### Critical
- <location>: <finding> - <consequence>

### Major
- <location>: <finding> - <consequence>

### Minor
- <location>: <finding>

### Summary
<one paragraph>
```

If any Critical finding exists, the verdict is TODO.
"""

COMMAND_TEMPLATE = """TODO: state the task in the imperative, addressed to Copilot.

1. TODO: the first thing to do.
2. TODO: the next.
3. TODO: the next.

Output TODO: the exact shape of the result. State explicitly whether files may be modified.
"""

HOOKS_TEMPLATE = {
    "version": 1,
    "hooks": {
        "preToolUse": [
            {
                "type": "command",
                "matcher": "shell|bash",
                "bash": "${PLUGIN_ROOT}/scripts/example-hook.sh",
                "timeoutSec": 5,
            }
        ]
    },
}

HOOK_SCRIPT = """#!/usr/bin/env bash
# TODO: describe what this hook does and which event it serves.
#
# preToolUse command hooks are fail-CLOSED on error and on exit code 2, but timeouts are
# always fail-OPEN. Keep this fast.
set -euo pipefail

payload="$(cat || true)"
[ -n "${payload}" ] || exit 0

# TODO: inspect "${payload}" and decide. Emit decision JSON on stdout, or exit 0 to allow.
exit 0
"""

MCP_TEMPLATE = {
    "mcpServers": {
        "TODO-namespaced-server-name": {
            "type": "stdio",
            "command": "${PLUGIN_ROOT}/bin/TODO-server",
            "args": ["--stdio"],
            "env": {"TODO_API_TOKEN": "${TODO_API_TOKEN}"},
        }
    }
}

LSP_TEMPLATE = {
    "lspServers": {
        "TODO-namespaced-server-name": {
            "fileExtensions": [".todo"],
            "bash": "${PLUGIN_ROOT}/scripts/launch-lsp.sh",
        }
    }
}

LSP_WRAPPER = """#!/usr/bin/env bash
# Guarded launcher: a plugin cannot assume the language server is installed.
set -euo pipefail

if ! command -v TODO-language-server >/dev/null 2>&1; then
  echo "TODO-language-server is not installed. Install it with: TODO" >&2
  exit 127
fi

exec TODO-language-server --stdio
"""

README_TEMPLATE = """# {name}

{description}

## Install

```bash
copilot plugin install ./{name}
copilot plugin list
```

## What this plugin adds
{components}
## Requirements
{requirements}
## Development

Re-run `copilot plugin install ./{name}` after every edit. Plugin components are copied at
install time, so editing this directory does not change an installed plugin.

```bash
validate_plugin.py . --warnings-as-errors
```
"""

GITIGNORE = """__pycache__/
*.pyc
.DS_Store
"""


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalize_name(raw: str) -> str:
    name = raw.strip().lower()
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"[^a-z0-9-]", "", name)
    return re.sub(r"-{2,}", "-", name).strip("-")


def title_from(name: str) -> str:
    return name.replace("-", " ").capitalize()


def write(path: Path, content: str, force: bool, executable: bool = False) -> None:
    if path.exists() and not force:
        fail(f"{path} already exists (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_json(path: Path, data: object, force: bool) -> None:
    write(path, json.dumps(data, indent=2) + "\n", force)


def build_manifest(args: argparse.Namespace, name: str) -> dict[str, object]:
    manifest: dict[str, object] = {"name": name}
    if args.description:
        manifest["description"] = args.description
    manifest["version"] = args.version
    if args.author:
        author: dict[str, str] = {"name": args.author}
        if args.email:
            author["email"] = args.email
        manifest["author"] = author
    if args.license:
        manifest["license"] = args.license
    if args.repository:
        manifest["repository"] = args.repository
    if args.keywords:
        manifest["keywords"] = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if args.category:
        manifest["category"] = args.category

    # Component fields are declared only when they do NOT sit at a default location.
    # `commands` has no default, so it is always declared when present.
    if args.with_command:
        manifest["commands"] = "commands/"
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a new GitHub Copilot CLI plugin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  init_plugin.py --name acme-conventions\n"
            "  init_plugin.py --name acme-platform --with-skill deployment --with-agent reviewer\n"
            "  init_plugin.py --name acme-guardrails --with-hooks --with-mcp --with-lsp\n"
        ),
    )
    parser.add_argument("--name", required=True, help="plugin name (kebab-case)")
    parser.add_argument("--path", default=".", help="directory to create the plugin in (default: .)")
    parser.add_argument("--description", default="", help="one-line plugin description")
    parser.add_argument("--version", default="0.1.0", help="initial semver version (default: 0.1.0)")
    parser.add_argument("--author", default="", help="author name")
    parser.add_argument("--email", default="", help="author email")
    parser.add_argument("--license", default="MIT", help="SPDX license identifier (default: MIT)")
    parser.add_argument("--repository", default="", help="repository URL")
    parser.add_argument("--homepage", default="", help="homepage URL")
    parser.add_argument("--keywords", default="", help="comma-separated keywords")
    parser.add_argument("--category", default="", help="category label")
    parser.add_argument(
        "--manifest-location",
        choices=sorted(MANIFEST_LOCATIONS),
        default="root",
        help="where to write plugin.json (default: root)",
    )
    parser.add_argument(
        "--with-skill", metavar="NAME", action="append", default=[], help="scaffold a skill (repeatable)"
    )
    parser.add_argument(
        "--with-agent", metavar="NAME", action="append", default=[], help="scaffold an agent (repeatable)"
    )
    parser.add_argument(
        "--with-command", metavar="NAME", action="append", default=[], help="scaffold a command (repeatable)"
    )
    parser.add_argument("--with-hooks", action="store_true", help="scaffold hooks/hooks.json and an example handler")
    parser.add_argument("--with-mcp", action="store_true", help="scaffold .mcp.json")
    parser.add_argument("--with-lsp", action="store_true", help="scaffold lsp.json and a guarded launcher")
    parser.add_argument("--no-readme", action="store_true", help="skip README.md")
    parser.add_argument("--no-license-file", action="store_true", help="skip the LICENSE file")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    name = normalize_name(args.name)
    if not name:
        fail(f"{args.name!r} does not reduce to a usable kebab-case name")
    if len(name) > MAX_NAME_LEN:
        fail(f"name is {len(name)} characters; the limit is {MAX_NAME_LEN}")
    if not NAME_RE.match(name):
        fail(f"{name!r} is not valid kebab-case")
    if name != args.name:
        print(f"note: normalized name to {name!r}")

    root = Path(args.path).expanduser() / name
    if root.exists() and any(root.iterdir()) and not args.force:
        fail(f"{root} already exists and is not empty (use --force)")
    root.mkdir(parents=True, exist_ok=True)

    created: list[str] = []

    manifest = build_manifest(args, name)
    if args.homepage:
        manifest["homepage"] = args.homepage
    manifest_path = root / MANIFEST_LOCATIONS[args.manifest_location]
    write_json(manifest_path, manifest, args.force)
    created.append(str(manifest_path.relative_to(root)))

    for raw in args.with_skill:
        skill_name = normalize_name(raw)
        if not skill_name:
            fail(f"{raw!r} is not a usable skill name")
        path = root / "skills" / skill_name / "SKILL.md"
        write(
            path,
            SKILL_TEMPLATE.format(
                skill_name=skill_name,
                skill_title=title_from(skill_name),
                license=args.license or "MIT",
            ),
            args.force,
        )
        created.append(str(path.relative_to(root)))

    for raw in args.with_agent:
        agent_id = normalize_name(raw)
        if not agent_id:
            fail(f"{raw!r} is not a usable agent name")
        path = root / "agents" / f"{agent_id}.agent.md"
        write(path, AGENT_TEMPLATE.format(agent_title=title_from(agent_id)), args.force)
        created.append(str(path.relative_to(root)))

    for raw in args.with_command:
        command_id = normalize_name(raw)
        if not command_id:
            fail(f"{raw!r} is not a usable command name")
        path = root / "commands" / f"{command_id}.md"
        write(path, COMMAND_TEMPLATE, args.force)
        created.append(str(path.relative_to(root)))

    if args.with_hooks:
        write_json(root / "hooks" / "hooks.json", HOOKS_TEMPLATE, args.force)
        write(root / "scripts" / "example-hook.sh", HOOK_SCRIPT, args.force, executable=True)
        created += ["hooks/hooks.json", "scripts/example-hook.sh"]

    if args.with_mcp:
        write_json(root / ".mcp.json", MCP_TEMPLATE, args.force)
        created.append(".mcp.json")

    if args.with_lsp:
        write_json(root / "lsp.json", LSP_TEMPLATE, args.force)
        write(root / "scripts" / "launch-lsp.sh", LSP_WRAPPER, args.force, executable=True)
        created += ["lsp.json", "scripts/launch-lsp.sh"]

    if not args.no_license_file and (args.license or "").upper() == "MIT":
        from datetime import datetime, timezone

        write(
            root / "LICENSE",
            MIT_LICENSE.format(year=datetime.now(tz=timezone.utc).year, holder=args.author or "TODO"),
            args.force,
        )
        created.append("LICENSE")

    if not args.no_readme:
        components = ""
        if args.with_skill:
            components += "\n### Skills\n\n" + "".join(f"- `{normalize_name(s)}` - TODO\n" for s in args.with_skill)
        if args.with_agent:
            components += "\n### Agents\n\n" + "".join(f"- `{normalize_name(a)}` - TODO\n" for a in args.with_agent)
        if args.with_command:
            components += "\n### Commands\n\n" + "".join(f"- `{normalize_name(c)}` - TODO\n" for c in args.with_command)
        if args.with_hooks:
            components += (
                "\n### Hooks\n\nThis plugin installs a `preToolUse` hook that runs in "
                "**every session**. TODO: state exactly what it does and why.\n"
            )
        if args.with_mcp:
            components += "\n### MCP servers\n\n- TODO: server name, the tools it provides, and their context cost.\n"
        if args.with_lsp:
            components += "\n### Language servers\n\n- TODO: server name and the file extensions it claims.\n"
        if not components:
            components = "\nTODO: list the skills, agents, and other components this plugin adds.\n"

        requirements = "\nTODO: none, or list required binaries and credentials.\n"
        if args.with_mcp:
            requirements = "\n- `TODO_API_TOKEN` must be set in the environment.\n"
        if args.with_lsp:
            requirements += "- `TODO-language-server` must be installed and on `PATH`.\n"

        write(
            root / "README.md",
            README_TEMPLATE.format(
                name=name,
                description=args.description or "TODO: one sentence describing this plugin.",
                components=components,
                requirements=requirements,
            ),
            args.force,
        )
        created.append("README.md")

    write(root / ".gitignore", GITIGNORE, args.force)
    created.append(".gitignore")

    print(f"Created plugin {name!r} at {root}")
    for item in created:
        print(f"  {item}")

    print("\nNext steps:")
    step = 1
    print(f"  {step}. Replace every TODO. Search for them: grep -rn TODO {root}")
    step += 1
    if args.with_skill:
        print(f"  {step}. Write each skill's `description` first - it decides whether the skill ever triggers.")
        step += 1
    if args.with_agent:
        print(f"  {step}. Narrow each agent's `tools` to the minimum it needs.")
        step += 1
    if args.with_hooks:
        print(f"  {step}. Reconsider the hook: plugin hooks run in every session of every installing user.")
        step += 1
    print(f"  {step}. Validate:  validate_plugin.py {root} --warnings-as-errors")
    step += 1
    print(f"  {step}. Install:   copilot plugin install {root}")
    step += 1
    print(f"  {step}. Verify:    copilot plugin list")
    step += 1
    print(f"  {step}. Trigger-test each component in a fresh session, then reinstall after every edit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
