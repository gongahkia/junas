"""Reproducible dataset builders for SGLB-NN tasks.

Builders read source material (the kevanwee scraper outputs or hand-curated
seed pools) and emit YAML dataset files for the harness. Each builder is
deterministic given a seed, so dataset versions are reproducible.
"""
