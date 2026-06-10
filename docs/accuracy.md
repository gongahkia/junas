# Kaypoh Detector Accuracy

This file is generated from committed recall and precision locks. Do not edit it by hand.

## Endpoint Data States

| Endpoint | Data state | Mapping retained | Accuracy caveat |
|---|---|---|---|
| `/pseudonymize` | Pseudonymised personal data | Yes | Detector baselines describe span detection before reversible replacement; output remains re-identifiable where the controller holds the mapping. |
| `/anonymize` | Placeholder-only anonymised text | No | Detector baselines do not prove statistical anonymisation; residual singling-out/linkability/inference risk remains document-context dependent. |
| `/redact` | Opaque redacted text | No | Detector baselines describe what was found for redaction; residual risk depends on unredacted context and container metadata handling. |

## Corpus Locks

| Corpus | Fixtures | Lock file | Description |
|---|---:|---|---|
| default legal corpus | 145 | `test/fixtures/legal-corpus/recall.lock.json` | Hand-labelled SG/legal-contract seed corpus. |
| adversarial corpus | 133 | `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` | Negative, obfuscated, and multilingual probes. |
| SEA jurisdiction corpus | 5 | `test/fixtures/legal-corpus-sea/legal-corpus-sea.lock.json` | Seed local-ID fixtures for MY, ID, TH, PH, and VN. |
| HK/AU/JP/KR jurisdiction corpus | 4 | `test/fixtures/legal-corpus-hk-au-jp-kr/legal-corpus-hk-au-jp-kr.lock.json` | Seed local-ID fixtures for HK, AU, JP, and KR. |

## Per-Detector Baselines

| Corpus | Fixtures | Detector | Recall | Precision |
|---|---:|---|---:|---:|
| default legal corpus | 145 | `advertising_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `age_reference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `au_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `bank_customer_reference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `biometric_identifier` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `consent_withdrawal_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `contract_discount_rate` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `contract_unit_price` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `cookie_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `cross_border_transfer_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `crypto_wallet_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `cyber_incident_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `data_minimisation_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `date_of_birth` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `definitive_agreement` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `device_serial_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `dpt_pre_listing_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `email_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `embargo_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `employee_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `esg_climate_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `esg_target_revision` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `eu_company_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `eu_national_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `eu_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `financial_amount` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `financial_percentage` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `genetic_data` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `health_condition` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `information_barrier_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `insider_list_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `insurance_member_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `internal_session_id` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `large_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `material_adverse_change` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `medical_record_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `medical_treatment` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `named_person` | 0.9773 | 1.0000 |
| default legal corpus | 145 | `nonpublic_marker` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `passport_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `personal_attribute_inference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `phone_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `political_opinion` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `racial_ethnic_origin` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `religious_belief` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `royalty_rate` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sex_life_reference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sexual_orientation` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_acra_transaction_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_hdb_reference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_insurance_policy_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_ipos_tm_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_nric_fin` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_sla_lot_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_tribunal_reference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_uen` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `sg_ura_planning_reference` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `total_contract_value` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `trade_union_membership` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `transaction_codename` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `uk_company_number` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `uk_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `us_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 145 | `volume_commitment` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `bank_account` | 0.0000 | not locked |
| adversarial corpus | 133 | `bank_customer_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `biometric_identifier` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `customer_account_number` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `definitive_agreement` | 0.9474 | 1.0000 |
| adversarial corpus | 133 | `email_address` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `embargo_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `employee_id` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `financial_amount` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `financial_percentage` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `genetic_data` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `health_condition` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `insurance_member_id` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `internal_session_id` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `large_number` | 0.8182 | 1.0000 |
| adversarial corpus | 133 | `material_event` | 0.0000 | not locked |
| adversarial corpus | 133 | `medical_record_number` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `medical_treatment` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `named_person` | 0.9778 | 1.0000 |
| adversarial corpus | 133 | `nonpublic_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `personal_attribute_inference` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `phone_number` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `racial_ethnic_origin` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `sex_life_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `sexual_orientation` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `sg_nric_fin` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `sg_postal_address` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `sg_uen` | 1.0000 | 1.0000 |
| adversarial corpus | 133 | `transaction_codename` | 0.9167 | 1.0000 |
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
