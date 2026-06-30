---
title: Junas Deterministic Demo
sdk: docker
app_port: 8000
suggested_hardware: cpu-basic
---

# Junas Deterministic Demo

This Space runs the Junas public demo profile:

- strict deterministic review only;
- no public-evidence retrieval;
- no LLM adjudication or helper layers;
- no provider keys or secrets;
- no review persistence.

Free CPU Basic Spaces can sleep after inactivity. The first request after sleep
may take longer while the container wakes.
