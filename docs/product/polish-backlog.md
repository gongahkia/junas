# Polish Backlog

This backlog captures low-cost polish ideas that must not block v1 launch. Treat every item here as deferred unless a later issue supplies user evidence, acceptance criteria, and a test path.

| Item | Estimate | v1 launch status | Maintainer discoverability |
|---|---:|---|---|
| Menu-bar easter egg: option-click cycles transforms instantly. | 0.5-1 day | Non-blocking polish. Do not implement before launch-critical review, packaging, and demo tasks. | Document the option-click path in maintainer docs or a debug menu note; add a UI smoke check for the modifier behavior. |
| Optional stress-test panel via a hidden shortcut. | 1-2 days | Non-blocking diagnostic surface. Keep out of default user flows. | Gate behind a named debug shortcut, list it in maintainer docs, and add a fixture-driven smoke test that opens/closes the panel. |
| `junas sticker` command that outputs a print-ready postcard PDF, if still worth doing. | 1-2 days | Non-blocking brand artifact. Re-evaluate after launch copy, demo URL, and current Junas branding are stable. | Put the command in CLI help and docs if built; store golden PDF/render checks under test artifacts. |

## Rule

None of these items blocks v1 launch. Hidden UI must be discoverable to maintainers through docs, CLI help, debug-menu labels, or tests before it ships.
