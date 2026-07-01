# Singling-Out Pack Evaluation

This document records the current widening decision for strict `singling_out_v2`.

Source report: `reports/current/singling_out_pack_eval_20260701.json`.

Decision: deepen SG/US/UK before widening quasi-ID coverage in thin packs.

Rationale: SG, US, and UK currently have the densest recognizer and frequency-table
support for relational singling-out. Thin packs should stay on the deterministic
identifying-weight fallback until SG/US/UK show stable TAB QUASI/coreference
behavior and candidate-corpus `singling_out_miss` reduction.
