# Writing skill descriptions

## Contents

- [Why the description is everything](#why-the-description-is-everything)
- [The formula](#the-formula)
- [Grading rubric](#grading-rubric)
- [Before and after](#before-and-after)
- [Disambiguating overlapping skills](#disambiguating-overlapping-skills)
- [Diagnosing trigger failures](#diagnosing-trigger-failures)

## Why the description is everything

Copilot keeps every installed skill's `name` and `description` in context permanently, but
loads a skill's body only after deciding the skill is relevant. That decision is made
**from the description alone**.

Two consequences follow, and almost every broken skill violates one of them:

1. A "When to use this skill" section in the body is useless. By the time it is read, the
   decision has already been made. Move it into the description.
2. A vague description cannot be rescued by an excellent body. If the skill never
   triggers, the body never runs.

## The formula

> `<What it does, third person, concrete>. Use when <situation>, or when the user asks to "<phrase>", "<phrase>", "<phrase>".`

Optionally add a boundary clause:

> `... Does not cover <adjacent thing>.`

Target 100–500 characters. Under 40 characters is rejected by validation; over 1024 is
rejected by the CLI.

Elements, in order of impact:

| Element | Why it matters |
| --- | --- |
| Quoted user phrasing | The strongest trigger signal — matches what a user actually types |
| Explicit `Use when` clause | Separates capability from applicability |
| Distinguishing nouns | File types, tool names, systems (`AcroForm`, `Terraform`, `.ipynb`) |
| Boundary clause | Prevents over-triggering and collisions with sibling skills |
| Third person | Describes the skill; second person reads as instructions to the user |

## Grading rubric

Score a description out of 5. Anything below 4 needs a rewrite.

| Point | Criterion |
| --- | --- |
| 1 | States concretely what the skill does |
| 1 | Contains an explicit `Use when ...` (or equivalent) clause |
| 1 | Quotes at least two realistic user phrasings |
| 1 | Names a distinguishing technology, file type, or system |
| 1 | Is 100–500 characters and free of second-person phrasing |

## Before and after

### 1. Too vague

❌ `Helps with database work.`

Fails on every criterion. It will either never trigger or trigger constantly.

✅ `Generate, review, and apply Alembic migrations for the PostgreSQL schema in db/. Use when the user asks to "add a migration", "change the schema", "alter a table", or mentions Alembic revisions. Does not cover data backfills.`

### 2. Second person and no triggers

❌ `You can use this when you need to work with our API.`

✅ `Call the internal Billing API v3 with the correct auth headers and pagination. Use when the user asks to "look up an invoice", "check a subscription", or mentions billing API endpoints.`

### 3. Describes implementation instead of purpose

❌ `A Python script that wraps pdftk and iterates over form field dictionaries.`

The user does not think in terms of `pdftk`. Describe the outcome, then the trigger.

✅ `Fill in and flatten AcroForm PDF fields from a JSON data file. Use when the user asks to "fill a PDF form", "populate a PDF", or mentions AcroForm fields. Does not handle scanned image PDFs.`

### 4. Over-broad, collides with everything

❌ `Handles all testing tasks in this repository.`

✅ `Write and run Playwright end-to-end tests for the web app in apps/web. Use when the user asks to "add an e2e test", "fix a flaky Playwright test", or mentions browser tests. Unit tests are handled separately by the jest-testing skill.`

### 5. Missing the body/description split

❌ Description: `Deployment helper.`
   Body: `## When to use this skill\nUse this when deploying to staging or production...`

✅ Description: `Deploy the service to staging or production using the release pipeline, including migration ordering and rollback. Use when the user asks to "deploy", "ship to staging", "cut a release", or "roll back".`
   Body: starts directly with the prerequisites and the workflow.

## Disambiguating overlapping skills

When two skills could plausibly serve the same request, make each description exclude the
other explicitly. Mutual exclusion is far more reliable than hoping Copilot infers the
boundary.

```yaml
# skills/jest-testing/SKILL.md
description: >-
  Write and debug Jest unit tests for TypeScript packages under packages/.
  Use when the user asks to "add a unit test", "fix a failing Jest test", or mentions
  mocks and spies. End-to-end browser tests are handled by the playwright-testing skill.
```

```yaml
# skills/playwright-testing/SKILL.md
description: >-
  Write and debug Playwright end-to-end browser tests for apps/web.
  Use when the user asks to "add an e2e test", "fix a flaky browser test", or mentions
  page objects or selectors. Unit tests are handled by the jest-testing skill.
```

## Diagnosing trigger failures

Work through these in order. Each step isolates a different cause.

1. **Is the skill loaded at all?** Run `/skills list`. If it is absent, the problem is
   location or filename, not the description.
2. **Does the body work?** Invoke it explicitly: `Use the /skill-name skill to ...`. If
   the result is good, the body is fine and the description is the only remaining
   variable.
3. **Does a literal phrasing trigger it?** Type one of the exact phrases quoted in the
   description. If that fails, the description is too abstract, or another skill is
   winning; check `/skills info skill-name` for a name collision.
4. **Does a natural phrasing trigger it?** Ask the way a real user would, without any
   quoted phrase. If step 3 works but step 4 does not, add more phrasings — collect them
   from real requests rather than inventing them.
5. **Does it trigger when it should not?** Add a boundary clause and narrow the nouns.

Record the phrasings that failed, add them to the description verbatim, and re-test in a
fresh session. Descriptions improve empirically, not by introspection.
