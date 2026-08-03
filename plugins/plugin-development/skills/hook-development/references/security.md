# Hook security

## Contents

- [Threat model](#threat-model)
- [Shell safety](#shell-safety)
- [Validate and allowlist](#validate-and-allowlist)
- [Timeouts are not a boundary](#timeouts-are-not-a-boundary)
- [Secrets](#secrets)
- [HTTP hooks](#http-hooks)
- [Third-party plugin hooks](#third-party-plugin-hooks)
- [Secure review checklist](#secure-review-checklist)

## Threat model

Hooks run with the user's full privileges in the same environment as Copilot CLI. A hook
can read the repository, access user files permitted by the operating system, use network
credentials in the environment, and mutate the working tree. Treat hook configuration and
handlers as executable code.

Plugin hooks have the largest blast radius because they run in every session for every
user who installs the plugin. Prefer project hooks for repository-specific policy.

## Shell safety

Never trust tool input as shell-safe. `toolArgs`, `tool_input`, prompts, file paths, and
notification messages are data from a model-mediated workflow and may contain shell
metacharacters, newlines, quotes, or command substitutions.

Use these rules in bash handlers:

| Risk | Safer pattern |
| --- | --- |
| `eval "$command"` | Do not execute model-provided commands. Inspect them as text. |
| `git -C $cwd status` | `git -C "$cwd" status` after confirming `cwd` is a directory. |
| Building a command string | Use arrays: `cmd=(git -C "$cwd" log --oneline -5)`. |
| Passing JSON through shell words | Use stdin or environment variables and parse with Python or `jq`. |

## Validate and allowlist

Prefer allowlists over denylists. A denylist can catch obvious dangerous commands, but it
misses equivalent spellings, aliases, shell functions, encoded payloads, and multi-step
chains. Use a denylist example only as defense in depth beside Copilot permissions,
repository review, and operating-system controls.

For permission hooks, make the default explicit:

| Goal | Default |
| --- | --- |
| Enforce a small safe command set | Deny unless the command matches an allowlist. |
| Audit without controlling execution | Allow or emit no decision, then log. |
| Add context after a result | Return `{}` when the payload is incomplete. |

## Timeouts are not a boundary

Timeouts fail open for every event, including `preToolUse` and policy hooks. A slow hook
is killed and processing continues through the normal permission flow. Therefore hooks are
defense in depth, not a standalone security boundary. A blocking hook must finish quickly
and return an explicit deny.

## Secrets

Keep secrets out of hook JSON. Read tokens from environment variables at runtime. For HTTP
hooks that need headers, use `allowedEnvVars` and an environment variable expansion in the
header value rather than embedding the literal token.

| ❌ Avoid | ✅ Prefer |
| --- | --- |
| `"Authorization": "Bearer ghp_..."` | `"Authorization": "Bearer ${HOOK_TOKEN}"` with `allowedEnvVars`. |
| `"password": "correct-horse..."` | Prompt-free secret storage outside the hook file. |
| Writing payloads with secrets to stdout | Redact and write only necessary audit fields. |

## HTTP hooks

HTTP hooks send the input payload as a JSON `POST`. Use HTTPS. The docs require HTTPS for
`preToolUse` and `permissionRequest` because responses can grant tool permissions; by
default, non-TLS HTTP is rejected except localhost cases controlled by
`COPILOT_HOOK_ALLOW_LOCALHOST=1`.

Network hooks fail open on errors, timeouts, non-2xx responses, and unreachable services.
Use them for telemetry or centrally reviewed advisory decisions unless the surrounding
permission policy already handles failure.

## Third-party plugin hooks

Review third-party plugin hooks before installation. Check `plugin.json` for a `hooks`
entry and inspect `hooks.json` or `hooks/hooks.json` in the plugin. Confirm every bundled
script path resolves inside the plugin, every network endpoint is expected, and no hook
silently mutates repositories.

## Secure review checklist

1. **Identify scope.** Confirm whether the hook is policy, user, project, settings, or
   plugin provided.
2. **Check event choice.** Use `preToolUse` only for decisions that must happen before
   execution.
3. **Inspect matchers.** Confirm anchored regex behavior does not broaden execution.
4. **Review parsing.** Verify invalid JSON and missing fields cannot crash audit hooks or
   accidentally allow guardrails that should deny.
5. **Review shell quoting.** Reject `eval`, unquoted variables, and model-provided command
   execution.
6. **Review outputs.** Confirm stdout is a single JSON object and stderr has no secrets.
7. **Review timeouts.** Keep timeouts small and never treat timeout as denial.
8. **Scan for secrets.** Reject literal tokens, passwords, access keys, and long encoded
   blobs in JSON or scripts.
