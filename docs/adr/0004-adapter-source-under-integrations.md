# ADR 0004: Adapter Source Under Top-Level `integrations/`

Status: Accepted

Date: 2026-06-14

## Context

Adapter source is currently split across `packaging/browser_extension/`, `packaging/office_addin/`, `packaging/word_addin/`, and `src/kaypoh/desktop/`. `packaging/` also contains PyInstaller specs, macOS installer scripts, and platform release assets. This mixes source ownership with release packaging and makes adapter maturity harder to read from the repo root.

The backend remains the trust boundary, and adapters remain optional activation surfaces. Moving adapter source should not imply that adapters are required for integration or that any adapter has stronger maturity than its matrix label.

## Decision

Move adapter source into top-level `integrations/` in a staged follow-up change:

- `packaging/browser_extension/` -> `integrations/browser_extension/`
- `packaging/office_addin/` -> `integrations/outlook_addin/`
- `packaging/word_addin/` -> `integrations/word_addin/`
- `src/kaypoh/desktop/` -> `integrations/desktop/`

Keep `packaging/` for packaging specs, release installers, launch-agent templates, platform packaging notes, and scripts that build artifacts from `integrations/`.

## Consequences

- Packaging scripts must be updated to use the new integration source paths.
- README and docs links must point to `integrations/` for adapter source and `docs/integrations/` for adapter docs.
- Compatibility paths or migration notes must remain for old source locations so existing contributors get a clear failure or pointer.
- Tests should assert packaging scripts fail clearly when expected integration paths are missing.
- Moving code does not promote adapter maturity; maturity remains governed by `docs/integrations/maturity-matrix.md`.

## Related Documents

- `docs/adr/0001-backend-first-adapters-second.md`
- `docs/integrations/README.md`
- `docs/integrations/maturity-matrix.md`
- `integrations/README.md`
