# Contributing

Thanks for helping improve the Copilot Dev Marketplace.

## Ground rules

This repository holds a plugin whose entire purpose is to be **authoritative**. An agent relies on it instead of the docs, so a wrong statement is worse than a missing one.

1. **Every factual claim must be traceable to the official Copilot CLI documentation.** Cite the doc page in your PR description. If the docs are ambiguous, say so in the text rather than guessing.
2. **Stay inside the authoring surface.** In scope: anything an author writes into a file, plus the local development loop. Out of scope: end-user actions such as installing, enabling, or managing plugins.
3. **One authoritative home per concept.** Skills use progressive disclosure. Do not restate the same rule in five files — link to the one place that owns it.

## Setup

Requirements: Python 3.10+, [`ruff`](https://docs.astral.sh/ruff/), and [`ty`](https://docs.astral.sh/ty/). [`uv`](https://docs.astral.sh/uv/) is recommended.

```bash
uv tool install ruff
uv tool install ty
```

The plugin scripts themselves have no required third-party dependencies. PyYAML is optional and only used for faster frontmatter parsing.

## Before opening a pull request

Run all three gates. Each must be clean.

```bash
./scripts/validate-all.sh          # every validator, warnings treated as errors
ruff check plugins/                # lint
ruff format --check plugins/       # formatting
ty check plugins/                  # type checking
```

Then verify the plugin actually loads in a real session:

```bash
copilot --plugin-dir ./plugins/plugin-development
```

`--plugin-dir` reads the working tree directly, so there is no install and no cache to go
stale. Inside the session, run `/skills list` and `/agent` to confirm what loaded. Note
that `copilot skill list` does **not** report `--plugin-dir` skills even though they load
correctly.

Before opening a PR, run the install path once to confirm the packaged layout works:

```bash
copilot plugin install ./plugins/plugin-development
copilot skill list
```

Plugin contents are cached at install time, so reinstall after every edit when testing this
way. Direct local-path installs are deprecated upstream; `--plugin-dir` and a local
marketplace are the durable options.

## Writing skills

- Keep `SKILL.md` focused and under roughly 500 lines. Move depth into `references/`.
- The `description` frontmatter field is the trigger. Describe **when** to use the skill, using concrete phrasings a user would actually say.
- Prefer runnable `examples/` and `scripts/` over prose describing what a file would look like.
- Match the house style of `skills/skill-development/SKILL.md`, which is the style exemplar for the repository.
- Validate with:

  ```bash
  python3 plugins/plugin-development/skills/skill-development/scripts/validate_skill.py <skill-dir>
  ```

## Writing Python scripts

- Scripts must run standalone under `python3` with no required third-party imports. Helpers are duplicated across scripts on purpose so each file can be copied out and used alone.
- Every script needs `--help` and meaningful exit codes: `0` success, `1` findings, `2` usage or I/O error.
- Narrow your exception handlers. Do not use a bare `except Exception` where a specific type applies.
- Suppressions (`# noqa`) require a comment explaining why the rule does not apply.

## Changing a validator

Validators are the repository's safety net, so changes need proof they did not silently alter behavior.

```bash
./scripts/validate-all.sh > /tmp/before.txt 2>&1
# ...make your change...
./scripts/validate-all.sh > /tmp/after.txt 2>&1
diff /tmp/before.txt /tmp/after.txt
```

Any diff must be intentional and explained in the PR.

Two traps worth knowing, both already handled — preserve them:

- Fenced code blocks are stripped before link extraction. Example links inside code fences are not real links.
- Quoted anti-pattern examples are stripped before style heuristics. A skill that documents a bad pattern is not committing it.

## Versioning

Versions live in both `plugins/<name>/plugin.json` and the matching entry in `.github/plugin/marketplace.json`. Keep them in sync:

```bash
python3 plugins/plugin-development/skills/marketplace-development/scripts/bump_version.py \
  plugins/plugin-development/plugin.json \
  --marketplace .github/plugin/marketplace.json \
  --minor
```

## Commit messages

Use imperative mood and explain the *why*. If a change corrects a factual claim, reference the doc page that motivated it.
