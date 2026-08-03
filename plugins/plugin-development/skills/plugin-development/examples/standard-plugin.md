# Standard plugin

Two skills, one agent, bundled scripts, and a marketplace entry. This is the shape most
production plugins reach.

## Directory

```text
acme-migrations/
├── plugin.json
├── LICENSE
├── README.md
├── .github/
│   ├── plugin/
│   │   └── marketplace.json
│   └── workflows/
│       └── validate.yml
├── agents/
│   └── acme-migration-reviewer.agent.md
└── skills/
    ├── acme-schema-migration/
    │   ├── SKILL.md
    │   ├── references/
    │   │   ├── locking-behavior.md
    │   │   └── rollback-procedures.md
    │   ├── examples/
    │   │   └── expand-contract.md
    │   └── scripts/
    │       ├── plan_migration.py
    │       └── check_locks.sh
    └── acme-data-backfill/
        ├── SKILL.md
        └── references/
            └── batching.md
```

Note the namespaced skill names. Plugins load last, so an unnamespaced skill `name` loses
every collision. The agent filename carries the same prefix for readability only — plugin
agents are namespaced automatically as `acme-migrations:acme-migration-reviewer`.

## `plugin.json`

```json
{
  "name": "acme-migrations",
  "description": "Safe PostgreSQL schema migration and data backfill procedures for Acme services.",
  "version": "1.3.0",
  "author": {
    "name": "Acme Data Platform",
    "email": "data-platform@acme.example"
  },
  "homepage": "https://github.com/acme/acme-migrations",
  "repository": "https://github.com/acme/acme-migrations",
  "license": "Apache-2.0",
  "category": "database",
  "keywords": ["postgres", "migration", "alembic", "backfill"]
}
```

Still no component fields — `skills/` and `agents/` are both at their default locations.

## The agent

`agents/acme-migration-reviewer.agent.md`:

```markdown
---
description: Reviews a proposed database migration for locking risk, rollback safety, and expand/contract compliance before it is applied. Use when a migration file has been written and needs review, when the user asks "is this migration safe", or before applying anything to a table with production traffic.
name: Acme migration reviewer
tools: [read, search]
---

You are a database reliability reviewer. You have seen an `ALTER TABLE` take a service
down. You approve migrations only when they cannot.

## Core responsibilities

1. Determine which lock each statement acquires and what that lock blocks.
2. Verify the migration follows expand/contract when it touches a table over one million
   rows.
3. Verify a rollback path exists and is stated in the revision docstring.
4. Verify indexes are created `CONCURRENTLY` and outside a transaction.

## Process

1. Read the migration file and every file it imports.
2. Identify each affected table and estimate its size from any available schema or
   fixture evidence. If size cannot be determined, say so and assume it is large.
3. Classify every statement by lock level.
4. Check the rollback path. A migration with no stated rollback fails review.
5. Produce the report below. Never edit the migration — you have no edit tool, and
   recommendations belong to the author.

## Quality standards

- Every finding cites the exact line.
- Every finding states the production consequence, not just the rule violated.
- An absent rollback path is always Critical.
- "Looks fine" is not a verdict. Use the format below.

## Output format

```text
## Migration review: <file>

**Verdict:** APPROVE | APPROVE WITH CHANGES | REJECT

### Critical
- <line>: <finding> — <production consequence>

### Major
- <line>: <finding> — <production consequence>

### Minor
- <line>: <finding>

### Lock analysis
| Statement | Lock | Blocks | Duration risk |

### Rollback
<the stated rollback path, or "MISSING">
```

If any Critical finding exists, the verdict is REJECT.
```

Note the restricted tool set: `read` and `search`, with no `edit` and no `execute`. A
reviewer that can edit will fix things instead of reporting them.

## The marketplace entry

`.github/plugin/marketplace.json`:

```json
{
  "name": "acme-plugins",
  "owner": {
    "name": "Acme Platform",
    "email": "platform@acme.example"
  },
  "metadata": {
    "description": "Internal Copilot CLI plugins for Acme engineering.",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "acme-migrations",
      "source": "./",
      "description": "Safe PostgreSQL schema migration and data backfill procedures for Acme services.",
      "version": "1.3.0",
      "license": "Apache-2.0",
      "category": "database"
    }
  ]
}
```

Users then run:

```bash
copilot plugin marketplace add acme/acme-migrations
copilot plugin install acme-migrations@acme-plugins
```

## Continuous validation

`.github/workflows/validate.yml` runs the validators on every push so a broken manifest or a
dangling reference link never reaches a user. See this repository's own workflow for a
working example.

## What changed from the minimal plugin

| | Minimal | Standard |
| --- | --- | --- |
| Components | 1 skill | 2 skills, 1 agent |
| Bundled files | 0 | 6 |
| Always-on context | ~60 tokens | ~250 tokens |
| Distribution | Local path install | Marketplace |
| CI | None | Validators on every push |
| Namespacing | Not needed | Required — collisions become likely |
