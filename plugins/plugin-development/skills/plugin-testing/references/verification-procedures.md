# Verification procedures

## Contents

- [Static validation](#static-validation)
- [Local install](#local-install)
- [Listing installed resources](#listing-installed-resources)
- [Skill verification](#skill-verification)
- [Agent verification](#agent-verification)
- [Hook verification](#hook-verification)
- [MCP verification](#mcp-verification)
- [LSP verification](#lsp-verification)
- [Cleanup](#cleanup)

## Static validation

Run the plugin smoke test from any directory:

```bash
/path/to/plugin/skills/plugin-testing/scripts/smoke_test_plugin.sh /path/to/plugin
```

Correct output ends with a PASS summary and exit code 0. A failure before install means
the package is malformed; fix static errors before runtime testing.

Validate skills individually when editing a single skill:

```bash
python3 /path/to/plugin/skills/skill-development/scripts/validate_skill.py /path/to/plugin/skills/SKILL-NAME
```

Correct output prints `PASS` or `PASS WITH NOTES` and exits 0.

## Loading the plugin under development

There are two ways to get a plugin in front of the CLI. Use the first for the edit-test
loop and the second only when you need to verify the real installed layout.

### `--plugin-dir` (preferred)

```bash
copilot --plugin-dir /path/to/plugin
```

This loads the plugin **directly from your working tree**. Nothing is copied, so there is
no stale-cache step and no reinstall after an edit — restart the session and the new files
are live. It is not deprecated, and it is the fastest loop by a wide margin.

Two things to know:

- `copilot plugin list` shows these under an **External Plugins (via --plugin-dir)**
  heading.
- `copilot skill list` does **not** list skills loaded this way, even though they load
  correctly and are usable in the session. Verify them from inside a session with
  `/skills list` rather than concluding they are missing.

### `copilot plugin install` (verification only)

```bash
copilot plugin install /path/to/plugin
```

Correct output indicates the plugin was installed. If the command fails, the install spec,
plugin manifest, or source path is wrong.

This path emits a deprecation warning:

```text
Warning: Direct plugin installs (repos, URLs, local paths) are deprecated.
Only plugin@marketplace installs will be supported in a future release.
```

Keep using it for the final pre-release check — it is the only way to exercise the real
installed layout, `${PLUGIN_ROOT}` resolution, and marketplace-equivalent packaging — but
do not build your edit loop on it. When you do install, **reinstall after every edit**: the
install step copies files, so a fresh session without reinstalling still sees the old copy.

The durable route is a local marketplace, which keeps working when direct installs are
removed:

```bash
copilot plugin marketplace add /absolute/path/to/repo
copilot plugin install PLUGIN@MARKETPLACE
```

## Listing installed resources

List installed plugins:

```bash
copilot plugin list
```

Correct output includes the plugin name from `plugin.json`. If it is absent, install did
not complete or a different Copilot home is active.

Inspect discoverable non-session resources:

```bash
copilot skill list --json
copilot plugins list --kind plugin --kind skill --kind mcp --kind lsp --json
```

`copilot skill list` covers skills and always works. `copilot plugins list` is the broader
cross-kind inspector, but it is gated in some builds and prints "The plugins command is not
available" when it is unavailable — fall back to `copilot skill list`, `copilot plugin
list`, and `copilot mcp list` in that case.

Correct JSON includes plugin, skill, MCP, and LSP entries that apply to the current
working directory. Custom agents and session-scoped hooks require a live session.

Plugin agents are namespaced as `<plugin-name>:<agent-id>`. Invoking one by its bare ID
fails with an error that lists every available qualified ID, which is the quickest way to
confirm the plugin's agents loaded:

```bash
copilot --agent no-such-agent -p "probe"
```

## Skill verification

In a live session, list skills:

```copilot
/skills list
```

Inspect one skill:

```copilot
/skills info SKILL-NAME
```

Correct output reports a location inside the installed plugin. If the path is under
`.github/skills` or `~/.copilot/skills`, a project or personal skill is shadowing the
plugin skill.

Test behavior explicitly first:

```copilot
Use the /SKILL-NAME skill to perform the smallest realistic task.
```

Then test natural triggering without naming the skill. If explicit invocation works but
natural triggering fails, rewrite the frontmatter `description`.

## Agent verification

In a live session, open the agent picker:

```copilot
/agent
```

Correct output lists the plugin agent under its qualified ID, `<plugin-name>:<agent-id>`.
If the agent is absent, check the file extension and the configured `agents` path.

From the terminal, invoke it non-interactively with the same qualified ID:

```bash
copilot --agent my-plugin:my-agent -p "a realistic task matching its description"
```

A bare ID will not resolve a plugin agent. `scripts/check_precedence.py --plugin
/path/to/plugin` prints the exact qualified ID for every agent the plugin ships.

Invoke the agent with a realistic task that matches its `description`. If the agent is
listed but never delegated to automatically, make the description more concrete.

## Hook verification

In a live session, inspect the loaded environment:

```copilot
/env
```

Correct output includes hook configuration sources when hooks are loaded. Trigger a safe
matching event and confirm the hook's observable behavior. For `preToolUse` hooks, verify
both allowed and blocked cases because command hook errors can block tool calls.

## MCP verification

List MCP servers non-interactively:

```bash
copilot mcp list
```

Inspect one server:

```bash
copilot mcp get SERVER --json
```

Correct output shows the server enabled, configured from the expected plugin, and exposing
the expected tools. If the server appears but tools are absent, check the `tools` filter,
server startup logs, and whether tool snapshot caching is stale.

## LSP verification

In a live session, inspect LSP configuration:

```copilot
/lsp show SERVER
/lsp test SERVER
/lsp logs SERVER
```

Correct output shows the server command and file extensions, a successful test, and no
startup errors. If it fails, check that `fileExtensions` is present and the command works
from the installed plugin path.

## Cleanup

Uninstall by plugin name, not by path:

```bash
copilot plugin uninstall PLUGIN-NAME
```

Correct output removes the installed plugin. If the plugin came from a marketplace, remove
the marketplace only after uninstalling plugins that depend on it:

```bash
copilot plugin marketplace remove MARKETPLACE-NAME
```
