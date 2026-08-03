# System prompt design for custom agents

## Contents

- [The standard skeleton](#the-standard-skeleton)
- [Persona and scope](#persona-and-scope)
- [Core Responsibilities](#core-responsibilities)
- [Process with failure branches](#process-with-failure-branches)
- [Quality Standards](#quality-standards)
- [Output Format templates](#output-format-templates)
- [Bound the scope](#bound-the-scope)
- [Failure and incomplete work](#failure-and-incomplete-work)
- [Length budgeting](#length-budgeting)
- [Prompt review checklist](#prompt-review-checklist)

## The standard skeleton

Use the same structure for most agents. Consistency makes agents easier to review and
makes failures easier to debug.

```markdown
You are an expert [role] specializing in [domain].

## Core Responsibilities

1. [Outcome the agent must produce]
2. [Second outcome]
3. [Boundary or safety responsibility]

## Process

1. **Gather context.** [What to read or search first.]
2. **Analyze.** [What criteria to apply.]
3. **Handle failures.** If [condition], [stop/report/fallback].
4. **Verify.** [How to check the result.]
5. **Report.** Use the output format exactly.

## Quality Standards

- [Testable assertion]
- [Testable assertion]

## Output Format

[Literal template]
```

Why each section exists:

| Section | Reason |
| --- | --- |
| Persona | Sets the role and expertise before the task begins. |
| Core Responsibilities | Defines success as outcomes, not subject areas. |
| Process | Converts intent into ordered behavior and prevents wandering. |
| Quality Standards | Gives the caller a way to judge whether work is acceptable. |
| Output Format | Makes the subagent's result usable by the main agent. |

## Persona and scope

Start with one sentence. Avoid biographies and motivational language.

| ❌ Avoid | ✅ Prefer |
| --- | --- |
| `You are helpful and smart.` | `You are a read-only code reviewer specializing in correctness bugs in recent changes.` |
| `You know everything about testing.` | `You are a test-runner agent that executes existing test commands and reports failures without editing files.` |

Add a scope sentence when the agent is easy to overuse:

```markdown
Review only the files or diff supplied by the caller. Do not expand into a whole-repository audit unless the caller explicitly requests that scope.
```

## Core Responsibilities

Write numbered outcomes, not topics.

| ❌ Topic list | ✅ Outcome list |
| --- | --- |
| `1. Security` | `1. Identify exploitable security defects with a concrete file:line location.` |
| `2. Tests` | `2. Run the smallest existing test command that covers the changed behavior.` |
| `3. Documentation` | `3. Produce a concise report that the caller can paste into a pull request.` |

A good responsibility contains a verb, an object, and a success condition.

## Process with failure branches

A process is an ordered list. Include the branch that applies when a step fails, because
subagents otherwise keep exploring after the useful path is closed.

```markdown
## Process

1. **Identify scope.** Read the delegated task and list the files, directories, or diff
   ranges it names. If no scope is clear, inspect `git diff --stat` once; if that is also
   empty, report that there is no review target and stop.
2. **Gather evidence.** Read only the scoped files and directly related definitions.
3. **Check rules.** Apply the Quality Standards in order. Do not report style-only issues.
4. **Verify findings.** Re-read each reported line and confirm the issue is still present.
5. **Report.** Use the Output Format exactly. If there are no findings, say what was
   checked and write `No reportable findings.`
```

Failure branches to encode explicitly:

| Failure | Instruction to include |
| --- | --- |
| Missing target | Report the missing input and stop. |
| Tool unavailable | State the blocked step and continue only if a read-only fallback exists. |
| Command fails | Include command, exit code, and relevant output; do not invent a pass. |
| Scope too large | Sample or prioritize by documented criteria, then disclose the limit. |
| Conflicting instructions | Follow the narrower task-specific instruction and report the conflict. |

## Quality Standards

Quality standards must be testable assertions. Avoid values that cannot be checked.

| ❌ Vague | ✅ Testable |
| --- | --- |
| `Be thorough.` | `Read every file named by the caller before reporting.` |
| `Give useful feedback.` | `Every finding includes impact, evidence, and a concrete next action.` |
| `Run tests when needed.` | `Run exactly one targeted existing test command when the agent has `execute`.` |
| `Keep it short.` | `Keep the final report under 300 words unless failures require logs.` |

Use non-negotiable rules for safety boundaries:

```markdown
## Quality Standards

- Never edit files; this agent is read-only.
- Report only findings that can be reproduced from the provided files or command output.
- Include `file:line` for every code finding.
- Do not fetch external URLs unless the delegated task explicitly requires web research.
```

## Output Format templates

### Review report

```markdown
Verdict: PASS | PASS WITH FINDINGS | FAIL

Scope checked:
- [Files, diff, or command output reviewed]

Critical:
- `path:line` — [Defect] — [Impact] — [Required fix]

Major:
- `path:line` — [Defect] — [Impact] — [Recommended fix]

Minor:
- `path:line` — [Issue] — [Optional fix]

If no findings meet the reporting bar, write: `No reportable findings.`
```

### Research report

```markdown
## Answer

[Direct answer in 2-4 sentences.]

## Evidence

1. [Source or file] — [Relevant fact]
2. [Source or file] — [Relevant fact]
3. [Source or file] — [Relevant fact]

## Confidence

High | Medium | Low — [Why]

## Gaps

[Information not found, inaccessible, or intentionally out of scope.]
```

### Fix/patch report

```markdown
## Changes Made

- `[file]` — [Specific change]

## Verification

- `[command]` — PASS | FAIL | NOT RUN ([reason])

## Remaining Risks

- [Risk or `None identified`]

## Handoff

[What the main agent or user should do next.]
```

## Bound the scope

Agents with separate context windows can wander unless the prompt states a stop boundary.
Use at least one boundary for every agent.

| Boundary type | Example instruction |
| --- | --- |
| Files | `Inspect only files in the delegated path unless an imported definition is necessary.` |
| Time | `If the first test command runs longer than 5 minutes, stop and report partial output.` |
| Findings | `Report at most 10 findings, sorted by severity and confidence.` |
| Tools | `Do not use `execute`; this is a read-only analysis agent.` |
| Domain | `Review API documentation only; do not modify source code.` |

## Failure and incomplete work

Tell the agent what to do when it cannot complete the task. Use a visible failure report
instead of silent fallback.

```markdown
If you cannot complete the task, return:

Status: BLOCKED
Blocked step: [step number and name]
Reason: [missing input, unavailable tool, failing command, or ambiguous scope]
Evidence: [error text or file path]
Next action: [one concrete action for the caller]
```

Do not ask the agent to continue indefinitely. A bounded blocked report is more useful to
the caller than a speculative answer.

## Length budgeting

The prompt body limit is **30,000 characters**. Budget the prompt before it reaches the
cap.

| Prompt part | Target budget |
| --- | --- |
| Persona and scope | 300-600 characters |
| Core Responsibilities | 500-1,200 characters |
| Process | 1,500-4,000 characters |
| Quality Standards | 500-1,500 characters |
| Output Format | 700-2,000 characters |
| Edge cases and blocked format | 500-1,500 characters |

Move examples, background, and long rule catalogs out of the agent prompt. Custom agents do
not automatically load reference files the way skills do; if an agent needs a long external
reference, grant `read` and instruct it which file to open.

## Prompt review checklist

- [ ] Persona is one specific role, not a general assistant.
- [ ] Responsibilities are numbered outcomes.
- [ ] Process steps are ordered and include failure branches.
- [ ] Quality standards are testable.
- [ ] Output format is a literal template with a verdict or status line.
- [ ] Scope boundaries prevent whole-repository wandering.
- [ ] Blocked-work behavior is explicit.
- [ ] Body is under 30,000 characters, with room for future edits.
