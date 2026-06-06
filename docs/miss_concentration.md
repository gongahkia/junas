# Miss Concentration

This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.
Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.

## Summary

- Review profile: strict
- Miss count: 23138
- Buckets: coverage_gap: 17393, conjunction_miss: 5026, singling_out_miss: 526, needs_review: 163, true_inference_miss: 30
- Detector families: mnpi_context: 5027, direct_identifier: 4932, mnpi_lexicon: 4437, privacy_event: 3896, pseudonymised_linkable: 1183, sector_mnpi: 1116, special_category: 1069, online_device: 789, quasi_identifier: 526, unknown: 163
- Jurisdictions by raw misses: IN: 1825, CN: 1622, EU: 1520, SA: 1432, KR: 1419, JP: 1357, MY: 1323, ID: 1312, PH: 1310, US: 1304
- Jurisdictions by misses per 100 docs: IN: 2172.62 per 100 docs (1825 raw), CN: 1930.95 per 100 docs (1622 raw), EU: 1809.52 per 100 docs (1520 raw), SA: 1704.76 per 100 docs (1432 raw), KR: 1689.29 per 100 docs (1419 raw), JP: 1615.48 per 100 docs (1357 raw), MY: 1575.0 per 100 docs (1323 raw), ID: 1561.9 per 100 docs (1312 raw), PH: 1559.52 per 100 docs (1310 raw), US: 1552.38 per 100 docs (1304 raw)

## Top Cells

| Detector family | Jurisdiction | Bucket | Misses | Docs | Misses / 100 docs | Top rules | Example |
|---|---|---|---:|---:|---:|---|---|
| direct_identifier | IN | coverage_gap | 462 | 84 | 550.0 | email_address: 130, in_pan: 90, in_aadhaar: 72, in_gstin: 70 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_adversarial_001.txt: `1234 5678 9012` |
| privacy_event | CN | coverage_gap | 459 | 84 | 546.43 | cross_border_transfer_marker: 210, data_minimisation_marker: 141, minor_data_reference: 90, consent_withdrawal_marker: 18 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_incident_report_adversarial_001.txt: `mirrored to a Hong Kong analytics node` |
| direct_identifier | SA | coverage_gap | 449 | 84 | 534.52 | sa_commercial_registration: 147, email_address: 101, sa_iqama: 90, sa_national_id: 31 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_incident_report_adversarial_001.txt: `CR 1012345678` |
| privacy_event | IN | coverage_gap | 431 | 84 | 513.1 | data_minimisation_marker: 173, minor_data_reference: 149, consent_withdrawal_marker: 57, cross_border_transfer_marker: 52 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_adversarial_001.txt: `child (under 18)` |
| direct_identifier | KR | coverage_gap | 430 | 84 | 511.9 | named_person: 125, email_address: 121, kr_rrn: 99, phone_number: 36 | test/fixtures/legal-corpus-candidates/kr/direct_identifiers/kr_direct_identifiers_incident_report_adversarial_001.txt: `421-87-31095` |
| direct_identifier | CN | coverage_gap | 423 | 84 | 503.57 | cn_uscc: 127, email_address: 95, cn_resident_id: 87, cn_phone: 43 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_incident_report_adversarial_001.txt: `138-1234-5678` |
| mnpi_context | US | conjunction_miss | 395 | 84 | 470.24 | selective_disclosure_risk: 194, information_barrier_marker: 71, blackout_period_reference: 63, tipping_language: 28 | test/fixtures/legal-corpus-candidates/us/direct_identifiers/us_direct_identifiers_incident_report_adversarial_001.txt: `this was not discussed with any sell-side analyst prior to the current report...` |
| mnpi_context | UK | conjunction_miss | 377 | 84 | 448.81 | selective_disclosure_risk: 85, information_barrier_marker: 84, blackout_period_reference: 78, insider_list_marker: 67 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_incident_report_adversarial_001.txt: `watch and restricted lists` |
| mnpi_context | EU | conjunction_miss | 353 | 84 | 420.24 | insider_list_marker: 90, blackout_period_reference: 70, information_barrier_marker: 69, selective_disclosure_risk: 64 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_incident_report_default_001.txt: `may significantly affect price` |
| mnpi_context | IN | conjunction_miss | 351 | 84 | 417.86 | blackout_period_reference: 110, information_barrier_marker: 77, insider_list_marker: 62, selective_disclosure_risk: 56 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_default_001.txt: `pre-clearance remained suspended` |
| direct_identifier | AE | coverage_gap | 349 | 84 | 415.48 | ae_trade_licence: 94, ae_emirates_id: 92, email_address: 91, bank_account: 25 | test/fixtures/legal-corpus-candidates/ae/direct_identifiers/ae_direct_identifiers_incident_report_adversarial_001.txt: `+971 4 555 0137` |
| mnpi_lexicon | ID | coverage_gap | 344 | 84 | 409.52 | nonpublic_marker: 114, material_event: 87, embargo_marker: 49, definitive_agreement: 28 | test/fixtures/legal-corpus-candidates/id/direct_identifiers/id_direct_identifiers_incident_report_adversarial_001.txt: `belum diumumkan ke publik` |
| direct_identifier | PH | coverage_gap | 339 | 84 | 403.57 | named_person: 124, email_address: 98, bank_account: 53, ph_tin: 30 | test/fixtures/legal-corpus-candidates/ph/direct_identifiers/ph_direct_identifiers_incident_report_adversarial_001.txt: `PA1234567` |
| mnpi_lexicon | JP | coverage_gap | 331 | 84 | 394.05 | material_event: 151, nonpublic_marker: 78, embargo_marker: 37, definitive_agreement: 23 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_incident_report_adversarial_001.txt: `tender offer` |
| mnpi_context | SG | conjunction_miss | 325 | 84 | 386.9 | selective_disclosure_risk: 77, information_barrier_marker: 76, blackout_period_reference: 69, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `may constitute MNPI` |
| mnpi_context | MY | conjunction_miss | 324 | 84 | 385.71 | selective_disclosure_risk: 82, blackout_period_reference: 81, information_barrier_marker: 67, contingent_mnpi_language: 45 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_incident_report_adversarial_001.txt: `re-wall-crossed` |
| mnpi_context | HK | conjunction_miss | 322 | 84 | 383.33 | information_barrier_marker: 89, selective_disclosure_risk: 69, blackout_period_reference: 66, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/hk/direct_identifiers/hk_direct_identifiers_incident_report_adversarial_001.txt: `may be price-sensitive under the SFO` |
| privacy_event | SA | coverage_gap | 318 | 84 | 378.57 | cross_border_transfer_marker: 164, data_minimisation_marker: 122, consent_withdrawal_marker: 26, minor_data_reference: 6 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_incident_report_adversarial_001.txt: `data minimised` |
| mnpi_lexicon | VN | coverage_gap | 310 | 84 | 369.05 | nonpublic_marker: 118, material_event: 76, embargo_marker: 40, definitive_agreement: 27 | test/fixtures/legal-corpus-candidates/vn/direct_identifiers/vn_direct_identifiers_incident_report_adversarial_001.txt: `not for public release` |
| mnpi_lexicon | UK | coverage_gap | 299 | 84 | 355.95 | nonpublic_marker: 127, material_event: 67, embargo_marker: 35, definitive_agreement: 27 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_incident_report_adversarial_001.txt: `inside information` |
