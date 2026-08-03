# AGENTS.md

Operating guide for AI agents working in this workspace. Read this fully before making
changes.

## What this project is

We are building a **GitHub Copilot CLI plugin marketplace** from scratch, containing a
`plugin-development` plugin whose job is to teach and tool the creation of Copilot CLI
plugins, skills, agents, hooks, MCP servers, LSP servers, and marketplaces.

The Copilot CLI harness has its own plugin/skill spec but ships **no** canonical
"plugin creation" or "skill creation" capability. Codex and Claude Code both do. This
project fills that gap for Copilot CLI.

### The two deliverables the user asked for

1. A **plugin development plugin**.
2. A **skill development skill** (permitted to live inside that plugin — it does).

### The yardsticks

Quality must match or exceed these two reference implementations, both cloned locally:

| Harness | Path | What to take from it |
| --- | --- | --- |
| Claude Code | `claude-code/plugins/plugin-dev` | Breadth, pedagogy, per-component teaching skills, ❌/✅ tables, LLM reviewer agents |
| OpenAI Codex | `codex/codex-rs/skills/src/assets/samples` (`skill-creator`, `plugin-creator`) | Deterministic rigor, Python validators/scaffolders, numeric thresholds, forward-testing methodology |

The user's explicit standard: *"I expect top-shelf quality, completeness, and
thoroughness. The output must be robust and rigorous, just like the codex and claude code
versions. Use those two as your yardstick."* And: *"Prioritize quality over speed."*

## Workspace layout

`AGENTS.md`, the marketplace manifest, and the plugin all live in this repository:

```text
copilot-plugin-dev/            # this repository
├── AGENTS.md                  # this file
├── .github/
│   ├── plugin/marketplace.json
│   └── workflows/validate.yml
├── scripts/validate-all.sh
└── plugins/plugin-development/
    ├── plugin.json
    ├── agents/                # 3 × *.agent.md
    └── skills/                # 8 skills
```

The repository was developed inside a scratch workspace that also held three read-only
reference inputs. They are **not** part of this repository, and nothing here depends on them
at runtime — but if you are extending this plugin, they are worth cloning again:

```text
claude-code/        # yardstick: its plugins/plugin-dev is the quality bar
codex/              # yardstick: codex-rs/skills/src/assets/samples
copilot-docs-md/    # offline hard copy of the GitHub Copilot docs (539 .md, 6.8 MB)
```

Treat all three as inputs only; never modify them.

## The user's definition of "completeness" — read this carefully

This was clarified over several turns and is the single most important piece of guidance
in this document. An earlier interpretation was **wrong** and produced wasted effort.

### What it means

> *"if someone has this plugin creation plugin installed, the agent should never have to
> look something up in the copilot cli docs, so long as the requested plugin spec only
> references official features (e.g. a plugin that involves hooks). The guiding mentality
> should be 'anything and everything you'll ever need to make a copilot cli plugin'"*

Completeness is **informational self-sufficiency**. The test is:

> Could an agent with this plugin installed, and **no network access**, build any
> spec-conformant Copilot CLI plugin correctly?

### What it does NOT mean

It is **not** feature-surface coverage ("is there a skill for every component?"). That was
the original, incorrect reading. It produced a good 8-skill layout but the wrong audit
criteria — it asks "does a skill exist?" when it should ask "is the information complete?"

### The scope boundary: authoring, not consumption

The user rejected including end-user CLI commands, with this analogy:

> *"if we were writing a guide on how to develop windows programs in Rust, we would not be
> including information like 'To install programs developed with rust on windows, first
> download it via your web browser, then double click the icon...'"*

Apply this split:

| In scope — authoring surface | Out of scope — consumption |
| --- | --- |
| Anything written **into a file**: manifest fields, frontmatter, hook schemas, MCP/LSP config | `copilot plugin marketplace add/remove/update` |
| The local dev loop: `copilot plugin install ./path`, the reinstall-vs-`/skills reload` cache trap, `copilot plugins list --kind skill --json` to verify components loaded | `copilot plugin install name@marketplace` |
| Precedence and loading order (needed to debug why a component didn't load) | `copilot plugins enable/disable`, `copilot skill add` |
| `${PLUGIN_ROOT}`, `${COPILOT_PLUGIN_DATA}` | End-user config in `~/.copilot/config.json` |

The dev-loop commands are in scope for the same reason a Rust guide documents
`cargo build` and `cargo test` but not how a user double-clicks an installer.

User-level commands may appear **only** where the author is being taught how their users
will consume what they publish (i.e. in marketplace publishing guidance), never as
tutorial filler.

## Methodological warning: how NOT to audit coverage

A real mistake made in this project, recorded so it is not repeated.

Coverage was "audited" by counting how many **files** mentioned a term, treating a low
count as a gap. This produced three false gaps (`argument-hint`, `$schema`/Open Plugin
Spec, `extensions.exclusive`) — all three were already correctly and fully documented.

The metric is **inverted**. Good progressive disclosure means each concept has exactly
**one** authoritative home. A term appearing in two files is the signature of correct
organization, not thin coverage. File-mention counts measure cross-reference density,
nothing more.

**The correct method:** enumerate the feature surface from the authoritative docs, then
verify each item has an authoritative home containing complete field and behavior
documentation. Work from the spec inward, never from grep counts outward.

## Authoritative sources, in order of precedence

1. **The installed binary.** `copilot --help`, `copilot <cmd> --help`. Version-accurate.
   Currently **v1.0.78-2**. When the binary and the docs disagree, trust the binary and
   note the discrepancy.
2. **`copilot-docs-md/`** — the offline hard copy. **Audited and cleared.** Two independent
   audits found it faithful to the live docs, including reproducing an upstream truncation
   bug verbatim (the "Open Plugin Spec support" section promises a bullet list that is
   missing in both copies). Treat it as the working authoritative source; it is complete
   enough that this project no longer needs the network to spec against.
3. **Live docs.** Append `.md` to any docs.github.com URL for an LLM-friendly rendering.

### Live docs URL structure — it was reorganized

The old paths now 404. Correct forms:

```text
https://docs.github.com/llms.txt                                        # root index
https://docs.github.com/en/copilot/reference/copilot-cli-reference.md   # CLI ref index
https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference.md
https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference.md
https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference.md
https://docs.github.com/en/copilot/reference/hooks-reference.md
```

Dead: `.../reference/copilot-cli/cli-command-reference.md` and `.../reference/copilot-cli`.

Docs source repo: `https://github.com/github/docs`. Pages under `/content/` may be in an
odd state; a local build is the reliable route.

## Design decisions already made — do not silently reverse

| Decision | Rationale |
| --- | --- |
| **Ship no `hooks.json` in this plugin** | Plugin hooks execute in *every session* of *every installing user* — intrusive for dev tooling. Example hooks live in `hook-development/examples/` to be copied. The user explicitly endorsed this: *"It was a good decision to not include any hooks."* Presented in the skill as a deliberate best-practice signal. |
| **Scripts live inside each skill's own `scripts/`** | Skills bundle their own files and stay self-contained. |
| **Each script is standalone** | ~40-line frontmatter parser is duplicated rather than cross-imported, so any script can be copied out and still run. |
| **Skill frontmatter stays minimal** | `name`, `description`, `license` only. No `version` — not part of the Copilot spec. |
| **Heavy use of deterministic scripts** | User endorsement: *"having scripts to automatically do well-specified things like init'ing a plugin skeleton, validating a plugin, etc. This is a good strategy."* |
| **Blend both yardsticks** | Codex's deterministic validators + numeric thresholds + forward-testing, with Claude's teaching skills + anti-pattern tables + reviewer agents. |

## House style — enforced by validators and review

1. **Imperative voice.** "Run the validator", not "You should run the validator".
2. **Descriptions are third person with explicit triggers.** What it does, then
   `Use when ...` with 2–5 quoted user phrasings, then optionally what it does not cover.
3. **No "When to use" section in a body.** The body loads only *after* the skill triggers,
   so that content is inert where it sits and missing where it is needed.
4. **Numbered workflows** with a bolded lead verb per step.
5. **❌/✅ tables** for anti-patterns, with concrete text in every cell.
6. **Numeric thresholds, not adjectives.** "Under 500 lines", never "keep it short".
7. **Table of contents** on any reference file over 100 lines.
8. **Body budget:** `SKILL.md` under 500 lines and 5,000 words. Detail goes to `references/`.
9. **References one level deep.** `references/foo.md`, never `references/a/b.md`.
10. **Every linked bundled file must exist.** Validators fail on broken links.
11. **No `README.md`/`CHANGELOG.md`/`INSTALL.md` inside a skill directory.**
12. **State the reason for a non-obvious rule** in one clause.
13. **One canonical way** to do a thing. Do not offer three options where one works.
14. **Every workflow states what to do when a step fails.**

Description length: error under 40 chars, ideal 100–500, hard max 1024.

## Current state

### Built and passing

- `.github/plugin/marketplace.json`, `plugins/plugin-development/plugin.json`
- **8 skills**, all `PASS` under `validate_skill.py --recursive`:
  `plugin-development`, `skill-development`, `agent-development`, `hook-development`,
  `mcp-integration`, `lsp-integration`, `marketplace-development`, `plugin-testing`
- **3 agents**, all `PASS` under `validate_agent.py`:
  `plugin-validator`, `skill-reviewer`, `agent-architect`
- **15 validator/scaffolder scripts.** `validate_plugin.py` reports 0 errors.
- Repo README, LICENSE, CONTRIBUTING, `.gitignore`; plugin README and LICENSE
- `.github/workflows/validate.yml` (5 jobs) and `scripts/validate-all.sh` (11 checks)
- **Python quality gate green**: `ruff check`, `ruff format --check`, `ty check` all clean.
  Verified on Python 3.10 and 3.14, with and without PyYAML — the fallback frontmatter
  parser produces byte-identical output to PyYAML.
- **End-to-end install verified** against the real CLI, plus the empirical findings below.
- **Informational-completeness audit applied** — every gap and correctness defect from the
  audit has been fixed.
- **Published** at `Defiect/copilot-plugin-dev` (public). CI green on GitHub Actions.
- **Marketplace install verified end to end** from the published repo:
  `copilot plugin marketplace add Defiect/copilot-plugin-dev` then
  `copilot plugin install plugin-development@copilot-plugin-dev` → 8 skills.

### Not yet done

- **Trigger testing is incomplete.** Only `skill-development` has been verified to activate
  from natural phrasing. The remaining 7 skills, plus false-trigger probes, are unverified.
  Method: `copilot -p "<phrasing that never names the skill>"` and check that line 1 of the
  output reads `● skill(<expected>)`. If a skill fails to fire, rewrite its `description`,
  not its body.

## Validation commands

```bash
cd copilot-plugin-dev

# all skills
python3 plugins/plugin-development/skills/skill-development/scripts/validate_skill.py \
  --recursive plugins/plugin-development/skills

# whole plugin (manifest + agents + skills + hooks + MCP + LSP + hygiene)
python3 plugins/plugin-development/skills/plugin-development/scripts/validate_plugin.py \
  plugins/plugin-development

# agents
python3 plugins/plugin-development/skills/agent-development/scripts/validate_agent.py \
  --recursive plugins/plugin-development/agents
```

All validators support `--json`, `--quiet`, `--warnings-as-errors`, and exit `0` clean /
`1` errors / `2` bad invocation. Note that piping to `tail` masks the exit code.

## Traps discovered the hard way

1. **Fenced code blocks are not real links.** Both `validate_skill.py` and
   `validate_plugin.py` originally flagged illustrative paths inside ``` blocks as broken
   files. Fixed with `_strip_fenced_blocks()` in both. Any new link-checking logic must
   strip fences first.
2. **Quoted anti-patterns are not style violations.** A ❌ row quoting
   `"You should run..."` was counted as second-person prose. Fixed with `_narrative()`,
   which strips table rows and quoted strings before style heuristics run.
3. **`lspServers.fileExtensions` is an OBJECT**, mapping extension → language ID
   (`{".ts": "typescript"}`), **not** a list of strings. An earlier internal brief had this
   wrong; the implementation is correct. Verify against
   `cli-plugin-reference.md` before changing.
4. **Plugin components are cached at install time.** Editing source files does nothing to
   an installed plugin. Re-run `copilot plugin install ./path`; `/skills reload` is not
   enough.
5. **Background agents do not survive a session crash**, but their written files do. After
   an interruption, inventory the filesystem before assuming work was lost.
6. **Piping validator output to `tail` masks the exit code.** Use `PIPESTATUS` or check
   separately.
7. **`ruff format` will reflow long f-strings you just wrote.** Run `ruff format` before
   `ruff format --check` in any edit batch, or the gate fails on your own formatting.

## Spec quick reference

Fuller detail lives in the plugin's own reference files, which are the real deliverable.

- **Manifest discovery:** `.plugin/plugin.json` → `plugin.json` →
  `.github/plugin/plugin.json` → `.claude-plugin/plugin.json`
- **Marketplace discovery:** `marketplace.json` → `.plugin/` → `.github/plugin/` →
  `.claude-plugin/`
- **`plugin.json`:** only `name` required (kebab-case, ≤64; dots only in Open Plugin Spec
  mode via canonical `$schema` from agent-plugins.org)
- **Component defaults:** `agents/`, `skills/`, `hooks.json` or `hooks/hooks.json`,
  `.mcp.json` or `.github/mcp.json`, `lsp.json` or `.github/lsp.json`
- **SKILL.md:** exact filename, own directory; frontmatter `name`, `description`,
  `license`, `allowed-tools`
- **Agents:** `NAME.agent.md`; ID from filename; `description` required; body ≤30,000
  chars; tool aliases `execute/read/edit/search/agent/web/todo`; `infer` is **retired**
- **Hooks:** 14 camelCase events with PascalCase aliases; entry types `command`/`http`/
  `prompt` (`prompt` is `sessionStart`-only); matcher anchored `^(?:PATTERN)$`; default
  `timeoutSec` 30. **`preToolUse` fails CLOSED on error/exit-2, but timeouts always fail
  OPEN.**
- **MCP:** types `local`/`stdio`/`http`/`sse`. VS Code's top-level `servers` key is **not**
  read by Copilot CLI.
- **LSP:** `fileExtensions` required (object map); one of `command`/`bash`/`powershell`;
  `args` ignored for `bash`/`powershell`
- **Precedence:** agents and skills **first-found-wins** (plugins load LAST, so project and
  personal always shadow them); MCP servers **last-wins**; built-ins never overridable

## Working agreements

- **Autopilot is active.** Work autonomously to completion; do not stop to ask when the
  path is clear.
- **Verify, do not assume.** Every claim about the spec must trace to the binary or the
  docs. Several confident assertions in this project turned out to be wrong.
- **Delegate genuinely parallel work** to background subagents with complete context —
  they are stateless. Give them the spec brief path and a style exemplar to match.
- **Run the validators after every change.** They are fast and they encode the spec.
- **Report honestly.** When a previous conclusion was wrong, say so plainly and explain
  the flawed reasoning. The user values this over confident restatement.

## Empirical findings — proven by live experiment, several falsify the docs

All verified against **v1.0.78-2**. Where these disagree with the published docs, the
experiment wins and our content follows the experiment.

1. **Plugin agents are auto-namespaced `<plugin-name>:<agent-id>`, and cannot be shadowed
   or shadow anything.** `--agent plugin-validator` fails with *"No such agent"* (the error
   helpfully lists every qualified ID); `--agent plugin-development:plugin-validator`
   works. A personal `plugin-validator` and the plugin's coexist. This **falsifies**
   `cli-plugin-reference.md:314`, which says plugin agents are "silently ignored" on
   collision — true for skills, wrong for agents.

2. **Skills behave oppositely: they ARE shadowed.** Adding `~/.copilot/skills/plugin-testing/`
   dropped the plugin's skill count 8 → 7; removing it restored 8. Skills use bare names,
   first-found-wins.

3. **Two plugins sharing a skill name both survive, qualified with a COLON.** Verified via
   `copilot skill list --json`, which reported `plug-a:shared-probe` and
   `plug-b:shared-probe`. The docs write this as `/my-plugin/search` with a **slash** —
   that notation is **wrong**. Qualification happens only on collision; unique names stay
   bare.

4. **Command files DO support frontmatter and ARE loaded from a plugin's `commands/`.**
   A probe command with `description`, `argument-hint`, and `disable-model-invocation`
   installed cleanly and appeared in `copilot skill list --json` with `"source": "plugin"`
   and its authored description — confirming commands are skills in a simplified format.

5. **Personal agents outrank project agents.** Settled empirically both directions.

6. **`copilot plugins` (plural) is gated** — documented with `--kind/--scope/--json` but
   prints *"The plugins command is not available"* in this build. `copilot plugin list`
   (singular) and `copilot skill list --json` work.

7. **`--plugin-dir <dir>` is the superior dev loop.** Loads skills and agents directly from
   the working tree — no install, no cache staleness, not deprecated. Quirk:
   `copilot skill list` does **not** show `--plugin-dir` skills even though they load and
   work; `copilot plugin list` shows an "External Plugins (via --plugin-dir)" section, and
   `/skills list` inside the session shows them. Meanwhile
   `copilot plugin install ./path` now warns that *direct plugin installs are deprecated*.

8. **A `preToolUse` hook must NOT emit `{"permissionDecision":"allow"}` for safe input.**
   `allow` bypasses the user's permission prompt, so a denylist that "allows" everything it
   does not recognize silently auto-approves every shell call. Empty output falls through
   to default behavior — that is the correct guardrail shape. Our examples were fixed.

9. **There is no top-level `copilot marketplace` command.** It is
   `copilot plugin marketplace add|browse|list|remove|update`. Our READMEs shipped the wrong
   form initially; `copilot marketplace add X` errors with `Invalid command format`.

10. **`copilot plugin install <bare-name>` fails** with
    `Invalid plugin spec. Use: plugin-name@marketplace-name, owner/repo, or a URL`.
    The marketplace-qualified form is required: `plugin-development@copilot-plugin-dev`.
    `copilot plugin marketplace browse <name>` prints the exact install line to use.

11. **Direct installs are on the way out.** Installing from a repo, URL, or local path warns:
    *"Direct plugin installs (repos, URLs, local paths) are deprecated. Only
    plugin@marketplace installs will be supported in a future release."* Prefer `--plugin-dir`
    for development and `plugin@marketplace` for distribution.

12. **The same plugin installed from two sources coexists.** `copilot plugin list` showed both
    `plugin-development@copilot-plugin-dev` and `plugin-development`, but `skill list --json`
    still returned exactly 8 skills, unqualified — duplicates are silently deduplicated rather
    than colon-qualified. A bare `copilot plugin uninstall plugin-development` removed the
    **marketplace** copy first, leaving the direct install behind. Uninstall twice to clear.

### Upstream docs defects worth reporting

- `cli-plugin-reference.md:314` — conflates agent and skill collision behavior (finding 1).
- Plugin-qualified skill names documented as `/plugin/skill`; actual form is
  `plugin:skill` (finding 3).
- "Open Plugin Spec support" section is truncated in the published docs: it ends with
  "additively on top of standard plugin loading:" and the promised list is absent.
- `extensions` is documented as having "a different meaning" in Open Plugin Spec mode, but
  that meaning is never defined anywhere.

## Open questions

- The `extensions` field's Open Plugin Spec semantics remain unspecified upstream. Our
  reference tells authors not to combine `$schema` with `extensions` until it is defined.
