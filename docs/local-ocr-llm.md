# Optional OCR-region classifier experiment

`junas.advisory.local_ocr_llm.LocalOcrRegionClassifier` classifies ambiguous OCR fragments as `secret_shaped`, `not_secret`, or `ambiguous`. It is a separate experiment, disabled by default, and does not change the main pipeline's findings.

```python
from junas.advisory.local_ocr_llm import LocalOcrRegionClassifier, settings_from_env

result = LocalOcrRegionClassifier(settings_from_env()).classify_text("AK1A0CRNO1SE", confidence=0.41)
```

Explicit activation requires `JUNAS_LOCAL_OCR_LLM_ENABLED=1` and `JUNAS_LOCAL_OCR_LLM_MODEL` with a locally installed Ollama model. The URL must be loopback. No model is bundled or downloaded. The prototype has no validated accuracy baseline; measure false positives and missed secrets before drawing conclusions.
