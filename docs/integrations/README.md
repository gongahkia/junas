# Integration Docs

These pages mirror current adapter notes after ADR 0004. Adapter source lives under top-level `integrations/`; old packaging and `src/kaypoh/desktop` paths remain compatibility symlinks during migration.

| Adapter | Source path | Mirror doc |
|---|---|---|
| Browser GenAI extension | `integrations/browser_extension/` | `browser-extension.md` |
| Outlook Smart Alerts add-in | `integrations/outlook_addin/` | `outlook.md` |
| Word taskpane | `integrations/word_addin/` | `word.md` |
| Desktop watcher/local daemon | `integrations/desktop/`, `packaging/` | `desktop-watcher.md` |

Adapters are optional activation surfaces. They collect workflow context, call the backend contract, display policy decisions, and must not become alternate trust boundaries.

Use `maturity-matrix.md` for the definitions of `core`, `supported-target`, `experimental`, `demo-only`, and `archived`.
