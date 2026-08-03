# Complete skill examples

Three full skills, from minimal to advanced. Each shows the whole directory, not an
excerpt.

## Contents

- [Minimal: instructions only](#minimal-instructions-only)
- [Standard: instructions plus references](#standard-instructions-plus-references)
- [Advanced: script-backed with progressive disclosure](#advanced-script-backed-with-progressive-disclosure)
- [What changes as skills grow](#what-changes-as-skills-grow)

## Minimal: instructions only

One file. Appropriate when the knowledge is short, stable, and always relevant once the
skill triggers.

```text
.github/skills/conventional-commits/
└── SKILL.md
```

```markdown
---
name: conventional-commits
description: Write commit messages in this repository's Conventional Commits format, including scope and breaking-change footers. Use when the user asks to "commit", "write a commit message", "squash these commits", or mentions conventional commits.
license: MIT
---

# Conventional commits

Every commit message in this repository follows Conventional Commits. CI rejects
non-conforming subjects on protected branches.

## Format

```text
<type>(<scope>): <subject>

<body>

<footer>
```

- `type` is one of `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`.
- `scope` is the package directory name, for example `api`, `web`, `worker`.
- `subject` is imperative, lowercase, no trailing period, at most 72 characters.
- The body explains **why**, not what — the diff already shows what.

## Breaking changes

Append a footer and use `!` after the scope:

```text
feat(api)!: drop support for v1 tokens

BREAKING CHANGE: clients must send v2 tokens. See docs/migrations/v2-tokens.md.
```

## Rules

- One logical change per commit. Split unrelated edits.
- Never reference an internal ticket ID in the subject; put it in the footer as
  `Refs: PROJ-123`.
- Do not add tooling attribution footers unless the user asks for them.
```

## Standard: instructions plus references

Detail that is only needed some of the time moves into `references/`.

```text
.github/skills/github-actions-triage/
├── SKILL.md
└── references/
    ├── common-failures.md
    └── self-hosted-runners.md
```

```markdown
---
name: github-actions-triage
description: Diagnose and fix failing GitHub Actions workflow runs for this repository, including flaky jobs and runner problems. Use when the user asks to "why is CI failing", "fix the build", "debug this workflow", or mentions a red check on a pull request.
license: MIT
---

# GitHub Actions triage

Finds the root cause of a failing workflow run without pulling thousands of log lines
into context.

## Workflow

1. **Find the run.** Use the GitHub MCP server's `list_workflow_runs` tool, filtered to
   the pull request or branch in question. Identify the failing run and its conclusion.
2. **Summarize the failure.** Use `summarize_job_log_failures` first. This returns an AI
   summary of the failing jobs and is almost always enough. Do not fetch raw logs yet.
3. **Fetch detail only if needed.** If the summary is ambiguous, call `get_job_logs` for
   the single failing job. Never call `get_workflow_run_logs` for a matrix build — it
   returns every job.
4. **Classify the failure.** Match it against
   [references/common-failures.md](references/common-failures.md). If the failure is a
   runner or infrastructure problem, read
   [references/self-hosted-runners.md](references/self-hosted-runners.md) instead of
   changing application code.
5. **Reproduce locally.** Run the same command the job ran, from the repository root.
   State clearly if it cannot be reproduced locally.
6. **Fix and verify.** Make the smallest change that addresses the root cause. Re-run the
   workflow and confirm it is green before reporting success.

## Rules

- Never disable a test, skip a job, or add `continue-on-error` to make CI pass. Report the
  problem instead.
- A test that fails intermittently is a bug, not a flake to be retried. Record the run URL
  and the failure rate.
- If the fix touches workflow YAML, validate it with `actionlint` before pushing.
```

## Advanced: script-backed with progressive disclosure

The fragile part is a script; `SKILL.md` documents its interface; deep detail sits in
references.

```text
.github/skills/schema-migration/
├── SKILL.md
├── references/
│   ├── rollback-procedures.md
│   └── locking-behavior.md
├── examples/
│   └── expand-contract.md
└── scripts/
    ├── plan_migration.py
    └── check_locks.sh
```

```markdown
---
name: schema-migration
description: Plan and apply PostgreSQL schema migrations safely against tables with live traffic, using expand/contract and lock-aware ordering. Use when the user asks to "add a migration", "alter a table", "add a column", "add an index", or mentions Alembic revisions. Does not cover data backfills, which are handled by the data-backfill skill.
license: MIT
allowed-tools: shell
---

# Schema migration

Produces migrations that will not take a long-lived lock on a table receiving production
traffic. An `ALTER TABLE` that queues behind a slow query has taken this service down
before; the plan step exists to prevent that.

## Workflow

1. **Describe the intended change** in one sentence and identify every affected table.
2. **Generate a plan.**

   ```bash
   scripts/plan_migration.py --table TABLE --change "add column foo text null"
   ```

   It prints a JSON object with `statements`, `estimated_lock`, and `safe` fields.
3. **Read `safe`.**
   - `safe: true` — continue to step 4.
   - `safe: false` — the change needs the expand/contract pattern. Read
     [examples/expand-contract.md](examples/expand-contract.md) and split the work into
     multiple migrations before continuing.
4. **Check current locks** before applying anything:

   ```bash
   scripts/check_locks.sh
   ```

   Exit code `1` means a long transaction is open. Report it and stop; applying now would
   queue behind it.
5. **Write the Alembic revision** using the exact statements from the plan output. Do not
   hand-edit them — the ordering matters.
6. **Apply to staging**, then verify with `alembic current` and a smoke query.
7. **Record the rollback path** in the revision docstring. Every migration must have one.

## Non-negotiable rules

- Never add a `NOT NULL` column without a default in a single statement on a table over
  one million rows. Use expand/contract.
- Always create indexes with `CONCURRENTLY`, and never inside a transaction.
- Never drop a column in the same release that stops writing to it. Leave one release of
  slack.

## Reference material

- [references/locking-behavior.md](references/locking-behavior.md) — which statements take
  which lock, and what they block. Read this when the plan output is unexpected.
- [references/rollback-procedures.md](references/rollback-procedures.md) — read when a
  migration has partially applied.
- [examples/expand-contract.md](examples/expand-contract.md) — the multi-release pattern
  for unsafe changes.
```

## What changes as skills grow

| | Minimal | Standard | Advanced |
| --- | --- | --- | --- |
| Files | 1 | 3 | 7 |
| Body length | ~40 lines | ~40 lines | ~60 lines |
| Detail lives in | The body | References | References plus scripts |
| Fragile steps | None | None | Delegated to scripts |
| `allowed-tools` | Omitted | Omitted | `shell`, because scripts are the point |

Note that the body does **not** grow much. Added complexity goes into level 3, not into
`SKILL.md`. A 900-line `SKILL.md` is a sign that references were never created, not a sign
of a thorough skill.
