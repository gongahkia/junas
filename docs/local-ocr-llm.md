# Opt-In Local OCR LLM Prototype

Junas includes a prototype classifier for low-confidence OCR regions that may be
secret-shaped. It is disabled by default, uses no new package dependency, and
only calls a loopback Ollama endpoint when explicitly enabled.

This is advisory prototype work. It does not change strict review, policy
blocking, redaction, or default install behavior.

## Run Locally

Install and run a local model in Ollama, then call one OCR fragment:

```sh
JUNAS_LOCAL_OCR_LLM_ENABLED=1 \
JUNAS_LOCAL_OCR_LLM_MODEL=<local-ollama-model> \
uv run aki ocr classify-region \
  --text "AK1A0CRNO1SE" \
  --confidence 0.41 \
  --json
```

Equivalent explicit flags:

```sh
uv run aki ocr classify-region \
  --enable-local-llm \
  --provider ollama \
  --base-url http://127.0.0.1:11434 \
  --model <local-ollama-model> \
  --text "ghp_0crN0ise" \
  --confidence 0.38
```

The command refuses non-loopback base URLs. The result contains a SHA-256 hash of
the fragment, not the raw fragment text.

## Config

| Variable | Default | Meaning |
|---|---|---|
| `JUNAS_LOCAL_OCR_LLM_ENABLED` | unset/false | Required opt-in gate. |
| `JUNAS_LOCAL_OCR_LLM_PROVIDER` | `ollama` | Prototype provider. |
| `JUNAS_LOCAL_OCR_LLM_BASE_URL` | `http://127.0.0.1:11434` | Must be loopback. |
| `JUNAS_LOCAL_OCR_LLM_MODEL` | unset | Operator-selected local Ollama model. |
| `JUNAS_LOCAL_OCR_LLM_CONFIDENCE_THRESHOLD` | `0.72` | Classify only regions at or below this OCR confidence. |
| `JUNAS_LOCAL_OCR_LLM_TIMEOUT_SECONDS` | `8.0` | Local model call timeout. |
| `JUNAS_LOCAL_OCR_LLM_MAX_CHARS` | `160` | Max fragment chars sent to local model. |

## Candidate Model Paths

The prototype currently uses Ollama's loopback HTTP API without adding Python
dependencies. Operators can test any locally installed small instruction model,
including Phi-family or Llama-family models, provided the model stays on the
same machine.

No model is bundled, downloaded, or installed by Junas.

## Accuracy And Latency Tradeoffs

| Path | Expected strength | Known tradeoff |
|---|---|---|
| Deterministic regexes | Fast, repeatable, fixture-locked. | Misses OCR-corrupted token shapes that no longer match regex. |
| Local OCR LLM prototype | Tests ambiguous low-confidence fragments with OCR noise. | Model-dependent false positives/negatives; no promoted accuracy lock. |
| Remote LLM helpers | Existing audit-grade advisory path for broader reasoning. | Requires tenant/provider gates and is not local-only. |

Latency is dominated by local model size, quantization, hardware, and whether the
model is already loaded. Treat results as reviewer-facing hints until a committed
eval report and promotion gate exist.

## Safety Boundary

- off by default
- loopback-only base URL
- no added default dependencies
- no remote provider support
- no high-severity finding creation
- no deterministic finding suppression
- no README "AI-powered" positioning
