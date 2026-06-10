# kaypoh-local packaging

Builds the offline-default desktop SKU as a single-folder PyInstaller distribution.

## Prereqs

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
```

## Build

```sh
uv run pyinstaller packaging/kaypoh-local.spec
```

Artifacts land in `dist/kaypoh-local/`. The launcher is `dist/kaypoh-local/kaypoh-local`.

## Run

```sh
./dist/kaypoh-local/kaypoh-local
# binds 127.0.0.1:8765 by default; deterministic engine only; cloud paths disabled
```

Override the loopback bind at launch:

```sh
KAYPOH_HOST=127.0.0.1 KAYPOH_PORT=8765 ./dist/kaypoh-local/kaypoh-local
```

Use a Unix-domain socket instead of TCP loopback when the client supports it:

```sh
KAYPOH_LOCAL_SOCKET_PATH=/tmp/kaypoh-local.sock ./dist/kaypoh-local/kaypoh-local
```

`browser_extension/` is the MV3 thin-client template for ChatGPT / Claude / Gemini. `office_addin/` is the Office.js taskpane template for Outlook pre-send review.

The local spec excludes the public-evidence and LLM-adjudicator modules. Use the source or Docker server runtime when a tenant has opted into those cloud-capable paths.
