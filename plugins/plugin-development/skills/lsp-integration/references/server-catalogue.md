# Language server catalogue

Use this catalogue to choose common language servers and extension mappings. Install
commands are for the reader's environment and are not verified by this repository.

## Contents

- [Catalogue](#catalogue)
- [Selection rules](#selection-rules)
- [Wrapper pattern](#wrapper-pattern)

## Catalogue

| Language | Server | Example install command | Launch command | File extensions to claim |
| --- | --- | --- | --- | --- |
| Go | `gopls` | `go install golang.org/x/tools/gopls@latest` | `gopls` | `.go` |
| Rust | `rust-analyzer` | `rustup component add rust-analyzer` | `rust-analyzer` | `.rs` |
| Python | `pyright` | `npm install -g pyright` | `pyright-langserver --stdio` | `.py`, `.pyw`, `.pyi` |
| Python | `basedpyright` | `pipx install basedpyright` | `basedpyright-langserver --stdio` | `.py`, `.pyw`, `.pyi` |
| TypeScript / JavaScript | `typescript-language-server` | `npm install -g typescript typescript-language-server` | `typescript-language-server --stdio` | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.mts`, `.cts` |
| C / C++ / Objective-C | `clangd` | `brew install llvm` or distro package manager | `clangd` | `.c`, `.h`, `.cc`, `.cpp`, `.cxx`, `.hpp`, `.hh`, `.m`, `.mm` |
| Java | `jdtls` | Install Eclipse JDT Language Server from its release docs | `jdtls` | `.java` |
| Lua | `lua-language-server` | `brew install lua-language-server` or release archive | `lua-language-server` | `.lua` |
| Bash | `bash-language-server` | `npm install -g bash-language-server` | `bash-language-server start` | `.sh`, `.bash`, `.zsh` |
| YAML | `yaml-language-server` | `npm install -g yaml-language-server` | `yaml-language-server --stdio` | `.yaml`, `.yml` |
| Ruby | `ruby-lsp` | `gem install ruby-lsp` | `ruby-lsp` | `.rb`, `.rbw`, `.rake`, `.gemspec` |

## Selection rules

1. **Prefer the ecosystem default.** Use `gopls` for Go, `rust-analyzer` for Rust, and
   `typescript-language-server` for TypeScript unless the plugin has a specific reason.
2. **Avoid duplicate claims.** Do not map `.py` to both `pyright` and `basedpyright` in
   the same plugin.
3. **Use documented language IDs.** Follow the language server's examples for values such
   as `typescriptreact` or `javascriptreact`.
4. **Ship wrappers for optional dependencies.** A wrapper turns a missing global install
   into an actionable error.

## Wrapper pattern

For a plugin-bundled launcher, use a shell script like
`examples/bundled-wrapper.sh` that checks the binary and then `exec`s it. Keep install
instructions in plugin docs, not inside the JSON config, because Copilot reads the config
every session.
