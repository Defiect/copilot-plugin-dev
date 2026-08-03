---
name: hook-development
description: Build, review, and test Copilot CLI hooks and hooks.json files. Use when the user asks to "add a hook", "run a command before every tool call", "block dangerous commands", or mentions "hooks.json". Does not cover cloud-agent setup.
license: MIT
---

# Hook development

Hooks are deterministic code that runs on Copilot lifecycle events. The one thing that
matters most: plugin hooks run in **every session** for **every user** who installs the
plugin, so keep them fast, quiet, and safe.

Use this skill to design hook configurations, write handlers, validate `hooks.json`, and
locally exercise hook scripts before installing them.

## Core principles

**1. Treat hooks as product code.** Hooks run outside the model with the user's operating
system privileges. Validate input, quote every shell value, prefer allowlists, and keep
secrets out of JSON configuration.

**2. Keep stdout machine-readable.** Command hook stdout is parsed as a single JSON
object after progress lines are stripped. Send diagnostics to stderr, and print nothing
on the successful no-op path unless the event expects output.

**3. Design for plugin blast radius.** A plugin hook affects every repository and every
session for each installer. Prefer examples users copy into project hooks unless the
behavior is safe as a universal default.

## Creating a hook: the 9-step workflow

1. **Choose the event.** Pick the earliest event that has the data and control needed;
   use the decision table below before opening the full reference.
2. **Choose the entry type.** Use `command` for local policy, `http` for a reviewed
   service endpoint, and `prompt` only for `sessionStart` startup text.
3. **Write the handler.** Read JSON from stdin, handle empty or invalid input, finish in
   under the configured timeout, and emit at most one final JSON object on stdout.
4. **Decide the failure posture.** Use command hooks for `preToolUse` guardrails that
   must fail closed on crashes. Do not rely on slowness, because timeouts fail open.
5. **Set the matcher.** Add the narrowest supported `matcher`; omit it only when every
   invocation of that event must run the hook.
6. **Set the timeout.** Start with `timeoutSec: 5` for local command hooks and raise it
   only when a measured handler needs more time.
7. **Test locally.** Run [scripts/test_hook.py](scripts/test_hook.py) with a built-in or
   custom payload until stdout, stderr, exit code, and decision interpretation are right.
8. **Validate configuration.** Run [scripts/validate_hooks.py](scripts/validate_hooks.py)
   on the hook file and fix every `ERROR`; review every `WARN` before installing.
9. **Install and verify.** Place the JSON in the intended hook location, restart Copilot
   CLI so configuration reloads, trigger the event once, and inspect logs if the hook does
   not fire.

## Event decision table

| Intent | Use this event | Entry type |
| --- | --- | --- |
| Block a dangerous command | `preToolUse` | `command` |
| Approve or deny permission prompts programmatically | `permissionRequest` | `command` or `http` |
| Format files after edits | `postToolUse` | `command` |
| Add recovery guidance after a failed tool | `postToolUseFailure` | `command` |
| Inject context at startup | `sessionStart` | `command` or `prompt` |
| Audit every prompt | `userPromptSubmitted` | `command` |
| Rewrite model-facing prompt content | `userPromptTransformed` | `command` |
| Preserve compaction guidance | `preCompact` | `command` |
| Notify another system when the agent stops | `agentStop` | `command` or `http` |
| Add context before a subagent runs | `subagentStart` | `command` |
| Redact or force continuation after a subagent | `subagentStop` | `command` |
| Log runtime errors | `errorOccurred` | `command` or `http` |
| React to CLI notifications | `notification` | `command` or `http` |
| Clean up at session end | `sessionEnd` | `command` |

## Complete event list

| Event | Fires when | `matcher` | Can block | Compatibility alias |
| --- | --- | --- | --- | --- |
| `sessionStart` | A new or resumed session begins | No | No | `SessionStart` |
| `sessionEnd` | The session terminates | No | No | `SessionEnd` |
| `userPromptSubmitted` | The user submits a prompt | No | No | `UserPromptSubmit` |
| `userPromptTransformed` | The runtime prepares model-facing prompt content | No | No | None documented |
| `preToolUse` | Before each tool executes | Yes, on `toolName` | Yes | `PreToolUse` |
| `postToolUse` | After a tool completes successfully | Yes, on `toolName` | No | `PostToolUse` |
| `postToolUseFailure` | After a tool completes with a failure | No | No | `PostToolUseFailure` |
| `agentStop` | The main agent finishes a turn | No | Yes, forces another turn | `Stop` |
| `subagentStart` | A subagent is spawned before it runs | Yes, on `agentName` | No | None documented |
| `subagentStop` | A subagent completes normally | No | Yes, forces continuation | `SubagentStop` |
| `errorOccurred` | An error occurs during execution | No | No | `ErrorOccurred` |
| `preCompact` | Context compaction is about to begin | Yes, on `trigger` | No | `PreCompact` |
| `notification` | The CLI emits a system notification | Yes, on `notification_type` | No | `Notification` |
| `permissionRequest` | Before the permission service runs | Yes, on `toolName` | Yes | `PermissionRequest` |

For full schemas and output contracts, open
[references/events-reference.md](references/events-reference.md) and
[references/io-contract.md](references/io-contract.md).

## Entry types

| Type | Required fields | Use for | Notes |
| --- | --- | --- | --- |
| `command` | At least one of `bash`, `powershell`, or `command` | Local scripts and fast policy checks | Ship **both** `bash` and `powershell` to cover Linux, macOS, and Windows. `type` defaults to `command`, but write it explicitly. |
| `http` | `type: "http"`, `url` | Reviewed webhook services | `https://` is mandatory for `preToolUse` and `permissionRequest`. |
| `prompt` | `type: "prompt"`, `prompt` | Startup text or slash commands | New interactive `sessionStart` only — not on resume, not under `-p`. |

`command` is a cross-platform fallback: its value is copied to both shells, and an explicit
`bash` or `powershell` in the same entry takes precedence. The cloud agent honors only
`bash`. See [references/configuration-reference.md](references/configuration-reference.md)
for the full field tables.

Use `${PLUGIN_ROOT}` when a hook references bundled scripts, for example
`${PLUGIN_ROOT}/skills/hook-development/examples/block-dangerous-commands.py`. Use
`${COPILOT_PLUGIN_DATA}` for writable plugin state such as audit logs; never write state
inside the installed plugin directory.

## Failure semantics that matter

`preToolUse` command hooks are fail-**closed** on non-timeout errors. Exit code `2`, a
crash, or any other non-zero exit denies the tool call even when stdout says
`permissionDecision: "allow"`.

**Timeouts are always fail-open.** A timed-out hook is killed, a warning is surfaced, and
processing continues as if the hook had not run. Security consequence: a hook intended to
block something must not rely on being slow, and must not be the only control. Keep
blocking hooks fast, explicit, and backed by normal Copilot permission policy or review.

HTTP `preToolUse` hooks fail open on network errors, timeouts, and non-2xx responses. Use
[references/security.md](references/security.md) before shipping any hook that enforces a
security policy.

## Matcher semantics

Native matchers are regexes compiled as `^(?:PATTERN)$`, so the whole value must match.
`Bash` does not match `Bash(git)`, and a pattern that looks unanchored is still anchored.

| ❌ Matcher | Why it fails | ✅ Matcher |
| --- | --- | --- |
| `Bash` for `Bash(git)` | The implicit anchors require the entire string | `Bash(?:\(.*\))?` |
| `git` for `Bash(git status)` | It is not a substring search | `.*git.*` |
| `edit|create` for `str_replace_editor` | Alternation lists only two exact names | `edit|create|str_replace_editor` |
| `manual|auto ` | The trailing space becomes part of the regex | `manual|auto` |

PascalCase `PreToolUse` and `PermissionRequest` use Claude-format matcher compatibility;
read [references/events-reference.md](references/events-reference.md) before mixing native
and compatibility event names.

## Hook anti-patterns

| ❌ Anti-pattern | ✅ Prefer |
| --- | --- |
| Write to stdout noisily on every event | Print one final JSON object only when needed; send diagnostics to stderr. |
| Block on network calls in `preToolUse` | Use a local command guardrail or accept fail-open HTTP behavior. |
| Set an unbounded or very large `timeoutSec` | Start at 5 seconds and justify anything above 60 seconds. |
| Mutate the repository without telling the user | Return `additionalContext` or document the automation in the hook config. |
| Ship a plugin hook when a project-level hook would do | Put repository-specific policy in `.github/hooks/*.json`. |
| Hardcode absolute paths | Reference bundled files with `${PLUGIN_ROOT}`. |
| Put secrets in hook JSON | Read tokens from environment variables and use `allowedEnvVars` for HTTP headers. |

## Should this hook ship in a plugin at all?

This plugin deliberately ships **no** `hooks.json`. Hook examples live in
[examples/hooks.json](examples/hooks.json) for users to copy because plugin hooks execute
in every session of every installing user. That is an intrusive default for a
development-tooling plugin. Treat this as a design signal: ship reusable hook knowledge,
validators, and examples in plugins; ship active hooks only when always-on behavior is the
product.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Hook not firing | File is not loaded, event name is wrong, or matcher misses | Validate with [scripts/validate_hooks.py](scripts/validate_hooks.py), restart Copilot CLI, and test without the matcher. |
| Hook fires but output is ignored | stdout is empty, invalid JSON, or contains two final JSON objects | Run [scripts/test_hook.py](scripts/test_hook.py) and emit exactly one final JSON object. |
| Hook blocks everything | `preToolUse` command exits non-zero or returns `permissionDecision: "deny"` too broadly | Make the handler exit `0` for allow paths and narrow the matcher. |
| Hook slows down every tool call | Event is too broad or timeout is too high | Add a matcher and move network work out of the hot path. |
| PascalCase/camelCase payload key mismatch | Handler reads `toolName` but compatibility payload sends `tool_name` | Support both keys or use one event-name style per file. |

## Bundled files

- [references/events-reference.md](references/events-reference.md) — complete event,
  payload, matcher, alias, output, and blocking reference.
- [references/io-contract.md](references/io-contract.md) — stdin, stdout, stderr, exit
  code, decision, and fail-open/fail-closed contracts.
- [references/security.md](references/security.md) — threat model and secure handler
  practices.
- [references/patterns.md](references/patterns.md) — proven hook patterns and trade-offs.
- [references/configuration-reference.md](references/configuration-reference.md) — every
  hook config field, load order, and error-tolerance rules.
- [examples/hooks.json](examples/hooks.json) — complete multi-event example config.
- [examples/block-dangerous-commands.py](examples/block-dangerous-commands.py) —
  `preToolUse` command guardrail.
- [examples/format-on-edit.py](examples/format-on-edit.py) — `postToolUse` formatter.
- [examples/session-context.py](examples/session-context.py) — `sessionStart` context
  injector.
- [examples/audit-log.py](examples/audit-log.py) — `userPromptSubmitted` JSONL audit log.
- [scripts/validate_hooks.py](scripts/validate_hooks.py) — standalone hook config
  validator.
- [scripts/test_hook.py](scripts/test_hook.py) — local hook execution harness.
