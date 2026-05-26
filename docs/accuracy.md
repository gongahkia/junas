# Kaypoh Detector Accuracy

This file is generated from committed recall and precision locks. Do not edit it by hand.

## Corpus Locks

| Corpus | Fixtures | Lock file | Description |
|---|---:|---|---|
| default legal corpus | 118 | `test/fixtures/legal-corpus/recall.lock.json` | Hand-labelled SG/legal-contract seed corpus. |
| adversarial corpus | 115 | `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` | Negative, obfuscated, and multilingual probes. |
| SEA jurisdiction corpus | 5 | `test/fixtures/legal-corpus-sea/legal-corpus-sea.lock.json` | Seed local-ID fixtures for MY, ID, TH, PH, and VN. |
| HK/AU/JP/KR jurisdiction corpus | 4 | `test/fixtures/legal-corpus-hk-au-jp-kr/legal-corpus-hk-au-jp-kr.lock.json` | Seed local-ID fixtures for HK, AU, JP, and KR. |

## Per-Detector Baselines

| Corpus | Fixtures | Detector | Recall | Precision |
|---|---:|---|---:|---:|
| default legal corpus | 118 | `definitive_agreement` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `email_address` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `embargo_marker` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `financial_amount` | 0.9512 | 1.0000 |
| default legal corpus | 118 | `financial_percentage` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `large_number` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `material_adverse_change` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `named_person` | 0.9766 | 1.0000 |
| default legal corpus | 118 | `nonpublic_marker` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `passport_number` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `phone_number` | 0.9883 | 1.0000 |
| default legal corpus | 118 | `sg_nric_fin` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `sg_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `sg_uen` | 1.0000 | 1.0000 |
| default legal corpus | 118 | `transaction_codename` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `bank_account` | 0.0000 | not locked |
| adversarial corpus | 115 | `definitive_agreement` | 0.9474 | 1.0000 |
| adversarial corpus | 115 | `email_address` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `embargo_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `financial_amount` | 0.9910 | 1.0000 |
| adversarial corpus | 115 | `financial_percentage` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `large_number` | 0.8182 | 1.0000 |
| adversarial corpus | 115 | `material_event` | 0.0000 | not locked |
| adversarial corpus | 115 | `named_person` | 0.9777 | 1.0000 |
| adversarial corpus | 115 | `nonpublic_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `phone_number` | 0.9529 | 1.0000 |
| adversarial corpus | 115 | `sg_nric_fin` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `sg_postal_address` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `sg_uen` | 1.0000 | 1.0000 |
| adversarial corpus | 115 | `transaction_codename` | 0.9091 | 1.0000 |
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
| HK/AU/JP/KR jurisdiction corpus | 4 | `au_abn` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `au_acn` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `au_tfn` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `definitive_agreement` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `email_address` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `embargo_marker` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `financial_amount` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `hk_cr_no` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `hk_hkid` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `jp_corporate_number` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `jp_my_number` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `kr_business_registration` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `kr_rrn` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `named_person` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `nonpublic_marker` | 1.0000 | 1.0000 |
| HK/AU/JP/KR jurisdiction corpus | 4 | `transaction_codename` | 1.0000 | 1.0000 |

## Known Limitations

- These are locked regression baselines over small, hand-labelled fixture corpora; they are not population-level accuracy claims.
- `not locked` means that corpus currently gates recall only for that detector.
- Public-evidence matching and LLM adjudication accuracy are not included in these deterministic detector locks.
- New detectors should not be represented as available until matching recall and precision locks are committed.
