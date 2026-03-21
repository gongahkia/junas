[![](https://img.shields.io/badge/kilter_together_1.0.0-passing-green)](https://github.com/gongahkia/kilter-together/releases/tag/1.0.0)
![](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# `Kilter Together`

Kilter Together is a collaborative climbing session app built with Flutter and peer-to-peer connectivity. One host creates a room, guests join via QR code or invite link, and everyone votes and queues climbs from their phones. No server required — all communication happens over P2P (Multipeer Connectivity on iOS, Nearby Connections on Android).

The app provisions a local offline Kilter dataset for solo browsing and relay-serves it to guests during collaborative sessions.

## Quick Start

```console
cd kilter-together-mobile
flutter pub get
flutter run
```

Requires Flutter SDK installed locally. Targets iOS and Android.

## How It Works

1. **Host** opens the app, picks a provider (`kilter` offline dataset or `crux`), and creates a room.
2. A QR code and invite link (`kiltertogether://join?slug=...`) are generated.
3. **Guests** scan the QR or tap the link, enter a display name, and join via P2P discovery.
4. Everyone votes on climbs, manages the queue, and tracks finalists in real-time over P2P.
5. When the session ends, a recap is saved locally.

## Architecture

- **Flutter** mobile app with feature-first modular structure
- **Riverpod** for state management
- **P2P transport layer** with platform-specific implementations:
  - iOS: Apple Multipeer Connectivity (native Swift plugin)
  - Android: Google Nearby Connections
  - Fallback: Stub transport for unsupported platforms
- **SQLite** offline Kilter catalog with cursor-based pagination
- **Secure storage** for provider credentials
- **Deep links** and QR codes for room invites

## Features

- Create and host collaborative climbing sessions
- Join sessions via QR scan, deep link, or nearby discovery
- Vote on climbs (fist bumps) with real-time sync
- Manage climb queue and finalists
- Solo catalog browsing with grade filtering
- Session recap with local history
- Offline-first Kilter dataset
- Plan sharing between sessions

## Project Structure

```
kilter-together-mobile/
├── lib/
│   ├── core/           # shared infra (p2p, models, storage, theme, routing)
│   ├── features/       # feature modules (room, join, create_room, solo, recap, etc)
│   ├── app.dart        # app config + deep link handling
│   └── main.dart       # entry point
├── ios/Runner/         # native Multipeer Connectivity plugin
├── android/            # Android platform code
└── test/               # unit tests
```

## Notes

- P2P sessions are inherently single-host. If the host leaves, the session ends.
- The offline Kilter catalog must be bootstrapped via Settings before solo browsing.
- Guests receive the catalog via P2P relay from the host during sessions.

## License

Provisioned under the [MIT License](./LICENSE).
