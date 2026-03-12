# Kilter Together Mobile

Flutter mobile client for Kilter Together.

## Status

This workspace is hand-authored because the Flutter SDK is not currently available on the machine `PATH`. It includes the initial feature-first app shell, token-aware API client, invite parsing, secure session storage, and the first create/join/room flows against the rewritten Go API contract.

## Intended Setup

1. Install Flutter and Dart locally.
2. Run `flutter create . --platforms=android,ios` from this directory to generate the platform shells around the existing `lib/` and config files.
3. Run `flutter pub get`.
4. Use `flutter run` for Android or iOS targets.

## Current Feature Coverage

- Landing screen with recent self-hosted servers
- Create room flow using the bearer-token API contract
- Join room flow with custom invite parsing
- Room screen with token-backed load, refresh, and SSE subscription
- Shared storage for active server, recent servers, and room sessions

