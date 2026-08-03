# Hook configuration reference

Every field of the hook configuration file, plus the rules that decide which files load and
in what order. For what each event *does*, see
[events-reference.md](events-reference.md); for the stdin/stdout payloads, see
[io-contract.md](io-contract.md).

## File shape

```json
{
  "version": 1,
  "disableAllHooks": false,
  "hooks": {
    "preToolUse": [
      { "type": "command", "bash": "…", "powershell": "…" }
    ]
  }
}
```

| Top-level field | Type | Required | Description |
| --- | --- | --- | --- |
| `version` | number | Yes | Must be `1`. A missing or wrong version rejects the whole file. |
| `hooks` | object | Yes | Maps event names to arrays of hook entries. |
| `disableAllHooks` | boolean | No | `true` skips every hook in this file without deleting it. Does **not** affect policy hooks. |

`disableAllHooks` is the supported way to pause hooks temporarily: while debugging whether a
hook is the cause of a problem, during a sensitive task, or as an opt-out switch for
contributors who set it in their own `settings.json`.

### Error tolerance differs by source

This distinction matters when you decide where to ship a hook.

- **Files loaded from a directory** (`.github/hooks/*.json`, `~/.copilot/hooks/*.json`, a
  plugin's `hooks.json`): a malformed *item* is dropped and logged, and valid sibling hooks
  in the same file still load. Structural errors — invalid JSON, a bad `version`, or an
  event whose value is not an array — still reject the entire file.
- **Inline `hooks` blocks in `settings.json`**: strict. Any item-level validation error
  rejects the whole `hooks` field.

Other configuration files always load independently of each other, so one bad file never
takes down the rest.

## Load order

Copilot CLI loads hooks from six sources and **combines** them. When the same event appears
in more than one source, every entry from every source runs — later sources do not override
earlier ones.

1. **Policy-level hook files** — machine-wide, loaded first, in alphabetical order.
   `/etc/github-copilot/policy.d/*.json` on Linux and macOS,
   `C:\ProgramData\GitHub\Copilot\policy.d\*.json` on Windows, plus values under
   `HKLM\Software\Policies\GitHub\Copilot` on Windows. Policy hooks **cannot** be disabled
   by `disableAllHooks` and load regardless of folder trust state. On POSIX systems the
   files must be owned by root and must not be group- or world-writable. Policy hooks are
   CLI-only.
2. **Repository-level hook files** — `.github/hooks/*.json` in the repository root.
3. **User-level hook files** — `*.json` in `~/.copilot/hooks/`
   (`%USERPROFILE%\.copilot\hooks\` on Windows, or `$COPILOT_HOME/hooks/` when
   `COPILOT_HOME` is set).
4. **Inline `hooks` block in repository settings** — the top-level `hooks` field of
   `.github/copilot/settings.json` or `.github/copilot/settings.local.json`. The
   cross-tool `.claude/settings.json` and `.claude/settings.local.json` files in the
   repository are read too.
5. **Inline `hooks` block in user settings** — the top-level `hooks` field of
   `~/.copilot/settings.json`.
6. **Plugin hooks** — each installed plugin's own `hooks.json`, or `hooks/hooks.json`,
   inside its installation directory.

As a plugin author you own source 6 only. Assume other hooks are already registered on the
same events, and never write a hook that only behaves correctly when it runs alone.

## Command entries

```json
{
  "type": "command",
  "bash": "\"${PLUGIN_ROOT}/hooks/check.sh\"",
  "powershell": "& \"${PLUGIN_ROOT}/hooks/check.ps1\"",
  "cwd": "optional/working/dir",
  "env": { "LOG_LEVEL": "debug" },
  "timeoutSec": 30
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | `"command"` | No | Defaults to `"command"` when omitted. Write it explicitly. |
| `bash` | string | One of the three | Shell command used on Linux and macOS. |
| `powershell` | string | One of the three | Shell command used on Windows. |
| `command` | string | One of the three | Cross-platform fallback. Copied into both `bash` and `powershell` **when those fields are absent**; an explicit `bash` or `powershell` wins on its own platform. |
| `cwd` | string | No | Working directory, absolute or relative to the repository root. |
| `env` | object | No | Environment variables to set. Supports variable expansion. |
| `timeoutSec` | number | No | Timeout in seconds. Default `30`. |
| `timeout` | number | No | Alias for `timeoutSec`. Used only when `timeoutSec` is absent; `timeoutSec` wins when both appear. |

**Ship both `bash` and `powershell`.** A hook with only `bash` silently does nothing on
Windows, which is worse than failing loudly. Use `command` alone only when one literal
command string is genuinely correct on every platform.

Under the Copilot cloud agent only `bash` is honored; `powershell` entries are ignored and
`command` is honored as the fallback.

### Progress messages

A command hook can write status lines to the CLI timeline while it runs. Emit a single-line
JSON object with `"type": "progress"` on stdout before the final decision object:

```bash
echo '{"type": "progress", "message": "Checking policy..."}'
# ... perform work ...
echo '{"permissionDecision": "allow"}'
```

Add `"temporary": true` to emit a transient line that replaces the previous transient line
and is cleared when the assistant responds, instead of accumulating in the timeline.

Progress messages are display-only and never affect decision logic. The parsing rules are
exact and easy to get wrong:

- The CLI scans stdout line by line. A line that, after trimming, is one complete JSON
  object with `"type": "progress"` is consumed as a progress event and **removed from the
  output stream**. Every other line — blank lines, plain text, non-progress JSON — is
  preserved verbatim.
- Each progress message must sit on its own line and be valid JSON on that single line.
  A pretty-printed, multi-line progress object is **not** recognized, stays in the output
  stream, and will usually break the final parse.
- When the hook exits, the preserved lines are concatenated, trimmed, and parsed with a
  single `JSON.parse`. The final decision object may therefore span multiple lines.
- If the leftover output is empty or fails to parse, the hook is treated as having produced
  no output and default behavior applies. Two non-progress JSON objects concatenate into
  invalid JSON, so **emit exactly one final decision object**.

## HTTP entries

```json
{
  "type": "http",
  "url": "https://hooks.example.com/copilot",
  "headers": { "X-Source": "copilot-cli" },
  "allowedEnvVars": ["GITHUB_TOKEN"],
  "timeoutSec": 30
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | `"http"` | Yes | Must be `"http"`. |
| `url` | string | Yes | Target URL. `preToolUse` and `permissionRequest` **must** use `https://`, because the response can grant tool permissions. |
| `headers` | object | No | Request headers to include. |
| `allowedEnvVars` | string[] | No | Environment variable names that may be expanded inside `headers` values. When set, `url` must use `https://`. |
| `timeoutSec` | number | No | Timeout in seconds. Default `30`. |
| `timeout` | number | No | Alias for `timeoutSec`, same precedence rule as command entries. |

The payload is sent as a JSON `POST`. Only `https://` URLs are allowed by default; plain
`http://` is rejected except for `http://localhost`, `http://127.*`, and `http://[::1]`
when `COPILOT_HOOK_ALLOW_LOCALHOST=1` is set.

**Plugins should avoid HTTP hooks.** They send session data to a third party and add network
latency to every event. If you ship one, make it opt-in and document exactly what leaves the
machine. See [security.md](security.md).

## Prompt entries

```json
{
  "type": "prompt",
  "prompt": "/my-plugin/session-brief"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | `"prompt"` | Yes | Must be `"prompt"`. |
| `prompt` | string | Yes | Text auto-submitted as if the user typed it. May be a natural language prompt or a slash command. |

Prompt entries are valid on **`sessionStart` only**, and they fire only for **new
interactive sessions**. They do not fire on resume and do not fire in non-interactive prompt
mode (`-p`). Cloud agent jobs run non-interactively, so prompt entries may not fire there
either.

Because a prompt entry consumes the user's first turn, a plugin should ship one only when
that is unmistakably the point of the plugin.

## Validate before you ship

```bash
python3 skills/hook-development/scripts/validate_hooks.py hooks.json
```

The validator checks the version, event names and matcher syntax, entry shapes, timeout
bounds, and the HTTPS requirement on `preToolUse` and `permissionRequest`.
