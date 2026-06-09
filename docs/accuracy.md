# Kaypoh Detector Accuracy

This file is generated from committed recall and precision locks. Do not edit it by hand.

## Corpus Locks

| Corpus | Fixtures | Lock file | Description |
|---|---:|---|---|
| default legal corpus | 141 | `test/fixtures/legal-corpus/recall.lock.json` | Hand-labelled SG/legal-contract seed corpus. |
| adversarial corpus | 130 | `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` | Negative, obfuscated, and multilingual probes. |
| SEA jurisdiction corpus | 5 | `test/fixtures/legal-corpus-sea/legal-corpus-sea.lock.json` | Seed local-ID fixtures for MY, ID, TH, PH, and VN. |
| HK/AU/JP/KR jurisdiction corpus | 4 | `test/fixtures/legal-corpus-hk-au-jp-kr/legal-corpus-hk-au-jp-kr.lock.json` | Seed local-ID fixtures for HK, AU, JP, and KR. |

## Per-Detector Baselines

| Corpus | Fixtures | Detector | Recall | Precision |
|---|---:|---|---:|---:|
| default legal corpus | 141 | `advertising_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `age_reference` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `au_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `bank_customer_reference` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `biometric_identifier` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `consent_withdrawal_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `contract_discount_rate` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `contract_unit_price` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `cookie_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `cross_border_transfer_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `crypto_wallet_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `cyber_incident_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `data_minimisation_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `date_of_birth` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `definitive_agreement` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `device_serial_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `dpt_pre_listing_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `email_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `embargo_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `employee_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `esg_climate_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `esg_target_revision` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `eu_company_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `eu_national_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `eu_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `financial_amount` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `financial_percentage` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `genetic_data` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `health_condition` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `information_barrier_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `insider_list_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `insurance_member_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `internal_session_id` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `large_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `material_adverse_change` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `medical_record_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `medical_treatment` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `named_person` | 0.9773 | 1.0000 |
| default legal corpus | 141 | `nonpublic_marker` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `passport_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `personal_attribute_inference` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `phone_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `political_opinion` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `racial_ethnic_origin` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `religious_belief` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `royalty_rate` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sex_life_reference` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sexual_orientation` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sg_insurance_policy_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sg_nric_fin` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sg_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sg_tribunal_reference` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `sg_uen` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `total_contract_value` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `trade_union_membership` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `transaction_codename` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `uk_company_number` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `uk_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `us_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 141 | `volume_commitment` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `bank_account` | 0.0000 | not locked |
| adversarial corpus | 130 | `bank_customer_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `biometric_identifier` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `customer_account_number` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `definitive_agreement` | 0.9474 | 1.0000 |
| adversarial corpus | 130 | `email_address` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `embargo_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `employee_id` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `financial_amount` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `financial_percentage` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `genetic_data` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `health_condition` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `insurance_member_id` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `internal_session_id` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `large_number` | 0.8182 | 1.0000 |
| adversarial corpus | 130 | `material_event` | 0.0000 | not locked |
| adversarial corpus | 130 | `medical_record_number` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `medical_treatment` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `named_person` | 0.9778 | 1.0000 |
| adversarial corpus | 130 | `nonpublic_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `phone_number` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `racial_ethnic_origin` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `sex_life_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `sexual_orientation` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `sg_nric_fin` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `sg_postal_address` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `sg_uen` | 1.0000 | 1.0000 |
| adversarial corpus | 130 | `transaction_codename` | 0.9167 | 1.0000 |
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
