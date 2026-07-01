# Uninstall And Rollback

Rollback and uninstall are operational changes, not data-deletion shortcuts. Keep
journals, mappings, audit packs, SIEM exports, logs, backups, and subject-erasure
tombstones under the retention and legal-hold policy before deleting any state.

## Common Rules

- Capture component version, artifact hash, config version, policy id/version, tenant or
  pilot group, and rollback owner before rollout.
- Roll back adapters and backend separately. A browser or Office adapter rollback should
  not delete backend journals.
- Revoke or rotate credentials that were embedded in an adapter, local token file,
  static hosting secret, or deployment Secret.
- After rollback, verify `/ready`, one benign `/review`, one blocked fixture, and
  adapter health for the remaining active surface.
- Do not delete `JUNAS_JOURNAL_DIR`, PVCs, SIEM indexes, audit packs, mapping stores, or
  subject indexes until retention/legal-hold disposition is complete.

## Server Backend

Docker stop without deleting volumes:

```sh
docker compose -f docker-compose.production.example.yml down
```

Docker rollback:

1. Restore the previous image tag, policy config, retention manifest, and secret version
   references in the compose file or environment.
2. Run `scripts/preflight.py --deployment production --strict`.
3. Start the prior version and check readiness:

```sh
docker compose -f docker-compose.production.example.yml up -d
curl -fsS http://localhost:8000/ready
```

Kubernetes rollback:

```sh
kubectl -n junas rollout undo deployment/junas
kubectl -n junas rollout status deployment/junas
kubectl -n junas get pods -l app=junas
```

Kubernetes stop without deleting state:

```sh
kubectl -n junas scale deployment/junas --replicas=0
```

Only delete `junas-journal` PVCs, `junas-secrets`, retention ConfigMaps, or backup
objects after the retention owner approves disposition. If policy config rollback is the
only needed change, publish the previous policy version and restart or reload the
backend according to the deployment mode; do not roll back adapter assignments.

## Local Daemon

Packaged macOS uninstall:

```sh
packaging/macos/uninstall.sh
```

The script unloads `~/Library/LaunchAgents/com.junas.local.plist` and removes the
installed bundle under `${JUNAS_INSTALL_DIR:-$HOME/Applications/junas-local}`. It does
not delete local tokens, sockets, or logs.

Optional profile cleanup after retention/support review:

```sh
security delete-generic-password -a default -s junas-local-daemon-token 2>/dev/null || true
rm -f ~/.junas/local_daemon_token
rm -f /tmp/junas-local.sock
rm -rf ~/Library/Logs/Junas
```

Local daemon rollback:

1. Restore the previous `dist/junas-local/` bundle.
2. Run `packaging/macos/update.sh` or reinstall with `packaging/macos/install.sh`.
3. Verify `curl http://127.0.0.1:8765/ready`.
4. Re-pair browser, Word, Outlook taskpane, or desktop watcher clients if local tokens
   were rotated.

## Outlook Add-In

Rollback:

1. Restore the previous rendered manifest or manifest URL for
   `dist/outlook-addin/{profile}/manifest.xml`.
2. Restore the previous HTTPS static origin contents for `taskpane.html`,
   `commands.html`, `launchevent.js`, and `taskpane.js`.
3. Update Microsoft 365 admin-managed deployment assignment to the prior manifest, or
   remove the pilot group assignment.
4. Ask pilot users to restart Outlook and repeat the Smart Alerts QA cases from
   `docs/integrations/outlook.md`.

Uninstall:

- Remove the Outlook add-in assignment from the pilot group or tenant.
- Revoke hosted-server bearer tokens or local pairing tokens used by the add-in.
- Keep the hosted static files until clients no longer request the old manifest.
- Confirm send attempts no longer invoke `OnMessageSend` for assigned users.

Do not remove backend journals or approval records when uninstalling the add-in; those
records remain backend audit evidence.

## Browser Extension

Rollback:

1. Publish or force-install the prior Chrome Web Store, Edge Add-ons, or self-hosted CRX
   version.
2. If enterprise policy is used, update `ExtensionSettings` to the prior extension id,
   update URL, installation mode, and runtime host allowlist.
3. Restore the prior hosted-server origin permission if the rollback changes backend
   mode.
4. Re-test connection health, prompt-submit review, warn confirmation, block behavior,
   and storage/log privacy.

Uninstall:

- Remove force-install policy or set the extension to blocked/removed according to the
  browser management system.
- Ask unmanaged users to remove the extension from Chrome or Edge extension settings.
- Revoke bearer tokens and local pairing tokens; rotate backend API keys if they were
  distributed through extension policy.
- Do not treat extension removal as deletion of backend telemetry, SIEM, or journal
  records.

## Word Add-In

Rollback:

1. Restore the prior Word manifest and HTTPS taskpane assets.
2. Reapply the previous Microsoft 365 admin-managed deployment assignment or controlled
   sideload package.
3. Verify the taskpane opens, can read selected text under `ReadDocument`, and calls the
   intended backend or local daemon endpoint.

Uninstall:

- Remove the Word add-in assignment or sideloaded manifest.
- Remove hosted taskpane assets only after assigned clients stop requesting them.
- Revoke tokens used by the taskpane.
- Tell users that Word review UI removal does not affect Outlook, browser, DMS, direct
  API, or backend policy enforcement.

## Rollback Evidence

Record these fields in the incident, change, or release ticket:

| Field | Required evidence |
|---|---|
| Component | server backend, local daemon, Outlook add-in, browser extension, or Word add-in |
| Prior version | image tag, package hash, manifest hash, extension version, or static asset revision |
| Scope | tenant, pilot group, local machine, browser policy OU, or Microsoft 365 assignment |
| Data disposition | journal/mapping/SIEM/audit-pack retention decision |
| Credential action | revoked, rotated, unchanged with reason |
| Verification | `/ready`, `/review`, adapter health, and user-visible result after rollback |
