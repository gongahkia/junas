# Local Daemon Security

This document covers the packaged `junas-local` daemon and browser/Office/desktop clients that call it on the same machine.

## Default Runtime

- Packaged daemon entrypoint: `packaging/junas_local_entrypoint.py`.
- Default bind: `127.0.0.1:8765`.
- Default local ACL in packaged mode: `JUNAS_LOCAL_DAEMON_ACL_ENABLED=1`.
- Default cloud posture: public evidence and LLM layers disabled by the packaged entrypoint.
- Token header: `X-Junas-Local-Token`.

The local daemon is an offline local fallback and adapter bridge. It is not endpoint DLP, EDR, MDM, browser policy, or enterprise enforcement.

## Local Pairing

Pairing is a three-step flow:

1. Client calls `POST /local/pairing/start` with its display name.
2. Desktop or tray process calls `POST /local/pairing/approve` with the pairing id, code, and daemon secret.
3. Client calls `POST /local/pairing/claim` and receives a signed local client token.

Current TTLs:

- Pairing request TTL: 300 seconds.
- Signed local client token TTL: 90 days.

`GET /local/pairing/status` reports ACL state, allowed origins, socket path, socket enabled state, pending pairing count, and token provisioning errors. It never returns the daemon token.

## Token Storage

Daemon secret resolution order:

1. `JUNAS_LOCAL_DAEMON_TOKEN`.
2. macOS Keychain generic password with service `junas-local-daemon-token` and account `default`.
3. Token file from `JUNAS_LOCAL_DAEMON_TOKEN_FILE`, or `~/.junas/local_daemon_token`.

Token files must be mode `0600`; group/world-readable token files fail. Same-user local processes may still read same-user files, environment variables, browser storage, or process memory depending on OS permissions and local compromise level. Treat the local token as a same-user secret, not as a host-wide trust boundary.

## Origin Rules

When local ACL is enabled:

- Browser-origin requests must have an `Origin` that matches `JUNAS_LOCAL_DAEMON_ALLOWED_ORIGINS`.
- Protected requests must include `X-Junas-Local-Token`.
- `OPTIONS` preflight requests are origin-checked but do not require the local token.
- Requests without an `Origin` are allowed for CLI/native clients; do not treat absent `Origin` as browser approval.

Default allowed origins:

- `chrome-extension://*`
- `https://chatgpt.com`
- `https://claude.ai`
- `https://gemini.google.com`

Protected paths are `/review`, `/classify`, `/classify/batch`, `/pseudonymize`, `/anonymize`, `/redact`, `/redact-pii`, `/safe-rewrite`, `/hold-until-public`, `/cite-public-source`, `/request-approval`, `/reidentify`, `/documents/scrub`, and `/review/*`.

## Unix Socket Option

Use `JUNAS_LOCAL_SOCKET_PATH=/tmp/junas-local.sock` to run Uvicorn on a Unix-domain socket instead of TCP loopback when the client supports Unix sockets. Socket deployments should set filesystem ownership and mode so only the intended local user or service account can connect.

Browser extensions cannot call Unix-domain sockets directly. They need loopback HTTP or a native host bridge.

## Loopback Risks

Loopback limits network reachability but still accepts connections from local processes. Risk cases:

- Another process running as the same user can attempt local requests.
- A malicious browser page can attempt loopback requests; origin allowlist plus `X-Junas-Local-Token` is the browser boundary.
- Local malware or remote-control software may read tokens, browser storage, keychain prompts, or clipboard contents.
- Firewall, DNS, proxy, or browser behavior can differ across managed desktops.

For production pilots, prefer tenant-authenticated server mode or a managed adapter where policy and telemetry are centrally controlled. Use local daemon mode for offline fallback, demos, and power users who explicitly opt in.

## Uninstall

LaunchAgent uninstall:

```sh
packaging/macos/uninstall.sh
```

That script unloads `~/Library/LaunchAgents/com.junas.local.plist` and removes the installed bundle under `${JUNAS_INSTALL_DIR:-$HOME/Applications/junas-local}`. It does not delete local tokens or logs.

Manual cleanup when decommissioning a user profile:

```sh
security delete-generic-password -a default -s junas-local-daemon-token 2>/dev/null || true
rm -f ~/.junas/local_daemon_token
rm -f /tmp/junas-local.sock
rm -rf ~/Library/Logs/Junas
```

Only remove logs after applying the operator's retention, legal-hold, and support policy.
