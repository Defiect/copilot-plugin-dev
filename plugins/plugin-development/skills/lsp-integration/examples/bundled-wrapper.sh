#!/usr/bin/env bash
set -euo pipefail

server="${1:-gopls}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$server" in
  gopls)
    install_hint="Install gopls with: go install golang.org/x/tools/gopls@latest"
    ;;
  pyright-langserver)
    install_hint="Install pyright with: npm install -g pyright"
    ;;
  rust-analyzer)
    install_hint="Install rust-analyzer with: rustup component add rust-analyzer"
    ;;
  *)
    install_hint="Install the language server binary '$server' and ensure it is on PATH."
    ;;
esac

if ! command -v "$server" >/dev/null 2>&1; then
  printf 'Language server binary not found: %s\n%s\n' "$server" "$install_hint" >&2
  exit 1
fi

exec "$server" "$@"
