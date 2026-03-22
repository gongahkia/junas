# Layer 1 Lexicon

This folder contains deterministic lexicon and rule-based screening logic.

- `filter.py`: regex, restricted-list, spaCy, and Presidio checks
- `restricted_list.json`: entity list used by restricted-list rules
- `score_threshold_mode` can be `static` or `dynamic`; dynamic mode raises the effective lexicon score threshold as input text gets longer
