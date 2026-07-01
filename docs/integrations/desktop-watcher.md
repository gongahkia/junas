# Desktop Watcher

Source: `integrations/desktop/`, `packaging/junas-local.spec`, `packaging/macos/`

Compatibility path: `src/junas/desktop/`

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
./dist/junas-local/junas-local
curl http://127.0.0.1:8765/ready
```

Install LaunchAgent:

```sh
packaging/macos/install.sh
```

Current behavior:

- Local daemon binds `127.0.0.1:8765` by default.
- `junas.desktop.watch` can review watched files and optional clipboard content.
- `--anonymize-output-dir` writes anonymized copies only when explicitly configured.
- Supported default file suffixes are `.txt`, `.md`, `.csv`, `.json`, and `.eml`.

## Opt-In Local Fallback Flow

The watcher runs only when a user or operator starts it with an explicit source:

```sh
uv run junas-watch ./draft.txt --base-url http://127.0.0.1:8765
uv run junas-watch --watch-folder ./drop --once --base-url http://127.0.0.1:8765
uv run junas-watch --clipboard --once --base-url http://127.0.0.1:8765
```

If no file path, `--watch-folder`, or `--clipboard` is provided, the CLI exits with an argument error. Clipboard polling is never enabled by default.

## Folder Watch

- `--watch-folder` recursively scans supported text-like suffixes.
- The first scan reviews existing matching files, then later scans review changed files.
- `--poll-seconds` controls polling interval.
- `--once` performs one scan and exits.
- `--anonymize-output-dir` writes anonymized copies only when findings exist and output is explicitly configured.

## Clipboard Watch

- `--clipboard` reads macOS clipboard text through `pbpaste`.
- Empty or unchanged clipboard text is skipped.
- Clipboard review emits a JSON summary; it should not print raw clipboard content.
- Use clipboard mode only for demos, offline local review, or power-user workflows where the user opted in.

## Enforcement Boundary

The desktop watcher is not enterprise endpoint enforcement.

- It does not block paste, save, send, upload, browser submit, email send, or DMS check-in.
- It does not run as an EDR, DLP agent, kernel extension, browser policy, or MDM control.
- It cannot prove that every local file, clipboard value, or app workflow was reviewed.
- It should route enforced workflows to direct API, Outlook Smart Alerts, DMS hooks, or managed browser adapters.

## Threat Model

The desktop watcher is an experimental opt-in local fallback and should not be treated as enterprise endpoint enforcement.

### Clipboard sensitivity

- Clipboard monitoring is enabled only when the user explicitly starts the watcher with `--clipboard`.
- Clipboard contents should be treated as sensitive and should not be written to logs or exposed in error messages.
- Clipboard review is intended for local review workflows where the user has explicitly opted in.

### Local authentication

- When local daemon ACLs are enabled, use `--local-token`, `--local-token-file`, or `JUNAS_LOCAL_DAEMON_TOKEN`.
- Authentication failures must not expose clipboard or watched file contents.

### Notifications and review

- The watcher provides local review results only.
- It does not guarantee that notifications are acknowledged or acted upon.
- Users remain responsible for deciding whether reviewed content should be shared.

### Watched-folder scope

- Configure `--watch-folder` only for directories intended for review.
- Avoid monitoring unnecessarily broad locations to reduce accidental review of unrelated files.
- Use `--once` when a single review pass is sufficient.

### Large-file considerations

- The watcher is intended for supported text-like files.
- Restrict watched folders to the intended review scope to reduce accidental scans of large or unrelated files.
- Enterprise enforcement workflows should use supported integrations instead of relying on local folder monitoring.

## Auth And Output

- Use `--local-token`, `--local-token-file`, or `JUNAS_LOCAL_DAEMON_TOKEN` when local daemon ACLs are enabled.
- Output is a JSON summary with source, risk, finding count, document score, and optional anonymized path.
- Do not redirect watcher output to shared logs unless paths and counts are acceptable for that environment.
- Keep `--anonymize-output-dir` scoped to a user-approved directory.

Security model:

- Desktop watcher is an opt-in local fallback, not enterprise endpoint enforcement.
- Local daemon ACLs use `X-Junas-Local-Token` when enabled.
- Clipboard polling must remain explicit user opt-in.
- Output must stay under the configured output directory.
- Auth failures must not print sensitive clipboard or file content.
