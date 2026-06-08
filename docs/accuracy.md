# Kaypoh Detector Accuracy

This file is generated from committed recall and precision locks. Do not edit it by hand.

## Corpus Locks

| Corpus | Fixtures | Lock file | Description |
|---|---:|---|---|
| default legal corpus | 133 | `test/fixtures/legal-corpus/recall.lock.json` | Hand-labelled SG/legal-contract seed corpus. |
| adversarial corpus | 124 | `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` | Negative, obfuscated, and multilingual probes. |
| SEA jurisdiction corpus | 5 | `test/fixtures/legal-corpus-sea/legal-corpus-sea.lock.json` | Seed local-ID fixtures for MY, ID, TH, PH, and VN. |
| HK/AU/JP/KR jurisdiction corpus | 4 | `test/fixtures/legal-corpus-hk-au-jp-kr/legal-corpus-hk-au-jp-kr.lock.json` | Seed local-ID fixtures for HK, AU, JP, and KR. |

## Per-Detector Baselines

| Corpus | Fixtures | Detector | Recall | Precision |
|---|---:|---|---:|---:|
| default legal corpus | 133 | `advertising_id` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `age_reference` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `bank_customer_reference` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `biometric_identifier` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `consent_withdrawal_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `contract_discount_rate` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `contract_unit_price` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `cookie_id` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `cross_border_transfer_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `crypto_wallet_address` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `cyber_incident_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `data_minimisation_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `date_of_birth` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `definitive_agreement` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `device_serial_number` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `dpt_pre_listing_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `email_address` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `embargo_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `employee_id` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `esg_climate_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `esg_target_revision` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `eu_national_id` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `financial_amount` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `financial_percentage` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `genetic_data` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `health_condition` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `information_barrier_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `insider_list_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `insurance_member_id` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `internal_session_id` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `large_number` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `material_adverse_change` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `medical_record_number` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `medical_treatment` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `named_person` | 0.9768 | 1.0000 |
| default legal corpus | 133 | `nonpublic_marker` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `passport_number` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `phone_number` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `royalty_rate` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sex_life_reference` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sexual_orientation` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sg_insurance_policy_number` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sg_nric_fin` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sg_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sg_tribunal_reference` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `sg_uen` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `total_contract_value` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `transaction_codename` | 1.0000 | 1.0000 |
| default legal corpus | 133 | `volume_commitment` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `bank_account` | 0.0000 | not locked |
| adversarial corpus | 124 | `bank_customer_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `biometric_identifier` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `customer_account_number` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `definitive_agreement` | 0.9474 | 1.0000 |
| adversarial corpus | 124 | `email_address` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `embargo_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `employee_id` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `financial_amount` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `financial_percentage` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `genetic_data` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `health_condition` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `insurance_member_id` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `internal_session_id` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `large_number` | 0.8182 | 1.0000 |
| adversarial corpus | 124 | `material_event` | 0.0000 | not locked |
| adversarial corpus | 124 | `medical_record_number` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `medical_treatment` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `named_person` | 0.9778 | 1.0000 |
| adversarial corpus | 124 | `nonpublic_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `phone_number` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `sex_life_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `sexual_orientation` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `sg_nric_fin` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `sg_postal_address` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `sg_uen` | 1.0000 | 1.0000 |
| adversarial corpus | 124 | `transaction_codename` | 0.9167 | 1.0000 |
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
