  1. Packaging
      - macOS signing/notarisation
      - Windows build if shipping Windows
      - installer, auto-start, uninstall, update path

  2. Local daemon security
      - browser/Office first-connect pairing
      - signed token flow
      - token storage UX
      - Origin/CORS hardening smoke tests

  3. Distribution surfaces
      - browser paste interception + signed extension package
      - Word add-in
      - Outlook event-based pre-send hook
      - native tray UX / watched-folder UX

  4. Enterprise server
      - Okta / Azure AD / SAML packaging
      - tenant key rotation UX
      - appliance runbook: install, upgrade, backup, restore
      - external KMS / customer-held keys

  5. Parser fidelity
      - PDF XFA / signed-region semantics
      - native .msg
      - 7z
      - richer Office embedded-object/media mapping

  6. Ops / compliance
      - production preflight command
      - retention manifest docs
      - SIEM setup docs
      - audit-pack export/verify smoke
      - redacted logs only

  7. Docs
      - install guide
      - admin/security guide
      - data-flow/threat model
      - known limitations
      - “not legal advice / not procurement-grade eval” wording
