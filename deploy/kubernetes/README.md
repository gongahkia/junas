# Kubernetes Reference Manifests

These manifests are a production-oriented reference, not a drop-in managed service. Replace image names, hosts, secret values, storage class, resource limits, and ingress annotations for the target cluster.

Apply order:

```sh
kubectl apply -f deploy/kubernetes/namespace.yaml
kubectl apply -f deploy/kubernetes/secret.example.yaml
kubectl apply -f deploy/kubernetes/configmap.yaml
kubectl apply -f deploy/kubernetes/pvc.yaml
kubectl apply -f deploy/kubernetes/deployment.yaml
kubectl apply -f deploy/kubernetes/service.yaml
kubectl apply -f deploy/kubernetes/ingress.example.yaml
```

Production requirements preserved here:

- tenant auth is enabled
- policy config and retention manifest are mounted read-only
- journal keys, mapping-store key, subject-index key, and tenant credentials come from a Secret
- review journal state is written to a PVC
- startup runs `scripts/preflight.py --deployment production --strict`
- Uvicorn access logs are disabled with `--no-access-log`
- readiness parses `/ready` JSON and requires `ready=true`

Keep TLS, WAF, body-size limits, request-body logging policy, backup, and network policy under the customer cluster baseline.
