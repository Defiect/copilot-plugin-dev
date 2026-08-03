---
name: plugin-testing
description: Verify and debug GitHub Copilot CLI plugins end to end. Use when the user asks to "test my plugin", "my skill isn't loading", "the agent doesn't appear", "why isn't my plugin working", or "validate my plugin".
license: MIT
---

# Plugin testing

A plugin is not done when the files exist. It is done when a real Copilot CLI session
loads it and each component actually triggers. Static validation and runtime verification
are different tests, and both are required before release.

## Two tiers of testing

| Tier | What it proves | Examples |
| --- | --- | --- |
| Static | Files are parseable, schemas are valid, links resolve, and scripts compile | JSON parses, `plugin.json` fields are valid, `SKILL.md` links exist, Python compiles, shell scripts pass `bash -n` |
| Runtime | Copilot copied, loaded, listed, and invoked the installed components | Plugin installs, skills appear, a skill triggers on a realistic prompt, an agent is delegated to, hooks fire, MCP tools appear |

Static tests prevent broken packages. Runtime tests prove the user experience works.

## Testing workflow

1. **Run validators.** Validate the plugin manifest and every skill. Fix errors before
   runtime testing.
2. **Run the smoke test.** Run `scripts/smoke_test_plugin.sh /path/to/plugin`. If it
   fails, fix the reported static issue and rerun it.
3. **Load the plugin.** Start the CLI with `copilot --plugin-dir /path/to/plugin`, which
   loads the plugin straight from your working tree with no copy and no stale cache. Use
   `copilot plugin install /path/to/plugin` only for the final pre-release check; it copies
   files into Copilot's installed-plugin cache and is deprecated for local paths.
4. **List components.** Run `copilot plugin list` and `copilot skill list`. Confirm each
   expected non-session component appears. Use a live session for agents and hooks.
5. **Trigger-test every skill.** Use the methodology below with realistic user phrasing.
   If a skill does not trigger, fix the `description` first.
6. **Invoke every agent.** In a live session, open `/agent`, or invoke it explicitly with
   `--agent <plugin-name>:<agent-id>`. Plugin agents only resolve under that qualified ID.
7. **Verify hooks, MCP, and LSP.** Use `/env`, `/mcp list`, `copilot mcp list`, and
   `/lsp show` as appropriate. Confirm hook behavior with a safe event.
8. **Uninstall and clean up.** Run `copilot plugin uninstall NAME` after testing. Remove
   local marketplace registrations only after uninstalling dependent plugins.

## Install-time caching gotcha

Installed plugin components are copied at install time. Editing the source directory does
nothing to an already installed plugin. Reinstall the plugin after every edit; `/skills
reload` is not enough for plugin-provided skills.

Use this edit loop:

```bash
# 1. Edit files in the plugin source directory.
# 2. Start a fresh session pointed at that directory. No install, no cache.
copilot --plugin-dir ./path/to/plugin

# 3. Inside the session, confirm what loaded.
#    /skills list   -- shows --plugin-dir skills; `copilot skill list` does not
#    /agent         -- shows agents as <plugin-name>:<agent-id>

# 4. Re-run the exact failing trigger or component test.
```

Before a release, repeat the run once through a real install to exercise the installed
layout and `${PLUGIN_ROOT}` resolution.

## Trigger testing methodology

1. **Write prompts first.** Before testing, list 3-5 realistic user phrasings per skill.
   Do not mention the skill name in the trigger prompts.
2. **Use a fresh session.** Start a new session for each phrasing so a previous success or
   failure does not contaminate the context.
3. **Paste the phrasing verbatim.** Do not explain that this is a test, and do not include
   the expected answer.
4. **Record the result.** Mark whether the skill triggered, whether it chose the right
   instructions, and the first point it went wrong.
5. **Fix the description first.** If the body works when invoked as `/skill-name` but the
   natural prompt does not trigger it, the fix is almost always the `description`, not the
   body.

Use this table:

| Skill | Prompt | Expected behavior | Triggered? | Notes |
| --- | --- | --- | --- | --- |
| `plugin-testing` | `why isn't my plugin working` | Loads plugin-testing and runs static then runtime checks | Yes/No |  |
| `plugin-testing` | `the agent doesn't appear after install` | Loads plugin-testing and checks precedence plus install cache | Yes/No |  |

For scoring and false-trigger tests, read
[references/evaluation.md](references/evaluation.md).

## Precedence debugging

Skills are first-found-wins, and plugins load last. A stale `.github/skills/foo/` or
`~/.copilot/skills/foo/` with the same `name` silently shadows the plugin version. Agents
are not affected: plugin agents are namespaced as `<plugin-name>:<agent-id>`.

1. **Inspect collisions.** Run
   `scripts/check_precedence.py --plugin /path/to/plugin` from any directory.
2. **Check the live session.** In Copilot, run `/skills info NAME` for skills and `/agent`
   for agents. Confirm the reported location is inside the installed plugin.
3. **Remove or rename stale copies.** Delete, rename, or disable the project or personal
   component that wins precedence.
4. **Reload and retest.** Start a fresh session with `copilot --plugin-dir /path/to/plugin`,
   or reinstall if you are testing the installed layout.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Plugin install fails | Invalid `plugin.json`, bad source, or unsupported install spec | Validate the plugin, then retry; prefer `copilot --plugin-dir ./path` while iterating |
| Plugin installs but no skills | Missing `skills/NAME/SKILL.md` or wrong `skills` path in `plugin.json` | Fix the path and reinstall |
| Skill listed but never triggers | Description lacks realistic trigger phrasing | Add quoted phrases to `description` and retest in a fresh session |
| Skill triggers but body seems ignored | Another skill with the same `name` wins precedence | Run `scripts/check_precedence.py --plugin ./plugin` and remove the shadowing copy |
| Agent missing | File does not end in `.agent.md` or lives outside the configured agents path | Rename or move the file, then reinstall |
| Agent never delegated to | Agent description does not state when to delegate | Rewrite the agent `description` with concrete task triggers |
| Hook never fires | Wrong event name, matcher mismatch, or hooks path not loaded | Validate hooks and confirm `/env` shows the hook source |
| Hook blocks everything | `preToolUse` command hook exits non-zero or exit code 2 | Make the hook fail-open unless blocking is intentional |
| MCP server absent | `mcpServers` path is wrong or the server is disabled | Check `copilot mcp list` and `/mcp list` |
| MCP tools absent though server present | Tool filter excludes them or discovery failed | Check `copilot mcp get SERVER --json` and server stderr logs |
| LSP not working | Missing `fileExtensions` or launch command fails | Check `/lsp show SERVER` and `/lsp logs SERVER` |
| Changes not taking effect | Installed plugin cache still contains old files | Re-run `copilot plugin install ./path`; `/skills reload` is not enough. `--plugin-dir` avoids this entirely |
| Name collision | Project or personal component shadows plugin component | Run `scripts/check_precedence.py --plugin ./plugin` |
| Broken bundled-file link | `SKILL.md` references a missing `references/`, `examples/`, or `scripts/` path | Run the skill validator and fix links |
| Script not executable | Script has a shebang but lacks executable permission | Run `chmod +x path/to/script` |
| JSON parse failure | Comments, trailing commas, or malformed JSON | Parse with Python or `jq` and fix the exact line |

For long-form diagnosis, read [references/troubleshooting.md](references/troubleshooting.md).
For exact verification commands, read
[references/verification-procedures.md](references/verification-procedures.md).

## Pre-release checklist

- [ ] Plugin manifest parses and validates.
- [ ] Every `SKILL.md` validates and links only to bundled files that exist.
- [ ] `scripts/smoke_test_plugin.sh /path/to/plugin` exits 0 or only fails on known
      incomplete sibling work outside this release.
- [ ] `copilot --plugin-dir /path/to/plugin` loads every expected component.
- [ ] `copilot plugin install /path/to/plugin` succeeds (final pre-release check).
- [ ] `copilot plugin list` shows the installed plugin.
- [ ] `copilot skill list` shows every plugin skill under "Plugin skills".
- [ ] Every custom agent resolves as `--agent <plugin-name>:<agent-id>`.
- [ ] Every skill passes 3-5 realistic trigger prompts and at least one false-trigger
      prompt.
- [ ] Every custom agent appears and delegates on a realistic prompt.
- [ ] Hooks, MCP servers, and LSP servers are verified when present.
- [ ] The edit → reinstall → verify loop has been tested after the last file change.
- [ ] The plugin is uninstalled and reinstalled from the release source.

## Bundled files

- [references/verification-procedures.md](references/verification-procedures.md) — exact
  commands, expected output, and failure meaning for each verification step.
- [references/troubleshooting.md](references/troubleshooting.md) — symptom-by-symptom
  debugging procedures.
- [references/evaluation.md](references/evaluation.md) — quality scoring, trigger
  reliability, context cost, and false-trigger testing.
- [scripts/smoke_test_plugin.sh](scripts/smoke_test_plugin.sh) — static smoke test for a
  plugin directory.
- [scripts/check_precedence.py](scripts/check_precedence.py) — detects project and
  personal skills that shadow plugin skills, and lists qualified plugin agent IDs.
