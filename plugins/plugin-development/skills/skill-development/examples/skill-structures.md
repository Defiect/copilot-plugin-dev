# Skill body structures

Four skeletons. Pick the one that matches the task, copy it into `SKILL.md`, and delete
the others.

## Contents

- [Workflow-based](#workflow-based)
- [Task-based](#task-based)
- [Reference and guidelines](#reference-and-guidelines)
- [Capability-based](#capability-based)
- [Choosing between them](#choosing-between-them)

## Workflow-based

For a fixed sequence: releases, migrations, incident response, onboarding.

```markdown
---
name: release-cut
description: Cut a tagged release of the service, including changelog, version bump, and pipeline trigger. Use when the user asks to "cut a release", "ship a version", "tag a release", or mentions release notes.
---

# Release cut

Produces a signed tag, a published changelog entry, and a green deploy pipeline.

## Prerequisites

- The working tree is clean and on `main`.
- `gh` is authenticated (`gh auth status`).

## Workflow

1. **Confirm the target version.** Read `CHANGELOG.md` and propose the next semantic
   version. Ask the user to confirm before continuing.
2. **Update the changelog.** Move entries from `## Unreleased` into a new
   `## X.Y.Z - YYYY-MM-DD` section.
3. **Bump the version.** Edit `package.json` only. Do not edit lockfiles by hand.
4. **Commit and tag.** `git commit -am "release: X.Y.Z" && git tag -s vX.Y.Z`
5. **Push.** `git push origin main --follow-tags`
6. **Verify.** `gh run watch` until the release workflow is green. If it fails, report
   the failing job and stop — do not retry automatically.

## When something fails

| Symptom | Cause | Fix |
| --- | --- | --- |
| Tag already exists | Release was partially cut | `git tag -d` locally, confirm with the user before deleting the remote tag |
| Pipeline fails at publish | Expired registry token | Report it; token rotation is a human task |
```

## Task-based

For several independent operations that share conventions.

```markdown
---
name: feature-flags
description: Create, roll out, and retire LaunchDarkly feature flags in this service. Use when the user asks to "add a feature flag", "ramp a flag", "clean up a flag", or mentions LaunchDarkly.
---

# Feature flags

All flags live in `config/flags.yaml` and are mirrored to LaunchDarkly by CI.

## Create a flag

1. Add an entry to `config/flags.yaml` with `key`, `owner`, and `expires` (max 90 days
   out).
2. Reference it through `flags.enabled("key")` — never read the config file directly.
3. Add a test that covers both branches.

## Ramp a flag

Edit only the `rollout` percentage. Never change `key` after creation; a rename orphans
the LaunchDarkly flag and silently disables the feature.

## Retire a flag

1. Confirm the flag has been at 100% for at least seven days.
2. Delete the branch that is now dead, then the `flags.enabled` call, then the YAML entry
   — in that order, so the build stays green at every step.

## Conventions

- Flag keys are `snake_case` and prefixed with the owning team.
- Every flag needs an `expires` date. CI fails on expired flags.
```

## Reference and guidelines

For rules applied while doing something else: standards, review checklists, style guides.

```markdown
---
name: api-design-rules
description: Apply this service's REST API conventions when adding or changing endpoints. Use when the user asks to "add an endpoint", "design an API", "review this route", or mentions request/response shapes.
---

# API design rules

Apply these when adding or modifying any route under `src/api/`.

## Rules

### Resource paths are plural nouns

`/invoices/{id}`, never `/invoice/{id}` or `/getInvoice`. Verbs belong in the HTTP method.

### Every list endpoint is paginated

Accept `limit` (default 50, max 200) and `cursor`. Return `{ "data": [...], "next": "..." }`.
Unbounded lists have caused three incidents.

### Errors use the problem+json shape

```json
{ "type": "https://api.example.com/errors/not-found", "title": "Invoice not found", "status": 404 }
```

### Breaking changes require a new version prefix

Adding an optional field is not breaking. Removing a field, renaming it, or narrowing its
type is.

## Review checklist

- [ ] Path is a plural noun; no verbs
- [ ] List endpoints paginate and cap `limit`
- [ ] Errors use problem+json
- [ ] OpenAPI spec regenerated (`make openapi`)
- [ ] No breaking change without a version bump
```

## Capability-based

For one fragile operation behind a script. Keep the body short: interface, output, limits.

```markdown
---
name: db-anonymize
description: Produce an anonymized copy of a production database dump for local use. Use when the user asks to "anonymize a dump", "get test data", "scrub PII from the database", or mentions a sanitized snapshot.
allowed-tools: shell
---

# Database anonymization

Rewrites every column tagged `pii` in `schema/pii.yaml` with deterministic fake values,
preserving referential integrity. Never run it against a live database.

## Running it

```bash
scripts/anonymize.py --input dump.sql --output dump.anon.sql
```

| Argument | Required | Meaning |
| --- | --- | --- |
| `--input` | Yes | Path to a plain-text `pg_dump` file |
| `--output` | Yes | Destination; refuses to overwrite |
| `--seed` | No | Fixes the fake-value seed for reproducible output |

## Reading the output

The script prints one JSON object per table: `{"table": "users", "rows": 1200, "columns_scrubbed": 4}`.

| Exit code | Meaning | Action |
| --- | --- | --- |
| `0` | Success | Report the table summary |
| `2` | A column tagged `pii` had no rule | Report the column and stop; do not guess a rule |
| `3` | Input is a binary dump | Ask the user to re-export with `pg_dump --format=plain` |

## Constraints

- Plain-text dumps only.
- Does not anonymize JSON blobs; columns of type `jsonb` are rejected with exit 2.
```

## Choosing between them

| Question | Suggests |
| --- | --- |
| Is there one correct order of steps? | Workflow |
| Are there several unrelated operations sharing conventions? | Task |
| Is the skill applied *while* doing other work? | Reference |
| Is one step fragile, numeric, or destructive? | Capability |

Mixing is fine: a task-based skill whose riskiest task delegates to a script is a common
and good shape.
