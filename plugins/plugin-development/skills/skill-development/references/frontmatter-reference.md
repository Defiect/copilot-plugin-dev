# SKILL.md frontmatter reference

## Contents

- [Format](#format)
- [Fields](#fields)
- [`name`](#name)
- [`description`](#description)
- [`license`](#license)
- [`allowed-tools`](#allowed-tools)
- [`argument-hint`](#argument-hint)
- [`user-invocable` and `disable-model-invocation`](#user-invocable-and-disable-model-invocation)
- [Fields from other tools](#fields-from-other-tools)
- [Validation rules in one table](#validation-rules-in-one-table)
- [Common frontmatter errors](#common-frontmatter-errors)

## Format

`SKILL.md` begins with a YAML block delimited by `---` on the very first line and closed
by a matching `---`:

```markdown
---
name: skill-name
description: What it does. Use when ...
---

Body starts here.
```

Hard requirements:

- The opening `---` must be the **first three characters of the file**. A blank line, a
  UTF-8 BOM, or an HTML comment before it prevents the frontmatter from being recognized
  and the skill silently fails to load.
- The block must be closed. An unclosed block swallows the entire body.
- The content must be a YAML **mapping** (`key: value` pairs), not a list or scalar.
- The file must be named exactly `SKILL.md` — uppercase, with that extension.

Quote any value containing a colon followed by a space, a leading `[`, `{`, `*`, `&`,
`#`, or `%`, or a string that YAML would read as a boolean (`yes`, `no`, `on`, `off`):

```yaml
description: "Deploy: build, upload, and verify. Use when the user says \"ship it\"."
```

## Fields

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `name` | string | Yes | Unique identifier, and the `/name` invocation token |
| `description` | string | Yes | What the skill does and when Copilot should load it |
| `argument-hint` | string | No | Freeform hint describing expected arguments, shown in the skill picker |
| `allowed-tools` | string or list | No | Tools pre-approved for this skill |
| `user-invocable` | boolean | No | Whether users can run `/name`. Default `true` |
| `disable-model-invocation` | boolean | No | Prevent the agent from loading the skill on its own. Default `false` |
| `license` | string | No | License that applies to the skill's contents |

Copilot CLI ignores unrecognized keys. They are harmless but misleading, so remove them.

## `name`

- Lowercase letters, digits, and single hyphens: `pdf-form-filling`, `k8s-triage`.
- Maximum 64 characters.
- Should equal the skill's directory name. When they differ, users see the directory in
  the filesystem but must type the frontmatter `name` as `/name`, which causes confusion.
- Skills are **deduplicated by `name`**. If two skills share a name, only the one from the
  highest-precedence root loads and the other is silently dropped. Prefix names that could
  collide (`acme-deploy` rather than `deploy`).
- Avoid generic names — `helper`, `tool`, `utils`, `assistant`, `misc` — which both
  collide easily and give Copilot no signal.

## `description`

The only part of a skill that is always in context. Maximum 1024 characters.

Write it in the third person, describing the skill rather than addressing the user, and
include the situations and phrasings that should trigger it. See
[description-writing.md](description-writing.md) for rewrites and a grading rubric.

Avoid `<` and `>` in the value: some clients that consume the same Agent Skills format
reject angle brackets, so omitting them keeps the skill portable.

## `license`

A short SPDX identifier (`MIT`, `Apache-2.0`) or a sentence pointing at a license file.
Set it on any skill you publish. It does not affect runtime behavior.

## `allowed-tools`

Names the tools Copilot may use from this skill **without asking for confirmation each
time**. Accepts a comma-separated string or a YAML list:

```yaml
allowed-tools: shell
```

```yaml
allowed-tools:
  - view
  - glob
```

Security guidance:

- Pre-approving `shell`, `bash`, or `powershell` removes the confirmation step for running
  terminal commands. A prompt injection that reaches a pre-approved skill can then execute
  arbitrary commands in the user's environment.
- Only pre-approve command execution when you have reviewed every bundled script and you
  control the distribution channel.
- Read-only tools (`view`, `glob`, `grep`) are far lower risk.
- When in doubt, omit the field entirely. Copilot will ask, which costs one keystroke.

## `argument-hint`

A freeform string shown next to the skill in the picker to describe what the skill expects
after `/name`:

```yaml
argument-hint: "[target] [mode]"
```

It is documentation only — Copilot does not parse, validate, or enforce it, and the skill
still receives whatever the user typed. Use it when the skill is meaningfully driven by
arguments; omit it when the skill reads its inputs from the conversation.

## `user-invocable` and `disable-model-invocation`

These two booleans control the skill's two independent entry points. Copilot can reach a
skill because the user typed `/name`, or because the model decided the description matched
the task. Each field switches off one path:

| Field | Default | `true` means |
| --- | --- | --- |
| `user-invocable` | `true` | (default) the skill appears in the picker and `/name` works |
| `disable-model-invocation` | `false` | the model may **not** load the skill on its own |

```yaml
user-invocable: false          # agent-only: no /name, no picker entry
disable-model-invocation: true # user-only: appears in the picker, never auto-loads
```

Guidance for plugin authors:

- **Leave both at their defaults for most skills.** A well-written `description` is a
  better filter than switching off a whole invocation path.
- Set `user-invocable: false` for internal helper skills a user would never invoke
  directly — this keeps the picker uncluttered without deleting the skill.
- Set `disable-model-invocation: true` for skills with side effects the user must
  explicitly ask for (deploys, releases, destructive migrations), so an over-eager
  description match cannot trigger them.
- Setting **both** makes the skill unreachable. The validator flags this.
- `user-invocable: false` also removes the skill from scheduled prompts, which can only
  run user-invocable skills.

## Fields from other tools

The Agent Skills format is shared across several AI systems, so you will encounter keys
that Copilot CLI does not use. They are ignored rather than rejected:

| Key | Origin | Copilot CLI behavior |
| --- | --- | --- |
| `version` | Various | Ignored; version the plugin or repository instead |
| `metadata` | Codex | Ignored |
| `allowed_tools` (underscore) | Older tooling | Ignored — use `allowed-tools` |
| `compatible-clients` | Cross-tool | Ignored |

Keeping them costs context and implies behavior that does not exist. Remove them unless
the same directory is genuinely consumed by another tool.

## Validation rules in one table

| Rule | Severity |
| --- | --- |
| File named exactly `SKILL.md` | Error |
| Frontmatter present and closed | Error |
| Frontmatter parses as a mapping | Error |
| `name` present, kebab-case, ≤ 64 chars | Error |
| `description` present, ≤ 1024 chars | Error |
| `description` ≥ 40 chars | Error |
| `name` matches the directory name | Warning |
| `description` contains a `Use when ...` clause | Warning |
| `description` between 100 and 500 chars | Warning outside range |
| Unknown frontmatter keys | Warning |
| `user-invocable: false` combined with `disable-model-invocation: true` | Warning |
| `allowed-tools` includes `shell`/`bash` | Warning |
| Body under 500 lines / 5,000 words | Warning above |
| Every referenced bundled file exists | Error |
| Referenced paths stay inside the skill directory | Error |

`scripts/validate_skill.py` implements all of these.

## Common frontmatter errors

| Written | Result |
| --- | --- |
| Blank line before the opening `---` | Frontmatter not detected; skill never loads |
| `Name:` instead of `name:` | Missing required field; YAML keys are case-sensitive |
| `description: Deploy: build and ship` | YAML parse error from the unquoted colon |
| `allowed-tools: [shell]` in a file also read by other tools | Fine for Copilot; check the other tool's parser |
| Frontmatter closed with `***` or `___` | Block never closes; the whole file is treated as frontmatter |
| Tabs used for indentation | YAML forbids tabs; use spaces |
