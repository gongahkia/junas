# Kaypoh Detector Accuracy

This file is generated from committed recall and precision locks. Do not edit it by hand.

## Corpus Locks

| Corpus | Fixtures | Lock file | Description |
|---|---:|---|---|
| default legal corpus | 6 | `test/fixtures/legal-corpus/recall.lock.json` | Hand-labelled SG/legal-contract seed corpus. |
| adversarial corpus | 3 | `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` | Negative, obfuscated, and multilingual probes. |
| SEA jurisdiction corpus | 5 | `test/fixtures/legal-corpus-sea/legal-corpus-sea.lock.json` | Seed local-ID fixtures for MY, ID, TH, PH, and VN. |

## Per-Detector Baselines

| Corpus | Fixtures | Detector | Recall | Precision |
|---|---:|---|---:|---:|
| default legal corpus | 6 | `definitive_agreement` | 1.0000 | not locked |
| default legal corpus | 6 | `email_address` | 1.0000 | not locked |
| default legal corpus | 6 | `embargo_marker` | 1.0000 | not locked |
| default legal corpus | 6 | `financial_amount` | 1.0000 | not locked |
| default legal corpus | 6 | `financial_percentage` | 1.0000 | not locked |
| default legal corpus | 6 | `material_adverse_change` | 1.0000 | not locked |
| default legal corpus | 6 | `named_person` | 1.0000 | not locked |
| default legal corpus | 6 | `passport_number` | 1.0000 | not locked |
| default legal corpus | 6 | `phone_number` | 1.0000 | not locked |
| default legal corpus | 6 | `sg_nric_fin` | 1.0000 | not locked |
| default legal corpus | 6 | `sg_postal_address` | 1.0000 | not locked |
| default legal corpus | 6 | `sg_uen` | 1.0000 | not locked |
| default legal corpus | 6 | `transaction_codename` | 1.0000 | not locked |
| adversarial corpus | 3 | `definitive_agreement` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `email_address` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `embargo_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `financial_amount` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `named_person` | 0.6667 | 1.0000 |
| adversarial corpus | 3 | `phone_number` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `sg_nric_fin` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `sg_uen` | 1.0000 | 1.0000 |
| adversarial corpus | 3 | `transaction_codename` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `email_address` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `embargo_marker` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `financial_percentage` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `id_nik` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `my_mykad` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `named_person` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `ph_philsys` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `ph_tin` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `th_national_id` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `transaction_codename` | 1.0000 | 1.0000 |
| SEA jurisdiction corpus | 5 | `vn_cccd` | 1.0000 | 1.0000 |

## Known Limitations

- These are locked regression baselines over small, hand-labelled fixture corpora; they are not population-level accuracy claims.
- `not locked` means that corpus currently gates recall only for that detector.
- Public-evidence matching and LLM adjudication accuracy are not included in these deterministic detector locks.
- New detectors should not be represented as available until matching recall and precision locks are committed.
