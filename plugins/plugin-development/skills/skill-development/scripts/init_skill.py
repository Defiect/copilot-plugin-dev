#!/usr/bin/env python3
"""Scaffold a new GitHub Copilot agent skill.

Usage:
    init_skill.py NAME --path DIR [options]

Examples:
    init_skill.py pdf-form-filling --path .github/skills
    init_skill.py release-checklist --path ~/.copilot/skills --structure workflow
    init_skill.py svg-convert --path skills --resources scripts,references --structure capability

Exit codes:
    0  skill created
    1  invalid arguments or the target already exists
"""

from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path

MAX_NAME_LEN = 64
VALID_RESOURCES = ("references", "examples", "scripts", "assets")
STRUCTURES = ("workflow", "task", "reference", "capability", "placeholder")

STRUCTURE_BODIES = {
    "workflow": """## Prerequisites

- TODO: tools, credentials, or state required before starting.

## Workflow

1. **TODO: first step.** State the exact command or edit to make.
2. **TODO: second step.** Include the expected output so deviations are noticeable.
3. **TODO: third step.**
4. **Verify.** TODO: the command that proves the work succeeded, and what its output
   should look like.

## When something fails

| Symptom | Cause | Fix |
| --- | --- | --- |
| TODO | TODO | TODO |
""",
    "task": """## TODO: task one

TODO: what to do, the exact command, and how to read the result.

## TODO: task two

TODO.

## TODO: task three

TODO.

## Conventions that apply to every task

- TODO: shared rules, naming, or output format.
""",
    "reference": """## Rules

### TODO: rule one

TODO: the rule, one sentence of rationale, and a short example.

```text
TODO
```

### TODO: rule two

TODO.

## Review checklist

- [ ] TODO
- [ ] TODO
""",
    "capability": """## What the script does

TODO: one paragraph describing the operation and its guarantees.

## Running it

Run `scripts/TODO.sh` from this skill's directory:

```bash
scripts/TODO.sh INPUT_PATH [OPTIONS]
```

| Argument | Required | Meaning |
| --- | --- | --- |
| `INPUT_PATH` | Yes | TODO |

## Reading the output

TODO: describe stdout format and exit codes.

| Exit code | Meaning | Action |
| --- | --- | --- |
| `0` | Success | TODO |
| `1` | TODO | TODO |

## Constraints

- TODO: what the script does not handle, so Copilot does not try.
""",
    "placeholder": """## TODO: Choose a structure

Delete this section once the body is written. Pick whichever structure fits and rerun
`init_skill.py` with `--structure` to generate a skeleton:

- `workflow` — a fixed sequence of steps (releases, migrations, incident response).
- `task` — several independent operations sharing conventions (a toolkit).
- `reference` — rules applied while doing something else (standards, review checklists).
- `capability` — one fragile operation exposed through a bundled script.
""",
}

SKILL_TEMPLATE = """---
name: {name}
description: {description}
{license_line}---

# {title}

{intro}

{body}
"""

EXAMPLE_SCRIPT = """#!/usr/bin/env bash
# TODO: describe what this script does.
set -euo pipefail

usage() {{
    cat >&2 <<'USAGE'
Usage: {script_name} INPUT_PATH

TODO: describe arguments and output.
USAGE
    exit 64
}}

[ $# -ge 1 ] || usage
input=$1

command -v jq >/dev/null 2>&1 || {{
    echo "error: jq is required but not installed" >&2
    exit 1
}}

# TODO: implement.
echo "processed: ${{input}}"
"""

EXAMPLE_REFERENCE = """# TODO: reference title

## Contents

- [Section one](#section-one)
- [Section two](#section-two)

## Section one

TODO: detail that does not belong in SKILL.md because it is only needed sometimes.

## Section two

TODO.
"""


def normalize(raw: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower())
    return re.sub(r"-{2,}", "-", name).strip("-")


def titleize(name: str) -> str:
    acronyms = {"api", "cli", "mcp", "lsp", "sql", "url", "pdf", "json", "yaml", "http", "ci", "id"}
    words = []
    for index, word in enumerate(name.split("-")):
        if word in acronyms:
            words.append(word.upper())
        elif index == 0:
            words.append(word.capitalize())
        else:
            words.append(word)
    return " ".join(words)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a new GitHub Copilot agent skill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("name", help="skill name (normalized to kebab-case)")
    parser.add_argument(
        "--path",
        default=".",
        help="directory that will contain the new skill folder (default: current directory)",
    )
    parser.add_argument(
        "--description",
        help="frontmatter description; a TODO placeholder is written when omitted",
    )
    parser.add_argument(
        "--structure",
        choices=STRUCTURES,
        default="placeholder",
        help="body skeleton to generate (default: placeholder)",
    )
    parser.add_argument(
        "--resources",
        default="",
        help=f"comma-separated subdirectories to create from: {', '.join(VALID_RESOURCES)}",
    )
    parser.add_argument("--license", help="SPDX license identifier for the frontmatter")
    parser.add_argument("--force", action="store_true", help="write into an existing directory instead of failing")
    args = parser.parse_args(argv)

    name = normalize(args.name)
    if not name:
        print(f"error: {args.name!r} does not normalize to a usable skill name", file=sys.stderr)
        return 1
    if len(name) > MAX_NAME_LEN:
        print(f"error: name exceeds {MAX_NAME_LEN} characters: {name}", file=sys.stderr)
        return 1
    if name != args.name:
        print(f"note: normalized name to {name!r}")

    resources: list[str] = []
    for item in (part.strip() for part in args.resources.split(",")):
        if not item:
            continue
        if item not in VALID_RESOURCES:
            print(
                f"error: unknown resource {item!r}; choose from {', '.join(VALID_RESOURCES)}",
                file=sys.stderr,
            )
            return 1
        resources.append(item)
    if args.structure == "capability" and "scripts" not in resources:
        resources.append("scripts")

    parent = Path(args.path).expanduser()
    skill_dir = parent / name
    if skill_dir.exists() and not args.force:
        print(f"error: {skill_dir} already exists (pass --force to write into it)", file=sys.stderr)
        return 1

    description = args.description or (
        'TODO: what this skill does. Use when the user asks to "TODO", "TODO", or mentions TODO.'
    )
    if len(description) > 1024:
        print("error: description exceeds the 1024 character limit", file=sys.stderr)
        return 1

    skill_dir.mkdir(parents=True, exist_ok=True)
    for resource in resources:
        (skill_dir / resource).mkdir(exist_ok=True)

    license_line = f"license: {args.license}\n" if args.license else ""
    content = SKILL_TEMPLATE.format(
        name=name,
        description=description,
        license_line=license_line,
        title=titleize(name),
        intro="TODO: one or two sentences stating what this skill does and the guarantees it "
        "provides. Do not describe when to use it here — that belongs in the description.",
        body=STRUCTURE_BODIES[args.structure].rstrip(),
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    created = ["SKILL.md"]
    if "scripts" in resources:
        script_name = f"{name}.sh"
        script_path = skill_dir / "scripts" / script_name
        if not script_path.exists():
            script_path.write_text(EXAMPLE_SCRIPT.format(script_name=script_name), encoding="utf-8")
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            created.append(f"scripts/{script_name}")
    if "references" in resources:
        reference_path = skill_dir / "references" / "details.md"
        if not reference_path.exists():
            reference_path.write_text(EXAMPLE_REFERENCE, encoding="utf-8")
            created.append("references/details.md")

    print(f"\nCreated skill: {skill_dir}")
    for item in created:
        print(f"  + {item}")
    for resource in resources:
        print(f"  + {resource}/")

    print(
        "\nNext steps:\n"
        f"  1. Replace every TODO in {skill_dir / 'SKILL.md'}.\n"
        "  2. Rewrite the description: what it does, then `Use when ...` with 2-5 quoted\n"
        "     phrases a user would actually type. This is what makes the skill trigger.\n"
        "  3. Delete any scaffolding section you did not use.\n"
        f"  4. Validate: validate_skill.py {skill_dir}\n"
        "  5. Load it: run `/skills reload` in a session, then `/skills info "
        f"{name}`.\n"
        f"  6. Test explicit invocation (`Use the /{name} skill to ...`), then test that a\n"
        "     natural request triggers it without naming the skill."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
