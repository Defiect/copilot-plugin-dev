# Minimal plugin

The smallest useful plugin: one manifest, one skill.

## Directory

```text
release-notes-conventions/
├── plugin.json
├── LICENSE
├── README.md
└── skills/
    └── release-notes/
        └── SKILL.md
```

`README.md` and `LICENSE` are for humans browsing the repository. Copilot reads neither.

## `plugin.json`

```json
{
  "name": "release-notes-conventions",
  "description": "Acme's release notes format and changelog conventions.",
  "version": "1.0.0",
  "author": { "name": "Acme Docs Team" },
  "license": "MIT"
}
```

No component fields. `skills/` is found automatically.

## `skills/release-notes/SKILL.md`

```markdown
---
name: release-notes
description: Writes release notes and changelog entries in Acme's house format, grouping changes by audience impact rather than by commit type. Use when the user asks to "write release notes", "update the changelog", "summarize what changed in this release", or mentions a version bump. Does not cover choosing the version number.
license: MIT
---

# Release notes

Acme release notes are read by customers, not by engineers. Group by what changed for the
reader, never by commit type.

## Structure

```text
## <version> — <YYYY-MM-DD>

### What's new
### What's improved
### What's fixed
### Breaking changes
### Upgrade notes
```

Omit any section with no entries. Never ship an empty heading.

## Rules

- One entry per user-visible change. Internal refactors do not appear.
- Write each entry as an outcome: "Exports now include archived records", not
  "Fixed export filter bug".
- Every breaking change entry links to a migration section in the docs.
- Link the pull request number at the end of the entry in parentheses.
- Never use the words "various", "misc", or "improvements" as an entry.

## Sourcing entries

1. List merged pull requests since the previous tag.
2. Discard entries labelled `internal` or `chore`.
3. Rewrite each remaining title as a user-facing outcome.
4. Ask the user about anything ambiguous rather than guessing at impact.
```

## Load and verify

```bash
copilot --plugin-dir ./release-notes-conventions
```

Then, in that session, say "write the release notes for 2.4.0". If the skill does not
activate, the `description` is the thing to fix.

## Why this is enough

The plugin adds roughly 60 tokens of always-on context, requires no privileges, has no
runtime dependencies, and cannot break a session. Most plugins should look like this. Add a
second component only when a concrete need appears.
