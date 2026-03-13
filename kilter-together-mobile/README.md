# Kilter Together Mobile

Flutter mobile client for Kilter Together.

The current requirements reference for the highest-urgency collaborative mobile
journey lives in
[../P1_P2_COLLABORATIVE_FLOW_REQUIREMENTS.md](../P1_P2_COLLABORATIVE_FLOW_REQUIREMENTS.md).

## Status

This workspace is a hand-authored, feature-first Flutter client. It includes the
mobile app shell, token-aware API client, invite parsing, secure session storage,
branch-specific onboarding and flow guides, and the create, join, room, solo,
recap, plan, and settings flows against the rewritten Go API contract.

## Local Setup

1. Install Flutter and Dart locally.
2. Run `flutter pub get`.
3. Run `flutter analyze` and `flutter test`.
4. Use `flutter run` for Android or iOS targets.

## Current Feature Coverage

- Landing screen with recent self-hosted servers
- Create room flow using the bearer-token API contract
- Join room flow with custom invite parsing
- Room screen with token-backed load, refresh, and SSE subscription
- Solo browse, recap, and plan sharing flows
- Shared storage for active server, recent servers, and room sessions
