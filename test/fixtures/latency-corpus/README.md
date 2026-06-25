# Latency Corpus

Place benchmark `.txt` inputs in this folder.

Recommended naming:

- `1000_words.txt`
- `2000_words.txt`
- `5000_words.txt`
- `10000_words.txt`

The benchmark wrapper script targets this folder by default:

```sh
./scripts/benchmark_latency_corpus.sh
```

Item 56's opt-in p95 SLO gate uses `1k.txt` as the default <= 10 KB extracted-text
fixture and runs `/review` plus `/anonymize` for strict and audit-grade profiles:

```sh
python3 scripts/check_latency_slo.py
KAYPOH_RUN_LATENCY_SLO=1 PYTHONPATH=src python3 -m pytest test/benchmarks -q
```

You can also drop any additional `.txt` files here and they will be included automatically.
