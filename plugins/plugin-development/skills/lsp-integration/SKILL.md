---
name: lsp-integration
description: Configure language servers for GitHub Copilot CLI plugins. Use when the user asks to "add a language server", mentions "lsp.json", says "go to definition isn't working", or wants to "bundle gopls". Covers configuring language servers shipped or referenced by a plugin, not writing a language server.
license: MIT
---

# LSP integration

Language Server Protocol integration gives Copilot code intelligence: definitions,
references, diagnostics, workspace symbols, and language-aware navigation. Prefer LSP
configuration when Copilot needs precise code structure instead of grep-based guessing.

## Core principles

**1. Configure servers that can actually start.** A plugin cannot assume `gopls`,
`pyright`, `rust-analyzer`, or any other language server exists on the user's machine.
Use a guarded wrapper when the binary might be missing.

**2. Claim only relevant extensions.** `fileExtensions` controls which files route to the
server. Broad mappings slow sessions and can send a file to the wrong language server.

**3. Keep launch forms simple.** Use one of `command`, `bash`, or `powershell` for each
server in this skill's configs. If a script needs arguments, put them in the script line
for `bash` or `powershell`; `args` is ignored for those entries.

## Integration workflow

1. **Confirm the binary.** Identify the language server executable and how users install
   it. If the plugin ships a wrapper, make the wrapper check `command -v` before running.
2. **Write the config.** Create an `lspServers` map in `lsp.json`, `.github/lsp.json`,
   `lsp-config/servers.json`, or an object referenced by `plugin.json` `lspServers`.
3. **Map extensions.** Set `fileExtensions` to a non-empty extension-to-language-ID map,
   for example `{".go": "go"}`. Avoid overlapping extensions unless the servers are
   intentionally mutually exclusive through plugin installation.
4. **Declare it.** Use the default file location or set `lspServers` in `plugin.json` to
   a path or inline object.
5. **Install the plugin.** Run `copilot plugin install ./path/to/plugin`. Reinstall after
   editing source files because installed plugin components are copied at install time.
6. **Verify the server.** Run `/lsp` to list configured servers, then `/lsp test NAME` to
   confirm startup. Fix the first startup error before testing code navigation.
7. **Handle missing binaries gracefully.** Print an actionable message to stderr and exit
   non-zero cleanly instead of crashing every session.

## Configuration reference

| Field | Required | Behavior |
| --- | --- | --- |
| `fileExtensions` | Yes | Map of file extensions to language IDs, for example `{".ts":"typescript"}`. |
| `command` | One launch form required | Executable to launch the server. Use `args` here when needed. |
| `bash` | One launch form required | Bash script line executed with `bash -c SCRIPT` on Linux/macOS. |
| `powershell` | One launch form required | PowerShell script line executed with `pwsh -c SCRIPT` on Windows. |
| `args` | No | Arguments passed only to `command`; ignored for `bash` and `powershell`. |
| `env` | No | Environment variables set when spawning the server. |
| `cwd` | No | Working directory, absolute or relative to the config file; supports `${PLUGIN_ROOT}`. |
| `rootUri` | No | Project root relative to the Git root; defaults to `.`. |
| `initializationOptions` | No | Options sent in the LSP `initialize` request. |
| `requestTimeoutMs` | No | Server request timeout in milliseconds; docs state the default is 90 seconds. |

Use [`references/configuration-reference.md`](references/configuration-reference.md) for
the full field reference, variable expansion notes, and launch-form details.

## `args` with scripts

| ❌ Silent mistake | ✅ Working config |
| --- | --- |
| `{"bash":"${PLUGIN_ROOT}/scripts/start-gopls.sh","args":["-rpc.trace"],"fileExtensions":{".go":"go"}}` | `{"bash":"${PLUGIN_ROOT}/scripts/start-gopls.sh -rpc.trace","fileExtensions":{".go":"go"}}` |

For `bash` and `powershell`, put flags in the script line or inside the wrapper. Reserve
`args` for `command` entries.

## File locations

| Location | Use |
| --- | --- |
| `lsp.json` | Default plugin LSP config. |
| `.github/lsp.json` | Shared repository-style config. |
| `lsp-config/servers.json` | Open Plugin Spec-compatible plugin config location. |
| `plugin.json` `lspServers` path | Point at a JSON file. |
| `plugin.json` `lspServers` object | Inline the server definitions. |

## The dependency problem

A plugin cannot assume a language server is installed globally. Use the guarded wrapper
pattern in [`examples/bundled-wrapper.sh`](examples/bundled-wrapper.sh): check the
binary, print the install hint, and `exec` only when the binary exists.

```json
{
  "lspServers": {
    "go": {
      "bash": "${PLUGIN_ROOT}/skills/lsp-integration/examples/bundled-wrapper.sh gopls",
      "fileExtensions": {".go": "go"}
    }
  }
}
```

If the binary is missing, the wrapper exits cleanly with an actionable message instead of
leaving Copilot with a confusing broken-pipe or spawn error.

## Anti-patterns

| ❌ Avoid | ✅ Prefer | Reason |
| --- | --- | --- |
| `"command": "/Users/alice/bin/gopls"` | `"bash": "${PLUGIN_ROOT}/scripts/start-gopls.sh"` | Hardcoded absolute paths fail on every other machine. |
| Assuming `pyright-langserver` is globally installed | A wrapper that checks `command -v pyright-langserver` | Missing binaries otherwise break every session that loads the plugin. |
| `"bash": "start.sh", "args": ["--stdio"]` | `"bash": "start.sh --stdio"` | `args` is ignored for `bash` and `powershell`. |
| Claiming `.ts` in two servers | One TypeScript server owns `.ts` | Overlaps make diagnostics and navigation unpredictable. |
| Enabling a heavyweight server for unused extensions | Claim only the plugin's supported extensions | Every claimed extension increases startup and analysis cost. |

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Server does not appear in `/lsp` | Config is not at a discovered location or `plugin.json` points to the wrong path | Move the file to a default location or fix `lspServers`, then reinstall the plugin. |
| `/lsp test NAME` cannot spawn the server | Binary is missing or path is hardcoded | Use a wrapper that checks `command -v` and prints the install command. |
| `args` appear ignored | The config uses `bash` or `powershell` | Move flags into the script string or wrapper. |
| Go to definition still falls back to search | The file extension is missing or claimed by another server | Fix `fileExtensions` and remove overlaps. |
| Diagnostics point at the wrong root | `rootUri` is wrong for a monorepo | Set `rootUri` to the project subdirectory relative to the Git root. |
| Works locally but not after plugin install | Source edits were not copied into the installed plugin | Reinstall the plugin after changing LSP files or scripts. |

## Bundled files

- [`references/configuration-reference.md`](references/configuration-reference.md) — all LSP config fields and launch-form behavior.
- [`references/server-catalogue.md`](references/server-catalogue.md) — common language servers, install commands, launch commands, and extensions.
- [`examples/lsp.json`](examples/lsp.json) — multi-language config example.
- [`examples/bundled-wrapper.sh`](examples/bundled-wrapper.sh) — guarded launch wrapper.
- [`scripts/validate_lsp.py`](scripts/validate_lsp.py) — stdlib-only LSP config validator.
