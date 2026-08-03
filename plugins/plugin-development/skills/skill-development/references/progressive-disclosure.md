# Progressive disclosure

## Contents

- [The three levels](#the-three-levels)
- [Budgets](#budgets)
- [When to split](#when-to-split)
- [Splitting patterns](#splitting-patterns)
- [Referencing files well](#referencing-files-well)
- [Very large references](#very-large-references)
- [Anti-patterns](#anti-patterns)

## The three levels

A skill is loaded in stages so that specialized knowledge costs nothing until it is
needed.

| Level | Content | Loaded | Cost |
| --- | --- | --- | --- |
| 1 | `name` + `description` | Always, for every installed skill | Paid on every request |
| 2 | `SKILL.md` body | When the skill triggers | Paid for the whole session once triggered |
| 3 | `references/`, `examples/`, `scripts/`, `assets/` | When `SKILL.md` directs Copilot to open or run them | Paid only when relevant |

Design each level for its cost. Level 1 is the most expensive per word because every
installed skill pays it on every single request; Level 3 is nearly free.

## Budgets

| Level | Target | Hard limit |
| --- | --- | --- |
| `description` | 100–500 characters | 1024 characters |
| `SKILL.md` body | Under 500 lines / 5,000 words | None enforced, but context is finite |
| A reference file | Whatever the topic needs | None |

A reference file over 100 lines needs a table of contents at the top. A reference file
over roughly 10,000 words should be searched rather than read — say so explicitly.

## When to split

Move content out of `SKILL.md` when **any** of these is true:

- The body exceeds 500 lines or 5,000 words.
- A section is only relevant in a minority of invocations (an edge case, one auth mode,
  one platform).
- A section is a lookup table rather than instructions — an API surface, an error code
  list, a field reference.
- A section is a complete artifact rather than guidance — a full config file, a long
  example.
- Two sections address different audiences (an everyday path and a maintenance path).

Keep content **in** `SKILL.md` when:

- It is needed on essentially every invocation.
- It is a rule that must not be missed (a safety constraint, a destructive-operation
  warning).
- It is the map that tells Copilot which reference to open.

## Splitting patterns

### Pattern 1 — Guide plus references

The default. `SKILL.md` holds the workflow and points at detail.

```text
terraform-review/
├── SKILL.md                    # workflow + when to open each reference
└── references/
    ├── security-rules.md       # opened when the plan touches IAM or networking
    ├── cost-rules.md           # opened when the plan adds resources
    └── state-recovery.md       # opened only when state is corrupt
```

### Pattern 2 — Domain partitioning

One skill covering several domains that never appear together.

```text
warehouse-queries/
├── SKILL.md                    # shared conventions + a routing table
└── references/
    ├── finance-schema.md
    ├── sales-schema.md
    └── product-schema.md
```

`SKILL.md` contains the routing table:

| Question is about | Read |
| --- | --- |
| Revenue, invoices, ledgers | `references/finance-schema.md` |
| Pipeline, accounts, quotas | `references/sales-schema.md` |
| Usage, events, retention | `references/product-schema.md` |

### Pattern 3 — Conditional detail

The common path is inline; the rare path is a reference.

```markdown
Authenticate with a personal access token in `$API_TOKEN`.

For OAuth device-flow or mutual-TLS setups, read `references/authentication.md` first.
```

### Pattern 4 — Script offload

Replace a fragile procedure with a script and describe only its interface. This shrinks
`SKILL.md` and eliminates a class of mistakes at the same time.

```markdown
Run `scripts/rotate-keys.py --env staging`. It prints one JSON object per rotated key.
Exit code 3 means a key was in use and was skipped — report those keys and stop.
```

## Referencing files well

State **when** to open a file, not just that it exists.

| | Example |
| --- | --- |
| ❌ | `See references/authentication.md for more information.` |
| ❌ | `Additional docs are in the references folder.` |
| ✅ | `For OAuth-protected servers, read references/authentication.md before writing the config.` |
| ✅ | `If validation reports an unknown field, look it up in references/manifest-fields.md.` |

Use relative paths from the skill directory, and use Markdown links so tooling can verify
them:

```markdown
[references/authentication.md](references/authentication.md)
```

`scripts/validate_skill.py` reports a broken link as an error, and reports a bundled file
that `SKILL.md` never mentions as a note — unreferenced files are usually dead weight.

## Very large references

For a reference big enough that reading it wastes more context than it saves, give Copilot
a search strategy instead:

```markdown
`references/api-catalog.md` lists all 400 endpoints. Do not read it end to end — grep it
for the resource name, for example `grep -n "^### /billing/invoices" references/api-catalog.md`,
then read only that section.
```

## Anti-patterns

| Anti-pattern | Why it hurts | Instead |
| --- | --- | --- |
| Nested references (a reference linking to another reference) | Copilot chases files instead of working | Keep references one level deep from `SKILL.md` |
| `README.md` inside the skill directory | Duplicates `SKILL.md`, loads as noise | Put it in the plugin or repo README |
| Splitting a 200-line body into six files | Fragmentation costs more than it saves | Split only past the budget or by relevance |
| A reference that is never mentioned in `SKILL.md` | Never loaded; pure dead weight | Link it, or delete it |
| Duplicating the same rule in body and reference | The two copies drift apart | State it once, in the place it is always needed |
| A body that is a table of contents and nothing else | Forces a second read for every task | Keep the common path inline |
