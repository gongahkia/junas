# macOS Signing And Credential Policy

## Decision

V1 releases use a maintainer-owned personal Developer ID Application certificate controlled by the repository owner.

A project-level Apple Developer identity is deferred until Aki has a legal organization or release team that can own Apple Developer Program membership, certificate renewal, incident response, and billing. A personal Developer ID is the simplest release-capable identity for the current single-maintainer project.

This decision does not allow Apple Development certificates for public releases. Apple Development identities are local-debug identities only and do not satisfy Gatekeeper for downloaded DMGs.

## Required Identity

Public DMG releases require:

- `Developer ID Application: <Name> (<TEAMID>)`
- Apple notarization credentials for the same Apple Developer Team ID

A Developer ID Installer certificate is not required for the current DMG flow because Aki ships as an app bundle inside a DMG, not as a `.pkg` installer.

## Local Secret Storage

The release maintainer may keep the Developer ID Application certificate in their macOS login keychain or a dedicated release keychain. The `.p12` export password and Apple app-specific password must live in a password manager, not in the repository.

Preferred local notarization setup:

```console
$ xcrun notarytool store-credentials aki-notary \
    --apple-id apple-id@example.com \
    --team-id TEAMID \
    --password app-specific-password
```

Then run:

```console
$ export AKI_SIGN_IDENTITY="Developer ID Application: Example Name (TEAMID)"
$ export AKI_NOTARY_KEYCHAIN_PROFILE="aki-notary"
$ scripts/release_macos_dmg.sh --version 0.1.0
```

Local `.env` files are ignored by Git. They may be used for non-shared release-maintainer convenience, but they must not be committed or pasted into issue/PR logs.

## CI Secret Storage

GitHub-hosted release builds use the protected `release` Environment. Configure required reviewers for that Environment before adding credentials.

Required Environment secrets:

- `MACOS_DEVELOPER_ID_APPLICATION_CERT_P12_BASE64`
- `MACOS_DEVELOPER_ID_APPLICATION_CERT_PASSWORD`
- `MACOS_DEVELOPER_ID_APPLICATION_IDENTITY`
- `AKI_NOTARY_APPLE_ID`
- `AKI_NOTARY_TEAM_ID`
- `AKI_NOTARY_PASSWORD`

The workflow imports the `.p12` into an ephemeral keychain, signs the app and DMG, submits notarization, uploads artifacts to the GitHub Release, and deletes the keychain in an `always()` cleanup step.

Do not store release credentials as normal repository files, workflow inputs, command-line arguments in PR comments, or plaintext build logs.

## Contributor Access

Contributors can run:

```console
$ cargo test --all
$ swift build --package-path macos/AkiMenuBar
$ scripts/release_macos_dmg.sh --unsigned
```

Contributors without release credentials cannot:

- Produce a public signed/notarized DMG.
- Run the protected GitHub release workflow successfully.
- Access Developer ID certificates, `.p12` exports, notary passwords, or GitHub Environment secrets.

This split lets contributors validate packaging mechanics without granting distribution authority.

## Safe Failure Rules

The release process must fail before public artifact creation when:

- `AKI_SIGN_IDENTITY` is missing.
- `AKI_SIGN_IDENTITY` is not a Developer ID Application identity.
- The named identity is not present in the keychain.
- Notarization credentials are missing and notarization was not explicitly skipped.
- A required non-system dylib cannot be vendored into the app bundle.

The script must not print app-specific passwords. The GitHub workflow must not echo secrets except through masked environment usage required to import the signing certificate.

## Rotation

If release credentials are suspected to be exposed:

1. Revoke the affected Developer ID certificate in Apple Developer.
2. Rotate the app-specific password or notary credential.
3. Replace GitHub Environment secrets.
4. Re-run a signed/notarized release from the protected workflow.
