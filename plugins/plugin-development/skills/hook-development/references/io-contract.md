# Hook I/O contract

## Contents

- [Input on stdin](#input-on-stdin)
- [Stdout output JSON](#stdout-output-json)
- [Progress messages](#progress-messages)
- [Stderr](#stderr)
- [Decision-control fields](#decision-control-fields)
- [Exit codes](#exit-codes)
- [Fail-open and fail-closed matrix](#fail-open-and-fail-closed-matrix)
- [Handler checklist](#handler-checklist)

## Input on stdin

Every command hook receives one JSON payload on stdin. The payload shape depends on the
event name style in the hook configuration:

| Event name style | Payload keys |
| --- | --- |
| camelCase native, such as `preToolUse` | camelCase keys such as `sessionId`, `toolName`, `toolArgs`. |
| PascalCase compatibility, such as `PreToolUse` | snake_case keys such as `session_id`, `tool_name`, `tool_input`. |

Read all of stdin once. Handle an empty string, invalid JSON, and missing keys without a
crash. For a guardrail, return an explicit deny when the payload cannot be inspected.
For an audit or notification hook, log the parse error and exit `0`.

## Stdout output JSON

Command hook stdout is parsed as hook output JSON when present. Emit at most one final
JSON object. Empty output or invalid JSON is treated as no output and falls through to the
event's default behavior.

Good final output:

```json
{"permissionDecision":"deny","permissionDecisionReason":"blocked by policy"}
```

Bad final output:

```text
checking policy...
{"permissionDecision":"allow"}
{"additionalContext":"extra"}
```

Two non-progress JSON objects concatenate into invalid JSON and are ignored.

## Progress messages

Command hooks may write progress status lines to stdout while they run. A progress line
must be one complete JSON object on one line with `"type": "progress"`:

```json
{"type":"progress","message":"Checking policy...","temporary":true}
```

The CLI strips progress objects before parsing final output. Pretty-printed progress
objects are not recognized and can break final JSON parsing.

## Stderr

Use stderr for diagnostics. It is surfaced or logged according to the event and exit code,
but it is not parsed as decision JSON. Keep stderr quiet on the success path because hooks
may run on every tool call.

## Decision-control fields

| Event | Field | Values | Effect |
| --- | --- | --- | --- |
| `preToolUse` | `permissionDecision` | `allow`, `deny`, `ask` | Controls whether the tool executes; cloud agent treats `ask` as `deny`. |
| `preToolUse` | `permissionDecisionReason` | string | Required when denying; shown to the agent. |
| `preToolUse` | `modifiedArgs` | object | Replaces tool arguments. |
| `permissionRequest` | `behavior` | `allow`, `deny` | Short-circuits normal permission handling. |
| `permissionRequest` | `message` | string | Reason fed back to the LLM when denying. |
| `permissionRequest` | `interrupt` | boolean | Stops the agent when combined with `deny`. |
| `agentStop` | `decision` | `block`, `allow` | `block` forces another main-agent turn. |
| `agentStop` | `reason` | string | Prompt for the forced turn. |
| `subagentStop` | `decision` | `block`, `allow` | `block` forces subagent continuation. |
| `subagentStop` | `reason` | string | Prompt for the forced continuation. |
| `subagentStop` | `modifiedResponse` | string | Replaces the response returned to the parent when not blocked. |
| `postToolUse` | `modifiedResult` | object | Replaces a successful tool result. |
| `postToolUse` | `additionalContext` | string | Appends context after the successful tool result. |
| `sessionStart` | `additionalContext` | string | Injects context into the session. |
| `subagentStart` | `additionalContext` | string | Prepends context to the subagent prompt. |
| `notification` | `additionalContext` | string | Injects a prepended user message into the session. |
| `userPromptTransformed` | `modifiedTransformedPrompt` | string | Replaces model-facing prompt content. |

## Exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | Success. stdout is parsed as hook output JSON if present. |
| `2` | Warning by default. For `permissionRequest` and `preToolUse`, treated as deny; stdout JSON is merged with the deny decision. For `postToolUseFailure`, stdout becomes recovery context shown to the agent. |
| Other non-zero | Logged as hook failure and execution continues, except `preToolUse` command hooks fail closed and deny the tool call. |
| Timeout | The hook is killed after `timeoutSec`; execution continues. Timeouts fail open for every event, including `preToolUse` and policy hooks. |

## Fail-open and fail-closed matrix

| Event / entry | Handler exits `0` | Handler exits `2` | Handler exits other non-zero | Handler times out |
| --- | --- | --- | --- | --- |
| `preToolUse` command | Honor stdout decision | Deny | Deny | Fail open to normal permission flow |
| `preToolUse` HTTP | Honor valid response | Not applicable | Fail open on network, timeout, non-2xx, or invalid response | Fail open |
| `permissionRequest` command | Honor stdout behavior | Deny | Logged and skipped | Fail open |
| `permissionRequest` HTTP | Honor valid response | Not applicable | Fail open | Fail open |
| `agentStop` / `subagentStop` command | Honor valid decision | Warning behavior unless valid output applies | Logged and skipped | Fail open |
| `postToolUseFailure` command | Success path | stdout appended as recovery context | Logged and skipped | Fail open |
| All other command hooks | Honor supported output fields | Warning by default | Logged and skipped | Fail open |

A hook that must stop a dangerous action must return an explicit denial quickly. Slowness
never blocks a tool call.

## Handler checklist

1. **Parse defensively.** Treat stdin as untrusted JSON and support both native and
   compatibility keys when reasonable.
2. **Filter early.** Exit `0` immediately when the event or tool does not matter.
3. **Emit one object.** Write one compact final JSON object to stdout only when needed.
4. **Keep diagnostics off stdout.** Use stderr, and only when something is actionable.
5. **Bound runtime.** Make the configured timeout a safety net, not normal control flow.
