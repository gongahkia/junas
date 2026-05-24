# kaypoh-local packaging

Builds the offline-default desktop SKU as a single-folder distribution (or single binary if
the spec is flipped) using PyInstaller.

## Prereqs

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[local,packaging]"
python -m spacy download en_core_web_sm
```

## Build

```sh
pyinstaller packaging/kaypoh-local.spec
```

Artifacts land in `dist/kaypoh-local/`. The launcher is `dist/kaypoh-local/kaypoh-local`.

## Run

```sh
./dist/kaypoh-local/kaypoh-local
# binds 127.0.0.1:8765 by default; PIPELINE_LAYERS=lexicon; cloud paths disabled
```

## Override defaults

The spec hardcodes loopback host + lexicon-only pipeline. Override at launch:

```sh
KAYPOH_HOST=127.0.0.1 KAYPOH_PORT=8765 ./dist/kaypoh-local/kaypoh-local
```

Setting `KAYPOH_PUBLIC_EVIDENCE_ENABLED=1` or `KAYPOH_LLM_ENABLED=1` will not enable those
layers in this build — the spec excludes their backing modules. To use cloud-when-better
paths, install `kaypoh[server]` instead and run from source.

## Verify the offline guarantee

After building, confirm no outbound sockets:

```sh
# macOS
lsof -nP -p $(pgrep -f kaypoh-local) | grep -E "TCP|UDP" | grep -v "127.0.0.1\|::1"
```

A clean offline binary returns no rows.
