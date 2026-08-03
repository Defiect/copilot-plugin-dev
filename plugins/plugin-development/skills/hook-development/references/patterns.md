# Hook patterns

## Contents

- [Command guardrail](#command-guardrail)
- [Auto-formatter](#auto-formatter)
- [Session context injection](#session-context-injection)
- [Audit log](#audit-log)
- [Notification bridge](#notification-bridge)
- [Test on stop](#test-on-stop)
- [Compaction summary preservation](#compaction-summary-preservation)

## Command guardrail

| Item | Guidance |
| --- | --- |
| Event | `preToolUse` |
| Matcher | `bash|powershell` or a compatibility matcher such as `Bash` when using `PreToolUse`. |
| Handler sketch | Parse `toolArgs.command` or `tool_input.command`, deny destructive commands with `permissionDecision: "deny"` and a reason, and print **nothing** otherwise. |
| Trade-off | Fast local checks fail closed on crashes, but timeouts fail open and denylists are bypassable. |

Never print `{"permissionDecision": "allow"}` for the commands your denylist did not match.
`allow` bypasses the user's permission prompt, so a guardrail that allows everything it
does not recognize silently auto-approves every shell call. Empty output falls through to
the normal permission flow, which is what you want.

Use [examples/block-dangerous-commands.py](../examples/block-dangerous-commands.py) as a
copyable starting point.

## Auto-formatter

| Item | Guidance |
| --- | --- |
| Event | `postToolUse` |
| Matcher | `edit|create|apply_patch|str_replace_editor` |
| Handler sketch | Extract likely changed file paths from tool arguments, run installed formatters for known extensions, print nothing on success, and never exit non-zero. |
| Trade-off | Improves consistency, but silent mutation can surprise users; document it clearly in the hook config. |

Use [examples/format-on-edit.py](../examples/format-on-edit.py) for a conservative local
formatter that only runs tools already installed on the machine.

## Session context injection

| Item | Guidance |
| --- | --- |
| Event | `sessionStart` |
| Matcher | None |
| Handler sketch | Read `cwd`, collect cheap repository facts such as branch and recent commits, return `additionalContext`. |
| Trade-off | Helpful context loads early, but every session pays the token cost. Keep it short. |

Use [examples/session-context.py](../examples/session-context.py) as a minimal context
injector.

## Audit log

| Item | Guidance |
| --- | --- |
| Event | `userPromptSubmitted` |
| Matcher | None |
| Handler sketch | Append one JSONL record to `${COPILOT_PLUGIN_DATA}` with timestamp, session ID, cwd, and prompt length or prompt text according to policy. |
| Trade-off | Useful for debugging and compliance, but prompts may contain sensitive data. Redact or hash when needed. |

Use [examples/audit-log.py](../examples/audit-log.py) for a non-blocking JSONL writer.

## Notification bridge

| Item | Guidance |
| --- | --- |
| Event | `notification` |
| Matcher | `agent_completed|permission_prompt` or a single notification type. |
| Handler sketch | Send a compact payload to an HTTPS endpoint or local notifier and ignore failures. |
| Trade-off | Notifications are asynchronous and cannot block. Network calls can still consume local resources. |

## Test on stop

| Item | Guidance |
| --- | --- |
| Event | `agentStop` |
| Matcher | None |
| Handler sketch | Detect whether this turn already came from a stop hook, run the smallest relevant test, and return `decision: "block"` with `reason` only when the agent must fix a failure. |
| Trade-off | Can improve quality, but repeated block decisions can loop. The CLI caps consecutive block continuations at 8. |

## Compaction summary preservation

| Item | Guidance |
| --- | --- |
| Event | `preCompact` |
| Matcher | `auto` or `manual|auto` |
| Handler sketch | Copy durable facts from the transcript or current state into a separate log, or emit progress diagnostics. |
| Trade-off | `preCompact` is notification-only; it cannot block compaction or rewrite the summary. Keep file writes fast. |
