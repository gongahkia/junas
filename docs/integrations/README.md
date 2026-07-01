# Integration Docs

These pages mirror current adapter notes after ADR 0004. Adapter source lives under top-level `integrations/`; old packaging and `src/junas/desktop` paths remain compatibility symlinks for existing local workflows.

| Adapter | Source path | Mirror doc |
|---|---|---|
| Direct API and Python client | `src/junas/backend/`, `src/junas/client.py`, `docs/api/` | `direct-api.md` |
| Browser GenAI extension | `integrations/browser_extension/` | `browser-extension.md` |
| GenAI browser capture assumptions | `integrations/browser_extension/` | `genai-browser.md` |
| Browser enterprise deployment | `integrations/browser_extension/` | `browser-enterprise-deployment.md` |
| Outlook Smart Alerts add-in | `integrations/outlook_addin/` | `outlook.md` |
| Word taskpane | `integrations/word_addin/` | `word.md` |
| Desktop watcher/local daemon | `integrations/desktop/`, `packaging/` | `desktop-watcher.md` |
| DMS manifest scanner | `src/junas/integrations/dms.py`, `scripts/scan_dms_manifest.py` | `dms.md` |
| Shared adapter protocol | backend contract boundary | `adapter-protocol.md` |
| Shared adapter auth | backend auth boundary | `auth.md` |
| Shared adapter privacy | backend privacy boundary | `privacy.md` |
| Shared adapter telemetry | backend observability boundary | `telemetry.md` |
| Shared recipient context | backend policy boundary | `recipient-context.md` |
| Shared failure semantics | backend contract boundary | `failure-semantics.md` |
| Shared adapter sequence diagrams | backend contract boundary | `sequence-diagrams.md` |

Adapters are optional activation surfaces. They collect workflow context, call the backend contract, display policy decisions, and must not become alternate trust boundaries.

Use `maturity-matrix.md` for the definitions of `core`, `supported-target`, `experimental`, `demo-only`, and `archived`.
