# Evaluating and iterating on a skill

## Contents

- [Treat skill authoring as an evaluation problem](#treat-skill-authoring-as-an-evaluation-problem)
- [Build the evaluation set first](#build-the-evaluation-set-first)
- [Forward-testing with subagents](#forward-testing-with-subagents)
- [Validation integrity rules](#validation-integrity-rules)
- [Testing triggering separately from behavior](#testing-triggering-separately-from-behavior)
- [The iteration loop](#the-iteration-loop)
- [Regression checklist](#regression-checklist)

## Treat skill authoring as an evaluation problem

A skill is a prompt that ships. Like any prompt, its quality is measured by behavior, not
by how sensible it reads. The only reliable signal is: **does a fresh agent, given only
the skill and a realistic request, produce the right result?**

Introspection is unreliable here. The author knows what the skill means, so the author
cannot judge whether the text conveys it.

## Build the evaluation set first

Before writing the body, collect 3–8 concrete cases:

| Case type | Purpose |
| --- | --- |
| Two or three typical requests | The everyday path must work |
| One edge case | Exercises the branch most likely to be under-specified |
| One failure case | The skill must fail loudly, not guess |
| One near-miss request | Should **not** trigger the skill |

Write each as the raw text a user would type, and record the expected outcome separately
from the request. Keeping the two apart matters — see the integrity rules below.

## Forward-testing with subagents

Copilot CLI can run a subagent with its own context window. That subagent is the closest
available stand-in for a fresh user session.

For each evaluation case:

1. Make sure the skill is installed and reloaded (`/skills reload`).
2. Delegate the raw request to a subagent, phrased the way a user would phrase it.
3. Read the transcript, not just the answer. Look for the moment the agent guessed.
4. Reset any files the run modified before the next case.

A good delegation prompt:

```text
Use the /pdf-form-filling skill to fill data/applicant.json into forms/i-9.pdf and save
the result to out/i-9-filled.pdf.
```

A bad delegation prompt:

```text
Pretend a user asked you to fill a PDF. The skill should call fill_form.py with the JSON
path first and then flatten. Check that you do that.
```

The second prompt tells the agent the answer, so it tests nothing.

## Validation integrity rules

These rules are what separate a real evaluation from a self-congratulatory one.

1. **Pass raw artifacts, not conclusions.** Give the subagent the input file, the error
   message, the failing command — not your summary of what is wrong.
2. **Never state the expected answer** in the prompt, and never name the functions,
   flags, or file paths the skill is supposed to lead the agent to.
3. **Do not describe the test as a test.** "Pretend a user asks you to..." changes
   behavior. Phrase it as the task itself.
4. **Use a fresh context per case.** A subagent that already saw a previous run has been
   contaminated.
5. **Clean up between iterations.** Delete generated files and revert edits, or the next
   run starts from a state the skill did not create.
6. **If the run only succeeds when the agent sees extra context, the skill is
   underspecified.** Tighten the skill; do not loosen the test.

## Testing triggering separately from behavior

These are two different failure modes with two different fixes. Test them separately.

| Test | Prompt style | Fixes |
| --- | --- | --- |
| Behavior | Names the skill: `Use the /name skill to ...` | The body |
| Triggering | Never names the skill; phrased naturally | The description |
| Over-triggering | A near-miss request the skill should ignore | The description's boundary clause |

Run the behavior test first. There is no point tuning a description that leads to a body
which does not work.

## The iteration loop

```text
      ┌──────────────────────────────────────────────┐
      │ 1. Run every evaluation case in a fresh agent │
      └───────────────────┬──────────────────────────┘
                          ▼
      ┌──────────────────────────────────────────────┐
      │ 2. Find the FIRST point the agent went wrong  │
      └───────────────────┬──────────────────────────┘
                          ▼
      ┌──────────────────────────────────────────────┐
      │ 3. Ask why: missing info, ambiguous wording,   │
      │    or a step that needed a script?             │
      └───────────────────┬──────────────────────────┘
                          ▼
      ┌──────────────────────────────────────────────┐
      │ 4. Make ONE change. Re-run ALL cases.          │
      └───────────────────┬──────────────────────────┘
                          ▼
              repeat until every case passes twice
```

Diagnosis guide for step 3:

| The agent... | Root cause | Fix |
| --- | --- | --- |
| Never loaded the skill | Description | Add quoted user phrasings |
| Loaded it but improvised a step | Missing information | Add the exact command or contract |
| Chose a valid but wrong-for-you approach | Too much freedom | Narrow to one canonical way |
| Made an arithmetic or sequencing mistake | Task too fragile for prose | Replace the steps with a script |
| Did the right thing the long way | Body buried the key instruction | Move it earlier, or into a heading |
| Kept going after a failure | No stop condition | State explicitly: "If X fails, report it and stop" |

Change one thing at a time. Two simultaneous edits make it impossible to attribute the
result.

## Regression checklist

Run before publishing, and again after any substantive edit:

- [ ] `scripts/validate_skill.py PATH` exits 0.
- [ ] Every evaluation case passes in a fresh subagent, twice.
- [ ] The near-miss case does **not** trigger the skill.
- [ ] Every bundled script runs from a clean checkout on a machine without your local
      state.
- [ ] The skill works when invoked explicitly *and* when triggered naturally.
- [ ] No file inside the skill directory is unreferenced.
- [ ] No absolute paths, machine-specific paths, or personal credentials appear anywhere.
- [ ] The body contains no "When to use this skill" section.
- [ ] `/skills info NAME` reports the location and source you expect.
