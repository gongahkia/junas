# Integration Docs

These pages mirror current adapter notes after ADR 0004. Adapter source lives under top-level `integrations/`; old packaging and `src/kaypoh/desktop` paths remain compatibility symlinks for existing local workflows.

| Adapter | Source path | Mirror doc |
|---|---|---|
| Direct API and Python client | `src/kaypoh/backend/`, `src/kaypoh/client.py`, `docs/api/` | `direct-api.md` |
| Browser GenAI extension | `integrations/browser_extension/` | `browser-extension.md` |
| Outlook Smart Alerts add-in | `integrations/outlook_addin/` | `outlook.md` |
| Word taskpane | `integrations/word_addin/` | `word.md` |
| Desktop watcher/local daemon | `integrations/desktop/`, `packaging/` | `desktop-watcher.md` |
| DMS manifest scanner | `src/kaypoh/integrations/dms.py`, `scripts/scan_dms_manifest.py` | `dms.md` |

Adapters are optional activation surfaces. They collect workflow context, call the backend contract, display policy decisions, and must not become alternate trust boundaries.

Use `maturity-matrix.md` for the definitions of `core`, `supported-target`, `experimental`, `demo-only`, and `archived`.
