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
| macOS automation wrappers | `integrations/macos_automation/` | `macos-automation.md` |
| Multi-display capture helper | `integrations/desktop/displays.py` | `multi-display-capture.md` |
| Offline video redaction | `integrations/desktop/offline_video.py` | `offline-video-redaction.md` |
| Time-machine buffer prototype | `integrations/desktop/time_buffer.py` | `time-machine-buffer.md` |
| OBS source-plugin prototype | `src/junas/integrations/obs_source.py` | `obs-source-plugin.md` |
| Direct MP4 sink | `integrations/desktop/mp4_sink.py` | `direct-mp4-sink.md` |
| DMS manifest scanner | `src/junas/integrations/dms.py`, `scripts/scan_dms_manifest.py` | `dms.md` |
| DMS matter id mapping | backend contract boundary | `dms-matter-ids.md` |
| Adapter compatibility matrix | backend contract boundary | `compatibility-matrix.md` |
| Adapter packaging | browser and Office artifact boundary | `adapter-packaging.md` |
| Adapter certification checklist | promotion evidence boundary | `adapter-certification-checklist.md` |
| No single pathway pilot guidance | production pilot boundary | `no-single-pathway.md` |
| Future Slack / Google Workspace notes | research-only | `future-slack-google-workspace.md` |
| Shared adapter protocol | backend contract boundary | `adapter-protocol.md` |
| Shared adapter auth | backend auth boundary | `auth.md` |
| Shared adapter privacy | backend privacy boundary | `privacy.md` |
| Shared adapter telemetry | backend observability boundary | `telemetry.md` |
| Shared recipient context | backend policy boundary | `recipient-context.md` |
| Shared document context | backend policy boundary | `document-context.md` |
| Shared failure semantics | backend contract boundary | `failure-semantics.md` |
| Shared adapter sequence diagrams | backend contract boundary | `sequence-diagrams.md` |

Adapters are optional activation surfaces. They collect workflow context, call the backend contract, display policy decisions, and must not become alternate trust boundaries.

Use `maturity-matrix.md` for maturity label definitions and `adapter-maturity.json` for the machine-readable surface registry used by tests.
