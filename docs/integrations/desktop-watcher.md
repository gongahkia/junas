# Desktop Watcher

Source: `integrations/desktop/`, `packaging/junas-local.spec`, `packaging/macos/`

Compatibility path: `src/junas/desktop/`

Maturity: `experimental-local-fallback`

Runtime target: macOS local watcher and packaged local daemon.

`junas-watch` remains a packaged console script for explicit opt-in local review. Its
maturity is `experimental-local-fallback`; do not present it as production endpoint
enforcement.

## Intended Use

Use the desktop watcher for offline local fallback, demos, and power users who
explicitly choose local file, folder, or clipboard review. Do not use it as enterprise
enforcement, fleet policy, endpoint DLP, or proof that every local workflow was
reviewed. Enforced production workflows should use direct API integration, Outlook Smart
Alerts, DMS hooks, or managed browser adapters.

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

## Optional LaunchAgent Install

`packaging/macos/install.sh` installs a LaunchAgent with `RunAtLoad` and `KeepAlive`.
Treat it as optional and admin-controlled, not a default developer quickstart path. For
developer smoke tests, run `./dist/junas-local/junas-local` directly and install the
LaunchAgent only when an operator has approved auto-start behavior for that profile.

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

Reference config sample: `docs/integrations/desktop-watcher.config.sample.toml`.
The current CLI is flag/env based and does not parse that file directly; use it as an
operator checklist when building shell wrappers, MDM profiles, or runbooks. The sample
keeps `clipboard = false` and requires explicit user opt-in through `--clipboard`.

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

## Threat Model

- Clipboard sensitivity: `--clipboard` reads the whole current macOS clipboard through
  `pbpaste` when polling runs. Clipboard mode must stay off by default because the
  clipboard may contain passwords, tokens, personal messages, or copied customer data.
- Local token use: `--local-token`, `--local-token-file`, and
  `JUNAS_LOCAL_DAEMON_TOKEN` send `X-Junas-Local-Token` to the local daemon. Treat the
  token as same-user local secret material; do not paste it into shell history, shared
  logs, notifications, or bug reports.
- Notifications: `--notify` uses macOS `osascript` notifications only when findings are
  present. Notifications should contain counts and source labels only; they can still
  expose a path or the word `clipboard` to screenshots, screen sharing, or lock-screen
  previews.
- Watched-folder scope: `--watch-folder` scans recursively for supported suffixes. Use a
  dedicated drop directory, not a home directory, synced drive root, mail archive, or
  source tree with unrelated customer files.
- Accidental large-file scans: the current CLI has no max-file-size option. A large
  matching file is read into memory and sent to the backend, so operators should test
  with `--once`, keep watched folders small, and avoid broad recursive roots until size
  limits are implemented.

## Enforcement Boundary

The desktop watcher is not enterprise endpoint enforcement.

- It does not block paste, save, send, upload, browser submit, email send, or DMS check-in.
- It does not run as an EDR, DLP agent, kernel extension, browser policy, or MDM control.
- It cannot prove that every local file, clipboard value, or app workflow was reviewed.
- It should route enforced workflows to direct API, Outlook Smart Alerts, DMS hooks, or managed browser adapters.

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
