---
name: skill-development
description: Create, review, and improve agent skills (SKILL.md files) for GitHub Copilot. Use when the user asks to "create a skill", "write a SKILL.md", "add an agent skill", "improve a skill description", "why isn't my skill triggering", "review my skill", or wants guidance on skill frontmatter, progressive disclosure, bundled scripts, allowed-tools, or where skills are discovered from.
license: MIT
---

# Skill development

A skill is a folder containing a `SKILL.md` file, plus optional references, examples,
scripts, and assets. Copilot loads a skill's instructions **only when it decides the skill
is relevant**, which keeps specialized knowledge out of the context window until it is
needed.

Use this skill to author new skills, diagnose skills that never trigger, and review
existing skills against the GitHub Copilot spec.

## Core principles

**1. Assume Copilot is already competent.** The context window is a shared, finite
resource. Only add what Copilot does not already know: project-specific procedures,
non-obvious API contracts, house conventions, exact command invocations. Delete anything
that merely restates general software knowledge. Challenge every paragraph with: *does
this justify its token cost?*

**2. Only the description is always loaded.** Copilot sees the skill `name` and
`description` at all times, and the body **only after** the skill triggers. Therefore all
"when to use this" information belongs in the `description`, never in the body.

**3. Set appropriate degrees of freedom.** Match how prescriptive the instructions are to
how fragile the task is.

| Task character | Freedom | What to write |
| --- | --- | --- |
| Many valid approaches, needs judgement | High | Prose guidance, principles, heuristics |
| A preferred sequence with variation | Medium | A numbered workflow with decision points |
| Fragile, error-prone, must be exact | Low | A script with few parameters; tell Copilot to run it |

Think of it as a route: an open field allows many paths (high freedom); a narrow bridge
over a cliff needs guardrails (low freedom). Writing a script is the strongest guardrail
available — prefer it whenever a mistake is expensive and the correct steps are fixed.

**4. Write in the imperative.** Address the reader as an agent receiving instructions:
"To convert the file, run `convert.sh`" — not "You should run" or "The user might want".

## Creating a skill: the 6-step loop

1. **Understand the need.** What concrete task will Copilot perform? What does it get
   wrong today without the skill? Ask the user for a real failing example before writing.
2. **Plan the contents.** Decide the skill name, the trigger phrases, and which of the
   four structures below fits. Decide what becomes a script versus prose.
3. **Scaffold.** Run `scripts/init_skill.py NAME --path DIR` to create the directory and
   a `SKILL.md` skeleton with the correct frontmatter.
4. **Write the body.** Follow the structure patterns and style rules below.
5. **Validate.** Run `scripts/validate_skill.py PATH`. Fix every error and consider every
   warning.
6. **Evaluate and iterate.** Test with fresh subagents as described in
   [references/evaluation-and-iteration.md](references/evaluation-and-iteration.md).
   Skills are rarely right on the first pass.

## Where skills live

Copilot CLI discovers skills from several roots. Only the **first** skill found with a
given `name` loads; the rest are silently ignored.

| Order | Location | Scope |
| --- | --- | --- |
| 1 | `<project>/.github/skills/` | Project |
| 2 | `<project>/.agents/skills/` | Project |
| 3 | `<project>/.claude/skills/` | Project |
| 4 | `<parents>/.github/skills/` etc. | Inherited (monorepo) |
| 5 | `~/.copilot/skills/` | Personal |
| 6 | `~/.agents/skills/` | Personal |
| 7 | A plugin's `skills/` directory | Plugin |
| 8 | `COPILOT_SKILLS_DIRS` env var and config | Custom |

Because plugin skills load **last**, a project or personal skill with the same name
always wins. Choose distinctive names when shipping a skill in a plugin, and see
[references/distribution.md](references/distribution.md) for the trade-offs between
project, personal, and plugin distribution.

## Directory anatomy

```text
skill-name/
├── SKILL.md          # Required. Frontmatter + instructions.
├── references/       # Docs Copilot reads on demand
│   └── api-details.md
├── examples/         # Complete, runnable, copy-pasteable samples
│   └── config.json
├── scripts/          # Executables Copilot runs
│   └── convert.sh
└── assets/           # Templates, fonts, images used in output
    └── report-template.html
```

The directory name must be lowercase with hyphens, and should match the frontmatter
`name`. All bundled files must live inside the skill folder — a skill is distributed as a
self-contained directory, so a path that escapes it will break on someone else's machine.

**Do not add** `README.md`, `CHANGELOG.md`, `INSTALL.md`, or `QUICKSTART.md` inside a
skill directory. They duplicate `SKILL.md`, add clutter, and get loaded as noise. Put
that content in the plugin or repository README instead.

## Frontmatter

`SKILL.md` starts with YAML frontmatter delimited by `---` on the first line.

```markdown
---
name: pdf-form-filling
description: Fill in and flatten AcroForm PDF fields from a JSON data file. Use when the user asks to "fill a PDF form", "populate a PDF", or mentions AcroForm fields.
license: MIT
---
```

| Field | Required | Rules |
| --- | --- | --- |
| `name` | Yes | Lowercase letters, digits, hyphens. Max 64 chars. Should match the directory name. This is what users type as `/name`. |
| `description` | Yes | Max 1024 chars. What the skill does **and** when to use it. |
| `argument-hint` | No | Freeform hint shown in the skill picker, for example `"[target] [mode]"`. |
| `allowed-tools` | No | Tools pre-approved for this skill, skipping the confirmation prompt. |
| `user-invocable` | No | Default `true`. Set `false` to hide the skill from `/name` and the picker. |
| `disable-model-invocation` | No | Default `false`. Set `true` to stop the agent loading the skill on its own. |
| `license` | No | An SPDX identifier or short license statement. |

Those are all the fields Copilot CLI reads; any other key is ignored. Setting both
`user-invocable: false` and `disable-model-invocation: true` makes the skill unreachable.
Full details, defaults, and cross-tool compatibility notes are in
[references/frontmatter-reference.md](references/frontmatter-reference.md).

### `allowed-tools` is a security decision

Listing `shell` or `bash` in `allowed-tools` removes the confirmation step before Copilot
runs terminal commands from this skill. Only do this when every bundled script has been
reviewed and the skill comes from a trusted source, because a prompt injection reaching a
pre-approved skill can execute arbitrary commands. When in doubt, omit the field and let
Copilot ask.

## Writing the description

The description is the single highest-leverage part of a skill. It is the only signal
Copilot has when deciding whether to load the skill, so it must be **specific** and
**contain the words a user would actually say**.

Use this shape:

> `<What it does>. Use when <situation>, or when the user asks to "<phrase>", "<phrase>", "<phrase>".`

| | Example |
| --- | --- |
| ❌ | `Helps with PDFs.` — no trigger, no scope |
| ❌ | `Use this skill when working with documents.` — vague, will over-trigger |
| ❌ | `You should use this to fill forms.` — second person, no trigger phrases |
| ✅ | `Fill in and flatten AcroForm PDF fields from a JSON data file. Use when the user asks to "fill a PDF form", "populate a PDF", or mentions AcroForm fields.` |

Checklist for a good description:

- [ ] States concretely what the skill does, in the third person.
- [ ] Contains an explicit `Use when ...` clause.
- [ ] Quotes 2–5 phrases a user would realistically type.
- [ ] Names the distinguishing technology, file type, or system.
- [ ] Excludes neighbouring cases if the skill could be confused with another
      (`... Does not handle scanned image PDFs.`).
- [ ] Is between roughly 100 and 500 characters. Under 40 is almost always too vague;
      over 1024 is rejected.

More worked before/after rewrites are in
[references/description-writing.md](references/description-writing.md).

## Progressive disclosure

Skills load in three levels. Keep each level as small as it can be.

| Level | Content | When loaded | Budget |
| --- | --- | --- | --- |
| 1 | `name` + `description` | Always | ~100 words |
| 2 | `SKILL.md` body | When the skill triggers | < 500 lines, < 5,000 words |
| 3 | `references/`, `examples/`, `scripts/` | When `SKILL.md` points to them | Large is fine |

Rules that follow from this:

- When the body approaches 500 lines, move detail into `references/` and link to it.
- Give any reference file over 100 lines a table of contents at the top.
- Keep references **one level deep**. A reference that points to another reference makes
  Copilot chase files instead of doing work.
- For a reference over ~10,000 words, tell Copilot how to search it rather than read it:
  *"Grep `references/api.md` for the endpoint name rather than reading the whole file."*
- Reference files from `SKILL.md` with relative paths and say **when** to open them:
  *"For OAuth-protected servers, read `references/authentication.md`."*

## Four structures for a skill body

Pick the one that matches the task and delete the rest.

**Workflow-based** — a fixed sequence. Use for release processes, migrations, incident
response. Number the steps; add a "Verify" step at the end.

**Task-based** — several related but independent operations. Use for a toolkit skill
(create / update / delete / inspect). Give each task its own `##` heading so Copilot can
jump straight to it.

**Reference and guidelines** — rules to apply while doing something else. Use for coding
standards, review checklists, style guides. Organize as rules with a rationale and an
example for each.

**Capability-based** — one capability exposed through a script. Use when the operation is
fragile. Keep `SKILL.md` short: what the script does, how to call it, how to read its
output, and what to do when it fails.

Skeletons for each are in [examples/skill-structures.md](examples/skill-structures.md).

## Bundling scripts

When a skill invokes a script, Copilot discovers every file in the skill directory, so a
relative reference is enough:

```markdown
To convert the diagram, run `scripts/svg-to-png.sh` from this skill's directory, passing
the input SVG path as the first argument. The script writes the PNG next to the input and
prints its path. If it exits non-zero, report the stderr text and stop.
```

Requirements for bundled scripts:

- Start with a shebang (`#!/usr/bin/env bash`, `#!/usr/bin/env python3`) and be executable
  (`chmod +x`).
- Use `set -euo pipefail` in bash so failures surface instead of silently continuing.
- Depend only on tooling you state in `SKILL.md`, and fail with a clear message when a
  dependency is missing.
- Print machine-readable output when Copilot needs to act on the result.
- Never require an interactive prompt; take arguments or environment variables instead.
- Ship a cross-platform pair (`.sh` and `.ps1`) when the skill should work on Windows.

## Style rules

| Rule | ❌ Avoid | ✅ Prefer |
| --- | --- | --- |
| Imperative form | "You should validate the file first." | "Validate the file before uploading." |
| Concrete over abstract | "Handle errors appropriately." | "On a 429, retry twice with 2s and 8s backoff, then report the failure." |
| No time-relative claims | "The new API (as of 2024) ..." | "Use the `v2` endpoint." |
| One canonical way | "You could use curl, httpie, or requests." | "Use `curl`. See `examples/request.sh`." |
| No meta-commentary | "This skill was written to help with ..." | *(delete it)* |
| No trigger info in the body | "## When to use this skill" | *(move it into `description`)* |

## Validating

```bash
# Validate a single skill
scripts/validate_skill.py path/to/skill-name

# Validate every skill under a directory, as CI would
scripts/validate_skill.py --recursive .github/skills --warnings-as-errors
```

The validator checks frontmatter presence and closure, the `name` pattern and length, the
`description` length and trigger phrasing, unknown frontmatter keys, name/directory
agreement, body size, broken links to bundled files, script shebang/permission mismatches,
paths that escape the skill directory, and risky `allowed-tools` values.

## Loading and testing a skill

1. Place the skill in `.github/skills/NAME/` (project) or `~/.copilot/skills/NAME/`
   (personal), or add it to a plugin's `skills/` directory.
2. In an interactive session run `/skills reload`, or start a new session.
3. Confirm it is registered: `/skills list`, then `/skills info NAME` to see its
   resolved location and source.
4. Invoke it explicitly first: `Use the /NAME skill to ...`. If that works, the body is
   fine and any remaining problem is in the description.
5. Then test **implicit** triggering by phrasing a request the way a user would, without
   naming the skill. If it does not trigger, the description is the thing to fix.

From the terminal, `copilot skill list --json` shows the same information without starting
a session. (`copilot plugins list --kind skill` covers more component kinds, but the plural
`plugins` command family is gated and unavailable in some builds.)

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Skill never appears in `/skills list` | Wrong filename or location | The file must be named exactly `SKILL.md`, inside its own subdirectory of a skills root |
| Skill listed but never triggers | Description too vague | Add explicit `Use when ...` plus quoted user phrasing |
| Triggers on unrelated requests | Description too broad | Narrow the scope and state what it does *not* cover |
| A different skill loads instead | Name collision | Skills dedupe by `name`, first root wins; rename or check `/skills info` |
| Changes have no effect | Cached or not reloaded | Run `/skills reload`; for a plugin, reinstall it with `copilot plugin install ./path` |
| Script "not found" when Copilot runs it | Non-relative path or missing `chmod +x` | Reference paths relative to the skill directory and mark scripts executable |
| Copilot asks permission every run | `allowed-tools` not set | Only add `shell` after reviewing the bundled scripts |

## Reference material

- [references/frontmatter-reference.md](references/frontmatter-reference.md) — every
  frontmatter field, validation rules, and cross-tool compatibility.
- [references/description-writing.md](references/description-writing.md) — before/after
  rewrites and a description grading rubric.
- [references/progressive-disclosure.md](references/progressive-disclosure.md) — budgets,
  splitting patterns, and how to reference large files.
- [references/evaluation-and-iteration.md](references/evaluation-and-iteration.md) —
  forward-testing skills with subagents without leaking answers.
- [references/distribution.md](references/distribution.md) — project vs personal vs plugin
  distribution, and installing skills for other people.
- [examples/skill-structures.md](examples/skill-structures.md) — skeletons for the four
  body structures.
- [examples/complete-skill-examples.md](examples/complete-skill-examples.md) — three full
  skills of increasing complexity.

To review someone else's skill rather than write one, delegate to the `skill-reviewer`
agent, which grades a skill against this guidance and returns prioritized fixes.
