# macOS Signing Credentials

Status: decision for v1 release automation.

## Decision

Official Junas macOS releases use a project-level `Developer ID Application` certificate owned by the release owner, not a contributor's personal Apple developer identity.

Personal Developer ID certificates are acceptable only for private local experiments. They must not be used for release artifacts, Homebrew casks, public install docs, or CI notarization.

## Local Contributor Boundary

Contributors can run local unsigned builds:

```sh
./scripts/package_macos_desktop.sh
```

Unsigned output is a developer artifact only. It is not a release candidate, not a Homebrew input, and not a notarized DMG substitute.

Release maintainers can run signed local packaging after importing the project release certificate into their macOS keychain and storing notarization credentials as a keychain profile:

```sh
xcrun notarytool store-credentials junas-notary
JUNAS_CODESIGN_IDENTITY="Developer ID Application: <release owner> (<TEAMID>)" \
JUNAS_NOTARYTOOL_PROFILE=junas-notary \
JUNAS_RELEASE_SIGNING_REQUIRED=1 \
./scripts/package_macos_desktop.sh
```

Do not commit certificates, `.p12` files, app-specific passwords, Apple account emails, team ids, keychain exports, or notarytool profile material.

## CI Secret Storage

CI release signing must use a protected release environment. The expected secret boundary is:

| Secret | Storage | Runtime handling |
|---|---|---|
| Developer ID certificate export | GitHub Actions environment secret or external secret manager | Import into a temporary keychain only for the release job |
| Certificate password | GitHub Actions environment secret or external secret manager | Pass only to the keychain import command |
| Notarization credential | GitHub Actions environment secret or keychain profile setup step | Store in the temporary keychain profile before `notarytool submit` |
| Team/account metadata | Protected release variable or secret | Use only in the release job |

The repo does not store these values. Logs must not echo secret values. Release jobs should delete the temporary keychain before exit.

## Fail-Safe Release Mode

`scripts/package_macos_desktop.sh` stays unsigned by default for local contributors. Release automation must set:

```sh
JUNAS_RELEASE_SIGNING_REQUIRED=1
```

With that flag, the script fails before building if either `JUNAS_CODESIGN_IDENTITY` or `JUNAS_NOTARYTOOL_PROFILE` is missing. If a notary profile is set without a signing identity, the script also fails. The script checks that the configured signing identity is present in the keychain and prints only generic configuration errors.

This makes missing credentials a hard release failure while preserving the local unsigned developer path.
