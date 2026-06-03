# Opt-In Local LLM Detector

This prototype classifies ambiguous low-confidence OCR text with a local model. It is disabled by default and does not change the default install footprint.

The current provider path is Ollama on localhost. The default model name is `phi3:mini`, but any locally installed Ollama model can be configured.

## Enable

Install and start Ollama separately, then pull a small local model:

```console
$ ollama pull phi3:mini
```

Enable the classifier in `~/.config/ascii-privacy/config.toml`:

```toml
[detection]
local_llm_enabled = true
local_llm_provider = "ollama"
local_llm_endpoint = "http://127.0.0.1:11434/api/generate"
local_llm_model = "phi3:mini"
local_llm_min_confidence = 20
local_llm_max_regions_per_frame = 2
local_llm_timeout_ms = 750
```

When disabled, `Aki` does not start Ollama, download a model, or call any model endpoint.

## How It Runs

The normal regex detector still handles OCR text at or above `detection.min_confidence`.

When the local classifier is enabled, OCR keeps lower-confidence words down to `local_llm_min_confidence`. Only regions below the normal threshold are sent to the local classifier. If the model returns `SECRET`, the region is treated as a medium-severity `local-llm-secret-shape` match and goes through the normal region expansion and transform pipeline.

The prompt asks for exactly `SECRET` or `SAFE`. Classifications that return anything else are ignored and logged.

## Local-Only Boundary

The prototype is local-only by configuration: it calls the configured endpoint, which should be a localhost Ollama server. Do not point `local_llm_endpoint` at a hosted model API unless you are intentionally changing that privacy boundary.

Only OCR text snippets are sent to the local endpoint, not frame pixels.

## Accuracy And Latency Tradeoffs

This detector is useful for text that OCR can see but regex rules do not confidently match. It is not a replacement for rule packs.

| Tradeoff | Impact |
|----------|--------|
| Recall | Can catch secret-shaped low-confidence text that regex scanning would otherwise skip. |
| Precision | May mark random high-entropy strings as secrets, so matches use medium severity. |
| Latency | Each local model call can add tens to hundreds of milliseconds, depending on model size and hardware. |
| Throughput | `local_llm_max_regions_per_frame` caps work per frame; keep it low for live capture. |
| Determinism | Small local models can still answer inconsistently, so non-`SECRET`/`SAFE` output is ignored. |

Recommended defaults for live capture are a small model, a short timeout, and one or two low-confidence regions per frame. For offline redaction, higher limits are safer because latency is less visible.
