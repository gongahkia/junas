# Reverse Proxy Examples

`nginx-junas.conf` is a hardened starting point for a production Junas backend behind TLS.

It includes:

- TLS listener and certificate placeholders
- `client_max_body_size 25m`
- upstream connect/read/send timeouts
- explicit route allowlist for backend API paths
- monitoring-only access for `/metrics` and `/diagnostics`
- no-body access log format; do not add `$request_body`, request headers, auth headers, or response bodies
- default `404` for unknown routes and local-daemon pairing routes

Replace hostnames, certificate paths, CIDR ranges, upstream address, and logging paths for the deployment.
