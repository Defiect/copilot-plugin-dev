#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: smoke_test_plugin.sh PLUGIN_DIR

Run static checks for a GitHub Copilot CLI plugin without installing it.
Checks plugin manifest discovery, JSON parsing, validate_*.py scripts under skills,
Python compilation, shell syntax, required SKILL.md files, non-empty agent files, and
executable shebang scripts.
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

PLUGIN_DIR="$1"
if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "error: plugin directory not found: $PLUGIN_DIR" >&2
  exit 2
fi

PLUGIN_DIR="$(cd "$PLUGIN_DIR" && pwd -P)"
USE_COLOR=0
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  USE_COLOR=1
fi

paint() {
  local code="$1" text="$2"
  if [[ "$USE_COLOR" -eq 1 ]]; then
    printf '\033[%sm%s\033[0m' "$code" "$text"
  else
    printf '%s' "$text"
  fi
}

PASS_COUNT=0
FAIL_COUNT=0
FAILURES=()

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '%s %s\n' "$(paint '32;1' PASS)" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAILURES+=("$1")
  printf '%s %s\n' "$(paint '31;1' FAIL)" "$1"
}

check_cmd() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "$label"
  else
    fail "$label"
  fi
}

MANIFEST="$(python3 - "$PLUGIN_DIR" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for rel in ('.plugin/plugin.json', 'plugin.json', '.github/plugin/plugin.json', '.claude-plugin/plugin.json'):
    path = root / rel
    if path.is_file():
        print(path)
        sys.exit(0)
sys.exit(1)
PY
)" || true

if [[ -n "${MANIFEST:-}" ]]; then
  pass "found plugin manifest: ${MANIFEST#$PLUGIN_DIR/}"
  check_cmd "plugin manifest parses as JSON" python3 -m json.tool "$MANIFEST"
else
  fail "no plugin manifest found"
fi

while IFS= read -r -d '' json_file; do
  rel="${json_file#$PLUGIN_DIR/}"
  if command -v jq >/dev/null 2>&1; then
    check_cmd "JSON parses: $rel" jq empty "$json_file"
  else
    check_cmd "JSON parses: $rel" python3 -m json.tool "$json_file"
  fi
done < <(find "$PLUGIN_DIR" -type f -name '*.json' -print0)

while IFS= read -r -d '' validator; do
  rel="${validator#$PLUGIN_DIR/}"
  dir="$(dirname "$validator")"
  skill_dir="$(dirname "$dir")"
  case "$(basename "$validator")" in
    validate_plugin.py)
      check_cmd "validator runs: $rel" python3 "$validator" "$PLUGIN_DIR"
      ;;
    validate_skill.py)
      if [[ -f "$skill_dir/SKILL.md" ]]; then
        check_cmd "validator runs: $rel" python3 "$validator" "$skill_dir"
      else
        check_cmd "validator help: $rel" python3 "$validator" --help
      fi
      ;;
    validate_marketplace.py)
      if [[ -f "$PLUGIN_DIR/marketplace.json" || -f "$PLUGIN_DIR/.plugin/marketplace.json" || -f "$PLUGIN_DIR/.github/plugin/marketplace.json" || -f "$PLUGIN_DIR/.claude-plugin/marketplace.json" ]]; then
        check_cmd "validator runs: $rel" python3 "$validator" "$PLUGIN_DIR"
      else
        check_cmd "validator help: $rel" python3 "$validator" --help
      fi
      ;;
    *)
      check_cmd "validator help: $rel" python3 "$validator" --help
      ;;
  esac
done < <(find "$PLUGIN_DIR/skills" -type f -name 'validate_*.py' -print0 2>/dev/null || true)

while IFS= read -r -d '' py_file; do
  check_cmd "Python compiles: ${py_file#$PLUGIN_DIR/}" python3 -m py_compile "$py_file"
done < <(find "$PLUGIN_DIR" -type f -name '*.py' -print0)

while IFS= read -r -d '' sh_file; do
  check_cmd "shell syntax: ${sh_file#$PLUGIN_DIR/}" bash -n "$sh_file"
done < <(find "$PLUGIN_DIR" -type f -name '*.sh' -print0)

SKILLS_ROOTS="$(python3 - "$PLUGIN_DIR" <<'PY'
from pathlib import Path
import json, sys
root = Path(sys.argv[1])
manifest = root / 'plugin.json'
paths = ['skills/']
if manifest.is_file():
    try:
        data = json.loads(manifest.read_text())
        value = data.get('skills', 'skills/')
        if isinstance(value, str):
            paths = [value]
        elif isinstance(value, list):
            paths = [p for p in value if isinstance(p, str)]
    except Exception:
        pass
for path in paths:
    print(root / path)
PY
)"

while IFS= read -r skills_root; do
  [[ -d "$skills_root" ]] || continue
  while IFS= read -r -d '' skill_dir; do
    rel="${skill_dir#$PLUGIN_DIR/}"
    if [[ -f "$skill_dir/SKILL.md" ]]; then
      pass "skill has SKILL.md: $rel"
    else
      fail "skill missing SKILL.md: $rel"
    fi
  done < <(find "$skills_root" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -print0)
done <<< "$SKILLS_ROOTS"

while IFS= read -r -d '' agent_file; do
  rel="${agent_file#$PLUGIN_DIR/}"
  if [[ -s "$agent_file" ]]; then
    pass "agent file non-empty: $rel"
  else
    fail "agent file empty: $rel"
  fi
done < <(find "$PLUGIN_DIR" -type f -name '*.agent.md' -print0)

while IFS= read -r -d '' script_file; do
  rel="${script_file#$PLUGIN_DIR/}"
  if head -n 1 "$script_file" | grep -q '^#!'; then
    if [[ -x "$script_file" ]]; then
      pass "shebang script executable: $rel"
    else
      fail "shebang script is not executable: $rel"
    fi
  fi
done < <(find "$PLUGIN_DIR" -type f \( -name '*.py' -o -name '*.sh' -o -name '*.bash' \) -print0)

echo
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  printf '%s %d checks passed\n' "$(paint '32;1' PASS)" "$PASS_COUNT"
  exit 0
fi
printf '%s %d passed, %d failed\n' "$(paint '31;1' FAIL)" "$PASS_COUNT" "$FAIL_COUNT"
printf 'Failures:\n'
for failure in "${FAILURES[@]}"; do
  printf '  - %s\n' "$failure"
done
exit 1
