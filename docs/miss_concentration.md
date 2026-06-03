# Miss Concentration

This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.
Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.

## Summary

- Review profile: strict
- Miss count: 13503
- Buckets: coverage_gap: 9998, conjunction_miss: 3064, singling_out_miss: 320, needs_review: 92, true_inference_miss: 29
- Detector families: mnpi_context: 3065, mnpi_lexicon: 2773, direct_identifier: 2662, privacy_event: 2087, pseudonymised_linkable: 746, sector_mnpi: 649, special_category: 628, online_device: 481, quasi_identifier: 320, unknown: 92
- Jurisdictions by raw misses: MY: 1317, ID: 1310, PH: 1308, VN: 1294, HK: 1282, AU: 1265, TH: 1215, SG: 1079, IN: 487, CN: 442
- Jurisdictions by misses per 100 docs: IN: 2319.05 per 100 docs (487 raw), CN: 2104.76 per 100 docs (442 raw), EU: 2023.81 per 100 docs (425 raw), JP: 1757.14 per 100 docs (369 raw), SA: 1738.1 per 100 docs (365 raw), KR: 1661.9 per 100 docs (349 raw), AE: 1619.05 per 100 docs (340 raw), UK: 1604.76 per 100 docs (337 raw), MY: 1567.86 per 100 docs (1317 raw), ID: 1559.52 per 100 docs (1310 raw)

## Top Cells

| Detector family | Jurisdiction | Bucket | Misses | Docs | Misses / 100 docs | Top rules | Example |
|---|---|---|---:|---:|---:|---|---|
| privacy_event | CN | coverage_gap | 134 | 21 | 638.1 | cross_border_transfer_marker: 65, data_minimisation_marker: 46, minor_data_reference: 20, consent_withdrawal_marker: 3 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_memo_adversarial_001.txt: `Cross-border: vendor BrightCloud HK Ltd. will receive HR contact lists; per C...` |
| direct_identifier | IN | coverage_gap | 116 | 21 | 552.38 | email_address: 36, in_pan: 21, in_gstin: 18, in_aadhaar: 15 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `91-9876543210` |
| mnpi_context | US | conjunction_miss | 114 | 21 | 542.86 | selective_disclosure_risk: 58, information_barrier_marker: 23, blackout_period_reference: 15, contingent_mnpi_language: 7 | test/fixtures/legal-corpus-candidates/us/direct_identifiers/us_direct_identifiers_memo_adversarial_001.txt: `not to be shared with sell-side analysts` |
| mnpi_context | EU | conjunction_miss | 111 | 21 | 528.57 | insider_list_marker: 30, blackout_period_reference: 23, selective_disclosure_risk: 23, information_barrier_marker: 20 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `maintain insider list entries` |
| mnpi_context | UK | conjunction_miss | 111 | 21 | 528.57 | blackout_period_reference: 28, information_barrier_marker: 28, selective_disclosure_risk: 22, insider_list_marker: 15 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `UK MAR insider list` |
| privacy_event | IN | coverage_gap | 111 | 21 | 528.57 | data_minimisation_marker: 59, minor_data_reference: 33, consent_withdrawal_marker: 14, cross_border_transfer_marker: 5 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `under 18 years` |
| direct_identifier | SA | coverage_gap | 108 | 21 | 514.29 | sa_commercial_registration: 31, sa_iqama: 26, email_address: 24, named_person: 9 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `2 45 6789 012` |
| direct_identifier | CN | coverage_gap | 105 | 21 | 500.0 | cn_uscc: 26, cn_resident_id: 25, email_address: 19, bank_account: 13 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_memo_adversarial_001.txt: `92310000MA0X1Y2Z3A` |
| direct_identifier | KR | coverage_gap | 105 | 21 | 500.0 | named_person: 34, email_address: 33, kr_rrn: 19, bank_account: 8 | test/fixtures/legal-corpus-candidates/kr/direct_identifiers/kr_direct_identifiers_memo_adversarial_001.txt: `123-45-67890` |
| mnpi_context | IN | conjunction_miss | 102 | 21 | 485.71 | blackout_period_reference: 31, selective_disclosure_risk: 20, information_barrier_marker: 17, insider_list_marker: 17 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `trading window to close` |
| mnpi_lexicon | JP | coverage_gap | 92 | 21 | 438.1 | material_event: 47, nonpublic_marker: 21, embargo_marker: 9, definitive_agreement: 6 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_memo_adversarial_001.txt: `proposed acquisition of Hikari Robotics KK via tender offer` |
| mnpi_lexicon | ID | coverage_gap | 344 | 84 | 409.52 | nonpublic_marker: 114, material_event: 87, embargo_marker: 49, definitive_agreement: 28 | test/fixtures/legal-corpus-candidates/id/direct_identifiers/id_direct_identifiers_incident_report_adversarial_001.txt: `belum diumumkan ke publik` |
| mnpi_context | JP | conjunction_miss | 85 | 21 | 404.76 | information_barrier_marker: 24, blackout_period_reference: 22, selective_disclosure_risk: 19, insider_list_marker: 12 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_memo_adversarial_001.txt: `do not circulate enumerated facts or tender-offer facts until official disclo...` |
| mnpi_lexicon | UK | coverage_gap | 85 | 21 | 404.76 | nonpublic_marker: 35, material_event: 24, embargo_marker: 11, financial_percentage: 4 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `6–8%` |
| direct_identifier | PH | coverage_gap | 338 | 84 | 402.38 | named_person: 124, email_address: 98, bank_account: 53, ph_tin: 30 | test/fixtures/legal-corpus-candidates/ph/direct_identifiers/ph_direct_identifiers_incident_report_adversarial_001.txt: `PA1234567` |
| mnpi_lexicon | IN | coverage_gap | 83 | 21 | 395.24 | nonpublic_marker: 47, material_event: 23, definitive_agreement: 6, embargo_marker: 4 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `unpublished order book` |
| privacy_event | EU | coverage_gap | 83 | 21 | 395.24 | cross_border_transfer_marker: 49, data_minimisation_marker: 28, consent_withdrawal_marker: 4, minor_data_reference: 2 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `cross-border transfer` |
| mnpi_context | SA | conjunction_miss | 82 | 21 | 390.48 | blackout_period_reference: 22, selective_disclosure_risk: 20, insider_list_marker: 15, information_barrier_marker: 12 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `restrict to need‑to‑know` |
| mnpi_context | MY | conjunction_miss | 324 | 84 | 385.71 | selective_disclosure_risk: 82, blackout_period_reference: 81, information_barrier_marker: 67, contingent_mnpi_language: 45 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_incident_report_adversarial_001.txt: `re-wall-crossed` |
| mnpi_context | SG | conjunction_miss | 324 | 84 | 385.71 | selective_disclosure_risk: 77, information_barrier_marker: 76, blackout_period_reference: 69, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `may constitute MNPI` |
