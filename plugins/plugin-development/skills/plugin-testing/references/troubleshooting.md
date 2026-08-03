# Plugin troubleshooting

## Contents

- [Plugin install fails](#plugin-install-fails)
- [Plugin installs but no skills](#plugin-installs-but-no-skills)
- [Skill listed but never triggers](#skill-listed-but-never-triggers)
- [Skill triggers but body seems ignored](#skill-triggers-but-body-seems-ignored)
- [Agent missing](#agent-missing)
- [Agent never delegated to](#agent-never-delegated-to)
- [Hook never fires](#hook-never-fires)
- [Hook blocks everything](#hook-blocks-everything)
- [MCP server absent](#mcp-server-absent)
- [MCP tools absent though server present](#mcp-tools-absent-though-server-present)
- [LSP not working](#lsp-not-working)
- [Changes not taking effect](#changes-not-taking-effect)
- [Name collision](#name-collision)
- [Broken bundled-file link](#broken-bundled-file-link)
- [Script not executable](#script-not-executable)
- [JSON parse failure](#json-parse-failure)

## Plugin install fails

**Symptom:** `copilot plugin install ./path` exits non-zero.

**Confirm:** Run the static smoke test and parse `plugin.json` with Python.

**Root cause:** The install spec is wrong, the manifest is invalid, or the plugin source is
not a directory containing a discoverable `plugin.json`.

**Fix:** Correct the source path, validate `plugin.json`, and reinstall.

**Prevent:** Add the smoke test to pre-release validation.

## Plugin installs but no skills

**Symptom:** `copilot plugin list` shows the plugin, but `/skills list` does not show its
skills.

**Confirm:** Check `plugin.json` `skills` paths and ensure every skill lives at
`skills/NAME/SKILL.md`.

**Root cause:** The skills directory is missing, misconfigured, or contains wrong file
names.

**Fix:** Move files to the configured skills path and reinstall.

**Prevent:** Keep the default `skills/` path unless there is a documented reason.

## Skill listed but never triggers

**Symptom:** `/skills list` shows the skill, but natural prompts do not load it.

**Confirm:** Invoke it explicitly with `/skill-name`; if that works, test a phrase quoted
in the description.

**Root cause:** The description does not match user phrasing.

**Fix:** Add 2-5 quoted realistic phrases and a clear `Use when` clause.

**Prevent:** Maintain a trigger evaluation set for every skill.

## Skill triggers but body seems ignored

**Symptom:** The wrong instructions run after a skill-like prompt.

**Confirm:** Run `/skills info NAME` and `scripts/check_precedence.py --plugin ./plugin`.

**Root cause:** A project or personal skill with the same frontmatter `name` shadows the
plugin skill.

**Fix:** Remove, rename, or disable the shadowing skill; then reinstall the plugin.

**Prevent:** Choose distinctive plugin skill names.

## Agent missing

**Symptom:** `/agent` does not list the plugin agent.

**Confirm:** Check that the file ends in `.agent.md` and lives in the configured `agents`
path.

**Root cause:** Wrong filename, wrong directory, or the plugin was not reinstalled.

**Fix:** Rename or move the file, then run `copilot plugin install ./path`.

**Prevent:** Run the smoke test before install.

## Agent never delegated to

**Symptom:** The agent appears, but Copilot handles matching tasks itself.

**Confirm:** Ask for a task using words from the agent description.

**Root cause:** The description says what the agent is, not when to delegate to it.

**Fix:** Rewrite the description with concrete task triggers and boundaries.

**Prevent:** Evaluate agents with realistic delegation prompts.

## Hook never fires

**Symptom:** Expected hook behavior never occurs.

**Confirm:** Run `/env` and inspect whether the hook source is loaded. Trigger a safe event
that should match the hook.

**Root cause:** Wrong event name, matcher mismatch, or hooks path not loaded.

**Fix:** Correct the event, matcher, or `plugin.json` `hooks` path.

**Prevent:** Test each hook with one known-matching event before release.

## Hook blocks everything

**Symptom:** Normal tool calls are denied or fail after installing the plugin.

**Confirm:** Disable the plugin and retry the same tool call.

**Root cause:** A `preToolUse` command hook exits non-zero or exit code 2 for too many
cases.

**Fix:** Narrow the matcher or make non-critical failures exit 0.

**Prevent:** Test allowed and blocked paths separately.

## MCP server absent

**Symptom:** `copilot mcp list` does not show the plugin server.

**Confirm:** Check `plugin.json` `mcpServers` and any referenced MCP config file.

**Root cause:** Wrong path, invalid JSON, or disabled server.

**Fix:** Correct the config and reinstall.

**Prevent:** Include MCP configs in static JSON parsing.

## MCP tools absent though server present

**Symptom:** The server appears, but expected tools are not available.

**Confirm:** Run `copilot mcp get SERVER --json`.

**Root cause:** Tool filter excludes them, discovery failed, or cached tool snapshots are
stale.

**Fix:** Adjust `tools`, fix server startup, or disable tool cache during debugging.

**Prevent:** Verify tools after every MCP config change.

## LSP not working

**Symptom:** `/lsp test SERVER` fails or language features do not appear.

**Confirm:** Run `/lsp show SERVER` and `/lsp logs SERVER`.

**Root cause:** Missing `fileExtensions`, invalid command, or paths that fail from the
installed plugin directory.

**Fix:** Add `fileExtensions`, use `${PLUGIN_ROOT}` for bundled launch scripts, and
reinstall.

**Prevent:** Test the server from a fresh session after install.

## Changes not taking effect

**Symptom:** Edited plugin files do not change runtime behavior.

**Confirm:** Compare source files with the installed plugin copy or reinstall and retest.

**Root cause:** Plugin components are copied at install time.

**Fix:** Run `copilot plugin install ./path` after every edit.

**Prevent:** Make reinstall step 2 in every edit-test loop.

## Name collision

**Symptom:** The wrong skill runs, or the plugin's skill does not appear at all.

**Confirm:** Run `scripts/check_precedence.py --plugin ./plugin`.

**Root cause:** Skills are keyed on the bare frontmatter `name`, first-found-wins, and
plugins load last. A project (`.github/skills/`) or personal (`~/.copilot/skills/`) skill
with the same `name` shadows the plugin's copy completely.

**Fix:** Rename the plugin's skill, or remove the higher-priority copy.

**Prevent:** Prefix generic skill names with a product or organization name.

**Not this:** A *missing plugin agent* is almost never a collision. Plugin agents are
namespaced as `<plugin-name>:<agent-id>` and cannot be shadowed — an agent that seems
missing was invoked by its bare ID. Run `copilot --agent bogus -p x` and read the error,
which lists every available qualified ID.

**Also not this:** Two plugins shipping the same skill `name` do not shadow each other.
Both remain reachable as `/plugin-a:name` and `/plugin-b:name`; only the bare `/name`
routes to the higher-priority plugin.

## Broken bundled-file link

**Symptom:** Skill validation fails on a missing `references/`, `examples/`, or `scripts/`
path.

**Confirm:** Run the skill validator and inspect the reported link.

**Root cause:** The file was moved, renamed, or referenced from inside the skill body with
a stale path.

**Fix:** Update the link or restore the file.

**Prevent:** Validate skills in CI.

## Script not executable

**Symptom:** A bundled script exists but cannot run.

**Confirm:** Check whether a shebang script has executable permission.

**Root cause:** Missing `chmod +x`.

**Fix:** Run `chmod +x path/to/script` and commit the mode change.

**Prevent:** Let the smoke test check shebang permissions.

## JSON parse failure

**Symptom:** JSON parsing fails during smoke testing or install.

**Confirm:** Run `python3 -m json.tool file.json`.

**Root cause:** JSON comments, trailing commas, or malformed strings.

**Fix:** Rewrite as strict JSON.

**Prevent:** Parse every JSON file in the smoke test.
