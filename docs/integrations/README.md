# Integration Docs

These pages mirror the current adapter notes before any source layout move. Adapter source remains in `packaging/`, `src/kaypoh/desktop/`, and `src/kaypoh/integrations/`.

| Adapter | Source path | Mirror doc |
|---|---|---|
| Browser GenAI extension | `packaging/browser_extension/` | `browser-extension.md` |
| Outlook Smart Alerts add-in | `packaging/office_addin/` | `outlook.md` |
| Word taskpane | `packaging/word_addin/` | `word.md` |
| Desktop watcher/local daemon | `src/kaypoh/desktop/`, `packaging/` | `desktop-watcher.md` |

Adapters are optional activation surfaces. They collect workflow context, call the backend contract, display policy decisions, and must not become alternate trust boundaries.

Use `maturity-matrix.md` for the definitions of `core`, `supported-target`, `experimental`, `demo-only`, and `archived`.
