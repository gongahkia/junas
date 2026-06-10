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
| default legal corpus | 147 | `test/fixtures/legal-corpus/recall.lock.json` | Hand-labelled SG/legal-contract seed corpus. |
| adversarial corpus | 134 | `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` | Negative, obfuscated, and multilingual probes. |
| SEA jurisdiction corpus | 5 | `test/fixtures/legal-corpus-sea/legal-corpus-sea.lock.json` | Seed local-ID fixtures for MY, ID, TH, PH, and VN. |
| HK/AU/JP/KR jurisdiction corpus | 4 | `test/fixtures/legal-corpus-hk-au-jp-kr/legal-corpus-hk-au-jp-kr.lock.json` | Seed local-ID fixtures for HK, AU, JP, and KR. |
| reviewed candidate corpus | 1428 | `test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json` | Human-approved candidate fixtures promoted into recall-lock form. |

## Per-Detector Baselines

| Corpus | Fixtures | Detector | Recall | Precision |
|---|---:|---|---:|---:|
| default legal corpus | 147 | `advertising_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `age_reference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `au_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `bank_customer_reference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `biometric_identifier` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `consent_withdrawal_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `contract_discount_rate` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `contract_unit_price` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `cookie_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `cross_border_transfer_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `crypto_wallet_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `cyber_incident_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `data_minimisation_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `date_of_birth` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `definitive_agreement` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `device_serial_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `dpt_pre_listing_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `email_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `embargo_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `employee_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `esg_climate_pre_disclosure` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `esg_target_revision` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `eu_company_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `eu_national_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `eu_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `financial_amount` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `financial_percentage` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `genetic_data` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `health_condition` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `information_barrier_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `insider_list_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `insurance_member_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `internal_session_id` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `large_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `material_adverse_change` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `medical_record_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `medical_treatment` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `named_person` | 0.9773 | 1.0000 |
| default legal corpus | 147 | `nonpublic_marker` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `passport_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `personal_attribute_inference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `phone_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `political_opinion` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `racial_ethnic_origin` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `religious_belief` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `royalty_rate` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sex_life_reference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sexual_orientation` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_acra_transaction_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_hdb_reference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_insurance_policy_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_ipos_tm_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_nric_fin` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_sla_lot_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_tribunal_reference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_uen` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `sg_ura_planning_reference` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `total_contract_value` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `trade_union_membership` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `transaction_codename` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `uk_company_number` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `uk_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `us_postal_address` | 1.0000 | 1.0000 |
| default legal corpus | 147 | `volume_commitment` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `bank_account` | 0.0000 | not locked |
| adversarial corpus | 134 | `bank_customer_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `biometric_identifier` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `customer_account_number` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `definitive_agreement` | 0.9474 | 1.0000 |
| adversarial corpus | 134 | `email_address` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `embargo_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `employee_id` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `financial_amount` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `financial_percentage` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `genetic_data` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `health_condition` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `insurance_member_id` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `internal_session_id` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `large_number` | 0.8182 | 1.0000 |
| adversarial corpus | 134 | `material_event` | 0.0000 | not locked |
| adversarial corpus | 134 | `medical_record_number` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `medical_treatment` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `named_person` | 0.9778 | 1.0000 |
| adversarial corpus | 134 | `nonpublic_marker` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `personal_attribute_inference` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `phone_number` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `racial_ethnic_origin` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `sex_life_reference` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `sexual_orientation` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `sg_nric_fin` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `sg_postal_address` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `sg_uen` | 1.0000 | 1.0000 |
| adversarial corpus | 134 | `transaction_codename` | 0.9167 | 1.0000 |
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
| reviewed candidate corpus | 1428 | `ae_emirates_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `ae_passport` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `ae_trade_licence` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `age_reference` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `au_abn` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `au_acn` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `au_postal_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `au_tfn` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `bank_account` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `biometric_identifier` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `cn_passport` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `cn_phone` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `cn_resident_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `cn_uscc` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `conjunctive_mnpi` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `consent_withdrawal_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `contingent_mnpi_language` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `contract_discount_rate` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `contract_unit_price` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `cross_border_transfer_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `customer_account_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `cyber_incident_pre_disclosure` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `data_minimisation_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `date_of_birth` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `definitive_agreement` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `device_serial_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `dpt_pre_listing_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `email_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `embargo_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `employee_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `esg_climate_pre_disclosure` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `esg_target_revision` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `eu_company_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `eu_national_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `financial_amount` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `financial_percentage` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `genetic_data` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `health_condition` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `hk_cr_no` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `hk_hkid` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `id_nik` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `id_postal_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `imei` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `in_aadhaar` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `in_gstin` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `in_pan` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `information_barrier_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `insider_list_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `ip_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `jp_corporate_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `jp_my_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `jp_postal_code` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `kr_business_registration` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `kr_rrn` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `large_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `legal_proceeding_mnpi` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `material_adverse_change` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `material_event` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `medical_record_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `medical_treatment` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `minor_data_reference` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `my_mykad` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `my_postal_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `named_person` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `nonpublic_marker` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `passport_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `personal_attribute_inference` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `ph_philsys` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `ph_tin` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `phone_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `postal_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `quasi_identifier_combination` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `religious_belief` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sa_iqama` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sa_national_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `selective_disclosure_risk` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sexual_orientation` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sg_insurance_policy_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sg_nric_fin` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sg_postal_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sg_sgx_counter` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `sg_uen` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `th_national_id` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `tipping_language` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `trade_union_membership` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `transaction_codename` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `uk_company_number` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `uk_postal_address` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `us_ein` | 1.0000 | 1.0000 |
| reviewed candidate corpus | 1428 | `vn_cccd` | 1.0000 | 1.0000 |

## Known Limitations

- These are locked regression baselines over small, hand-labelled fixture corpora; they are not population-level accuracy claims.
- `not locked` means that corpus currently gates recall only for that detector.
- Public-evidence matching and LLM adjudication accuracy are not included in these deterministic detector locks.
- New detectors should not be represented as available until matching recall and precision locks are committed.
