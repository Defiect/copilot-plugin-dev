#!/usr/bin/env bash
# Run every validator in the repository. Warnings are treated as errors.
#
# Usage: ./scripts/validate-all.sh [--allow-warnings]
#
# Exit codes: 0 = all checks passed, 1 = one or more checks reported findings.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 2

PLUGIN="plugins/plugin-development"
SKILLS="$PLUGIN/skills"
PY="${PYTHON:-python3}"

STRICT="--warnings-as-errors"
if [[ "${1:-}" == "--allow-warnings" ]]; then
  STRICT=""
fi

FAILED=()
PASSED=0

run() {
  local label="$1"
  shift
  printf '\n\033[1m==> %s\033[0m\n' "$label"
  if "$@"; then
    PASSED=$((PASSED + 1))
  else
    FAILED+=("$label")
  fi
}

# shellcheck disable=SC2086
run "plugin manifest and structure" \
  "$PY" "$SKILLS/plugin-development/scripts/validate_plugin.py" "$PLUGIN" $STRICT

# shellcheck disable=SC2086
run "skills (recursive)" \
  "$PY" "$SKILLS/skill-development/scripts/validate_skill.py" "$SKILLS" --recursive $STRICT

# shellcheck disable=SC2086
run "agents (recursive)" \
  "$PY" "$SKILLS/agent-development/scripts/validate_agent.py" "$PLUGIN/agents" --recursive $STRICT

# shellcheck disable=SC2086
run "marketplace manifest" \
  "$PY" "$SKILLS/marketplace-development/scripts/validate_marketplace.py" \
  .github/plugin/marketplace.json $STRICT

# Example configurations ship as documentation, so they must stay valid.
for example in "$SKILLS"/hook-development/examples/*.json; do
  [[ -e "$example" ]] || continue
  # shellcheck disable=SC2086
  run "hooks example: $(basename "$example")" \
    "$PY" "$SKILLS/hook-development/scripts/validate_hooks.py" "$example" $STRICT
done

for example in "$SKILLS"/mcp-integration/examples/*.json; do
  [[ -e "$example" ]] || continue
  # shellcheck disable=SC2086
  run "mcp example: $(basename "$example")" \
    "$PY" "$SKILLS/mcp-integration/scripts/validate_mcp.py" "$example" $STRICT
done

for example in "$SKILLS"/lsp-integration/examples/*.json; do
  [[ -e "$example" ]] || continue
  # shellcheck disable=SC2086
  run "lsp example: $(basename "$example")" \
    "$PY" "$SKILLS/lsp-integration/scripts/validate_lsp.py" "$example" $STRICT
done

run "plugin smoke test" \
  bash "$SKILLS/plugin-testing/scripts/smoke_test_plugin.sh" "$PLUGIN"

printf '\n\033[1m==> Summary\033[0m\n'
if [[ ${#FAILED[@]} -eq 0 ]]; then
  printf '\033[32mAll %d check(s) passed.\033[0m\n' "$PASSED"
  exit 0
fi

printf '\033[31m%d check(s) failed:\033[0m\n' "${#FAILED[@]}"
for label in "${FAILED[@]}"; do
  printf '  - %s\n' "$label"
done
exit 1
