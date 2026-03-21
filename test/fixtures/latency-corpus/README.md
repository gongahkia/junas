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

You can also drop any additional `.txt` files here and they will be included automatically.
