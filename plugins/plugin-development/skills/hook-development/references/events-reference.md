# Hook events reference

## Contents

- [Payload format families](#payload-format-families)
- [Event matrix](#event-matrix)
- [sessionStart / SessionStart](#sessionstart--sessionstart)
- [sessionEnd / SessionEnd](#sessionend--sessionend)
- [userPromptSubmitted / UserPromptSubmit](#userpromptsubmitted--userpromptsubmit)
- [userPromptTransformed](#userprompttransformed)
- [preToolUse / PreToolUse](#pretooluse--pretooluse)
- [postToolUse / PostToolUse](#posttooluse--posttooluse)
- [postToolUseFailure / PostToolUseFailure](#posttoolusefailure--posttoolusefailure)
- [agentStop / Stop](#agentstop--stop)
- [subagentStart](#subagentstart)
- [subagentStop / SubagentStop](#subagentstop--subagentstop)
- [errorOccurred / ErrorOccurred](#erroroccurred--erroroccurred)
- [preCompact / PreCompact](#precompact--precompact)
- [notification / Notification](#notification--notification)
- [permissionRequest / PermissionRequest](#permissionrequest--permissionrequest)
- [Matcher reference](#matcher-reference)
- [Tool names](#tool-names)

## Payload format families

Copilot selects the payload shape from the event name in the hook configuration.

| Config event style | Field style | Example |
| --- | --- | --- |
| camelCase, Copilot native | camelCase keys | `preToolUse` receives `toolName` and `toolArgs`. |
| PascalCase, compatibility | snake_case keys | `PreToolUse` receives `tool_name` and `tool_input`. |

PascalCase aliases exist only where documented below. Do not invent a compatibility event
name for `userPromptTransformed` or `subagentStart`; the current reference documents only
native payloads for those events.

## Event matrix

| Event | Trigger | Output fields | Matcher | Blocking behavior | Alias |
| --- | --- | --- | --- | --- | --- |
| `sessionStart` | A new or resumed session begins | `additionalContext` | No | Cannot block | `SessionStart` |
| `sessionEnd` | The session terminates | None processed | No | Cannot block | `SessionEnd` |
| `userPromptSubmitted` | The user submits a prompt | None processed | No | Cannot block | `UserPromptSubmit` |
| `userPromptTransformed` | The model-facing prompt is prepared | `modifiedTransformedPrompt` | No | Cannot block | None documented |
| `preToolUse` | Before each tool executes | `permissionDecision`, `permissionDecisionReason`, `modifiedArgs` | Yes, on `toolName` | Can allow, deny, ask, or modify args | `PreToolUse` |
| `postToolUse` | After a tool succeeds | `modifiedResult`, `additionalContext` | Yes, on `toolName` | Cannot block | `PostToolUse` |
| `postToolUseFailure` | After a tool fails | Exit code `2` stdout becomes recovery context | No | Cannot block | `PostToolUseFailure` |
| `agentStop` | The main agent finishes a turn | `decision`, `reason` | No | `decision: "block"` forces another turn | `Stop` |
| `subagentStart` | A subagent is spawned before it runs | `additionalContext` | Yes, on `agentName` | Cannot block creation | None documented |
| `subagentStop` | A subagent completes normally | `decision`, `reason`, `modifiedResponse` | No | `decision: "block"` forces continuation | `SubagentStop` |
| `errorOccurred` | An error occurs during execution | None processed | No | Cannot block | `ErrorOccurred` |
| `preCompact` | Context compaction is about to begin | None processed | Yes, on `trigger` | Cannot block | `PreCompact` |
| `notification` | The CLI emits a system notification | `additionalContext` | Yes, on `notification_type` | Never blocks; fire-and-forget | `Notification` |
| `permissionRequest` | Before the permission service runs | `behavior`, `message`, `interrupt` | Yes, on `toolName` | Can allow or deny | `PermissionRequest` |

## `sessionStart` / `SessionStart`

Fires when a new or resumed session begins. Prompt hook entries are allowed only on this
event.

**Native input:**

| Field | Type | Notes |
| --- | --- | --- |
| `sessionId` | string | Session identifier. |
| `timestamp` | number | Unix timestamp in milliseconds. |
| `cwd` | string | Current working directory. |
| `source` | `"startup" \| "resume" \| "new"` | Session source. |
| `initialPrompt` | string, optional | Initial prompt when present. |

**Compatibility input:**

| Field | Type | Notes |
| --- | --- | --- |
| `hook_event_name` | `"SessionStart"` | Compatibility event name. |
| `session_id` | string | Session identifier. |
| `timestamp` | string | ISO 8601 timestamp. |
| `cwd` | string | Current working directory. |
| `source` | `"startup" \| "resume" \| "new"` | Session source. |
| `initial_prompt` | string, optional | Initial prompt when present. |

**Output:** return `additionalContext` to inject context into the session. Return `{}` or
empty output for no action. **Matcher:** not supported. **Blocking:** cannot block.

## `sessionEnd` / `SessionEnd`

Fires when the session terminates.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`, `reason:
"complete" | "error" | "abort" | "timeout" | "user_exit"`.

**Compatibility input:** `hook_event_name: "SessionEnd"`, `session_id: string`,
`timestamp: string` ISO 8601, `cwd: string`, and the same `reason` values.

**Output:** none processed. **Matcher:** not supported. **Blocking:** cannot block.

## `userPromptSubmitted` / `UserPromptSubmit`

Fires when the user submits a prompt.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`, `prompt:
string`.

**Compatibility input:** `hook_event_name: "UserPromptSubmit"`, `session_id: string`,
`timestamp: string` ISO 8601, `cwd: string`, `prompt: string`.

**Output:** none processed. **Matcher:** not supported. **Blocking:** cannot block.

## `userPromptTransformed`

Fires after the runtime transforms a submitted prompt into model-facing content, just
before that content is emitted and persisted to session history. It runs for the primary
message and for every preceding message in a batched submission. System notifications do
not trigger it.

**Input:**

| Field | Type | Notes |
| --- | --- | --- |
| `sessionId` | string | Session identifier. |
| `timestamp` | number | Epoch milliseconds. |
| `cwd` | string | Current working directory. |
| `prompt` | string | User prompt after `userPromptSubmitted` hooks have run. |
| `transformedPrompt` | string | Runtime-transformed content sent to the model. |

**Output:** `modifiedTransformedPrompt?: string`. The replacement changes only the
content sent to the model and stored in history; it does not change the prompt displayed
in the timeline. Return `{}` or empty output to leave content unchanged. **Matcher:** not
supported. **Blocking:** mutation-only, cannot block.

## `preToolUse` / `PreToolUse`

Fires before each tool executes.

**Native input:**

| Field | Type | Notes |
| --- | --- | --- |
| `sessionId` | string | Session identifier. |
| `timestamp` | number | Unix timestamp in milliseconds. |
| `cwd` | string | Current working directory. |
| `toolName` | string | Runtime tool name. |
| `toolArgs` | unknown | Tool arguments. |

**Compatibility input:**

| Field | Type | Notes |
| --- | --- | --- |
| `hook_event_name` | `"PreToolUse"` | Compatibility event name. |
| `session_id` | string | Session identifier. |
| `timestamp` | string | ISO 8601 timestamp. |
| `cwd` | string | Current working directory. |
| `tool_name` | string | Claude tool name where a mapping exists. |
| `tool_input` | unknown | Tool arguments, parsed from a JSON string when possible. |

**Output:**

| Field | Values or type | Notes |
| --- | --- | --- |
| `permissionDecision` | `"allow"`, `"deny"`, `"ask"` | Empty output uses default behavior. Cloud agent treats `ask` as `deny`. |
| `permissionDecisionReason` | string | Required when the decision is `deny`. |
| `modifiedArgs` | object | Substitute tool arguments. |

**Matcher:** supported on `toolName` in native config. PascalCase `PreToolUse` uses
Claude-format matcher compatibility. **Blocking:** can deny. Command hook crashes and
non-zero exits fail closed, but timeouts fail open.

## `postToolUse` / `PostToolUse`

Fires after each tool completes successfully.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`, `toolName:
string`, `toolArgs: unknown`, and `toolResult: { resultType: "success";
textResultForLlm: string }`.

**Compatibility input:** `hook_event_name: "PostToolUse"`, `session_id: string`,
`timestamp: string`, `cwd: string`, `tool_name: string`, `tool_input: unknown`, and
`tool_result: { result_type: "success"; text_result_for_llm: string }`.

**Output:**

| Field | Type | Notes |
| --- | --- | --- |
| `modifiedResult` | object | Replacement result. Must have `resultType: "success"`; `resultType: "failure"` routes downstream and triggers `postToolUseFailure`. |
| `additionalContext` | string | Appended for the model after tool output; multiple hook values join with double newline and are capped at 10 KB. |

**Matcher:** supported on `toolName`. **Blocking:** cannot block.

## `postToolUseFailure` / `PostToolUseFailure`

Fires after a tool completes with a failure.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`, `toolName:
string`, `toolArgs: unknown`, `error: string`.

**Compatibility input:** `hook_event_name: "PostToolUseFailure"`, `session_id: string`,
`timestamp: string`, `cwd: string`, `tool_name: string`, `tool_input: unknown`, `error:
string`.

**Output:** exit code `2` is treated as `additionalContext`; stdout is appended to the
failure shown to the agent. **Matcher:** not documented. **Blocking:** cannot block.

## `agentStop` / `Stop`

Fires when the main agent finishes a turn.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`,
`transcriptPath: string`, `stopReason: "end_turn"`, `stop_hook_active: boolean`.

**Compatibility input:** `hook_event_name: "Stop"`, `session_id: string`, `timestamp:
string`, `cwd: string`, `transcript_path: string`, `stop_reason: "end_turn"`,
`stop_hook_active: boolean`.

**Output:** `decision?: "block" | "allow"`, `reason?: string`. A valid block decision
forces another agent turn using `reason` as the prompt. After 8 consecutive block
continuations, the CLI overrides the hook and ends the turn. **Matcher:** not supported.
**Blocking:** can force continuation.

## `subagentStart`

Fires when a subagent is spawned before it runs. The built-in `general-purpose` agent does
not emit `subagentStart` or `subagentStop`; other built-in YAML-based agents and custom
agents emit these events.

**Input:** `sessionId: string`, `timestamp: number`, `cwd: string`, `transcriptPath:
string`, `agentName: string`, `agentDisplayName?: string`, `agentDescription?: string`.

**Output:** `additionalContext?: string`, prepended to the subagent prompt. **Matcher:**
supported on `agentName`. **Blocking:** cannot block creation.

## `subagentStop` / `SubagentStop`

Fires when a subagent completes normally, before returning results to the parent. The
`response` field carries the full final subagent response before large-response spill
handling.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`,
`transcriptPath: string`, `agentId: string`, `agentType: string`, `agentName: string`,
`agentDisplayName?: string`, `response: string`, `stopReason: "end_turn"`.

**Compatibility input:** `hook_event_name: "SubagentStop"`, `session_id: string`,
`timestamp: string`, `cwd: string`, `transcript_path: string`, `agent_id: string`,
`agent_type: string`, `agent_name: string`, `agent_display_name?: string`,
`last_assistant_message: string`, `stop_reason: "end_turn"`.

**Output:** `decision?: "block" | "allow"`, `reason?: string`, and
`modifiedResponse?: string`. A valid block decision wins over `modifiedResponse`; if more
than one hook returns `modifiedResponse`, the last one wins. **Matcher:** not supported.
**Blocking:** can force continuation.

## `errorOccurred` / `ErrorOccurred`

Fires when an error occurs during execution.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`, `error:
{ message: string; name: string; stack?: string }`, `errorContext: "model_call" |
"tool_execution" | "system" | "user_input"`, `recoverable: boolean`.

**Compatibility input:** `hook_event_name: "ErrorOccurred"`, `session_id: string`,
`timestamp: string`, `cwd: string`, the same `error` object, `error_context:
"model_call" | "tool_execution" | "system" | "user_input"`, `recoverable: boolean`.

**Output:** none processed. **Matcher:** not supported. **Blocking:** cannot block.

## `preCompact` / `PreCompact`

Fires when context compaction is about to begin, manually or automatically.

**Native input:** `sessionId: string`, `timestamp: number`, `cwd: string`,
`transcriptPath: string`, `trigger: "manual" | "auto"`, `customInstructions: string`.

**Compatibility input:** `hook_event_name: "PreCompact"`, `session_id: string`,
`timestamp: string`, `cwd: string`, `transcript_path: string`, `trigger: "manual" |
"auto"`, `custom_instructions: string`.

**Output:** none processed. **Matcher:** supported on `trigger`. **Blocking:** cannot
block.

## `notification` / `Notification`

Fires asynchronously when the CLI emits a system notification. It is fire-and-forget and
never blocks the session.

**Input:**

| Field | Type | Notes |
| --- | --- | --- |
| `sessionId` | string | Session identifier. |
| `timestamp` | number | Unix timestamp in milliseconds. |
| `cwd` | string | Current working directory. |
| `hook_event_name` | `"Notification"` | Included in the documented payload. |
| `message` | string | Human-readable notification text. |
| `title` | string, optional | Short title such as `Permission needed` or `Shell completed`. |
| `notification_type` | string | One of the notification types below. |

**Notification types:** `shell_completed`, `shell_detached_completed`,
`agent_completed`, `agent_idle`, `permission_prompt`, `elicitation_dialog`.

**Output:** `additionalContext?: string`, injected into the session as a prepended user
message. This can trigger further processing if the session is idle. Return `{}` or empty
output for no action. **Matcher:** supported on `notification_type`. **Blocking:** never
blocks.

## `permissionRequest` / `PermissionRequest`

Fires before the permission service runs: before rule checks, session approvals,
auto-allow or auto-deny, and user prompting. It does not apply under cloud agent; use
`preToolUse` there.

The current reference documents decision fields and matcher semantics for this event, but
does not publish a separate input payload schema. Write handlers defensively and support
the same tool fields used by `preToolUse` (`toolName` / `tool_name` and tool arguments)
without claiming undocumented fields are guaranteed.

**Output:**

| Field | Values or type | Notes |
| --- | --- | --- |
| `behavior` | `"allow"`, `"deny"` | Approves or denies the tool call. |
| `message` | string | Reason fed back to the LLM when denying. |
| `interrupt` | boolean | With `deny`, stops the agent entirely when `true`. |

Return empty output or `{}` to fall through to normal permission handling. For command
hooks, exit code `2` is treated as deny; stdout JSON is merged with
`{"behavior":"deny"}` and stderr is ignored. **Matcher:** supported on `toolName`;
PascalCase `PermissionRequest` uses Claude-format matcher compatibility. **Blocking:**
can allow or deny.

## Matcher reference

Native matchers are regexes compiled as `^(?:PATTERN)$`. Invalid regexes cause the hook
entry to be skipped. Omit `matcher` to receive all invocations of a supported event.

| Event | Matched value |
| --- | --- |
| `notification` | `notification_type` |
| `permissionRequest` | `toolName` |
| `postToolUse` | `toolName` |
| `preCompact` | `trigger` (`manual` or `auto`) |
| `preToolUse` | `toolName` |
| `subagentStart` | `agentName` |

PascalCase `PreToolUse` and `PermissionRequest` use Claude-format semantics: `*`, `**`,
or an empty matcher fires for every tool; a literal name or `|`-separated alternation
fires when any token equals the runtime tool name or Claude tool name; other values are
case-sensitive regexes anchored as `^(?:PATTERN)$` against the Claude tool name or runtime
name.

## Tool names

| Runtime tool | Description |
| --- | --- |
| `ask_user` | Ask the user a clarifying question; not useful under cloud agent because there is no user. |
| `bash` | Execute Unix shell commands. |
| `create` | Create files. |
| `edit` | Modify file contents. |
| `glob` | Find files by pattern. |
| `grep` | Search file contents. |
| `powershell` | Execute Windows PowerShell commands; absent under cloud agent. |
| `task` | Run subagent tasks. |
| `view` | Read file contents. |
| `web_fetch` | Fetch web pages. |

Claude compatibility maps `bash` and `powershell` to `Bash`, `view` to `Read`, `create`
to `Write`, `edit`, `str_replace_editor`, and `apply_patch` to `Edit`, `grep` and `rg` to
`Grep`, `glob` to `Glob`, `web_fetch` to `WebFetch`, `web_search` to `WebSearch`,
`ask_user` to `AskUserQuestion`, `update_todo` to `TodoWrite`, and `task` to `Agent`;
the literal `Task` is also accepted. Tools without a Claude equivalent keep their runtime
names.
