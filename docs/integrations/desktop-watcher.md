# Desktop Watcher

Source: `src/kaypoh/desktop/`, `packaging/kaypoh-local.spec`, `packaging/macos/`

Maturity: `experimental-local-fallback`

Runtime target: macOS local watcher and packaged local daemon.

Build:

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
./scripts/package_macos_desktop.sh
```

Run packaged daemon:

```sh
./dist/kaypoh-local/kaypoh-local
curl http://127.0.0.1:8765/ready
```

Install LaunchAgent:

```sh
packaging/macos/install.sh
```

Current behavior:

- Local daemon binds `127.0.0.1:8765` by default.
- `kaypoh.desktop.watch` can review watched files and optional clipboard content.
- `--anonymize-output-dir` writes anonymized copies only when explicitly configured.
- Supported default file suffixes are `.txt`, `.md`, `.csv`, `.json`, and `.eml`.

Security model:

- Desktop watcher is an opt-in local fallback, not enterprise endpoint enforcement.
- Local daemon ACLs use `X-Kaypoh-Local-Token` when enabled.
- Clipboard polling must remain explicit user opt-in.
- Output must stay under the configured output directory.
- Auth failures must not print sensitive clipboard or file content.
