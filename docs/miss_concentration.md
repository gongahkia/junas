# Miss Concentration

This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.
Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.

## Summary

- Review profile: strict
- Miss count: 16909
- Buckets: coverage_gap: 12683, conjunction_miss: 3701, singling_out_miss: 377, needs_review: 119, true_inference_miss: 29
- Detector families: mnpi_context: 3702, direct_identifier: 3544, mnpi_lexicon: 3410, privacy_event: 2719, pseudonymised_linkable: 901, sector_mnpi: 788, special_category: 750, online_device: 599, quasi_identifier: 377, unknown: 119
- Jurisdictions by raw misses: IN: 1820, KR: 1417, JP: 1354, MY: 1318, ID: 1311, PH: 1309, VN: 1298, HK: 1283, AU: 1269, TH: 1218
- Jurisdictions by misses per 100 docs: IN: 2166.67 per 100 docs (1820 raw), CN: 2109.52 per 100 docs (443 raw), EU: 2023.81 per 100 docs (425 raw), SA: 1738.1 per 100 docs (365 raw), KR: 1686.9 per 100 docs (1417 raw), AE: 1619.05 per 100 docs (340 raw), JP: 1611.9 per 100 docs (1354 raw), UK: 1604.76 per 100 docs (337 raw), MY: 1569.05 per 100 docs (1318 raw), ID: 1560.71 per 100 docs (1311 raw)

## Top Cells

| Detector family | Jurisdiction | Bucket | Misses | Docs | Misses / 100 docs | Top rules | Example |
|---|---|---|---:|---:|---:|---|---|
| privacy_event | CN | coverage_gap | 134 | 21 | 638.1 | cross_border_transfer_marker: 65, data_minimisation_marker: 46, minor_data_reference: 20, consent_withdrawal_marker: 3 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_memo_adversarial_001.txt: `Cross-border: vendor BrightCloud HK Ltd. will receive HR contact lists; per C...` |
| direct_identifier | IN | coverage_gap | 462 | 84 | 550.0 | email_address: 130, in_pan: 90, in_aadhaar: 72, in_gstin: 70 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_adversarial_001.txt: `1234 5678 9012` |
| mnpi_context | US | conjunction_miss | 114 | 21 | 542.86 | selective_disclosure_risk: 58, information_barrier_marker: 23, blackout_period_reference: 15, contingent_mnpi_language: 7 | test/fixtures/legal-corpus-candidates/us/direct_identifiers/us_direct_identifiers_memo_adversarial_001.txt: `not to be shared with sell-side analysts` |
| mnpi_context | EU | conjunction_miss | 111 | 21 | 528.57 | insider_list_marker: 30, blackout_period_reference: 23, selective_disclosure_risk: 23, information_barrier_marker: 20 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `maintain insider list entries` |
| mnpi_context | UK | conjunction_miss | 111 | 21 | 528.57 | blackout_period_reference: 28, information_barrier_marker: 28, selective_disclosure_risk: 22, insider_list_marker: 15 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `UK MAR insider list` |
| direct_identifier | SA | coverage_gap | 108 | 21 | 514.29 | sa_commercial_registration: 31, sa_iqama: 26, email_address: 24, named_person: 9 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `2 45 6789 012` |
| direct_identifier | KR | coverage_gap | 430 | 84 | 511.9 | named_person: 125, email_address: 121, kr_rrn: 99, phone_number: 36 | test/fixtures/legal-corpus-candidates/kr/direct_identifiers/kr_direct_identifiers_incident_report_adversarial_001.txt: `421-87-31095` |
| privacy_event | IN | coverage_gap | 430 | 84 | 511.9 | data_minimisation_marker: 173, minor_data_reference: 149, consent_withdrawal_marker: 57, cross_border_transfer_marker: 51 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_adversarial_001.txt: `child (under 18)` |
| direct_identifier | CN | coverage_gap | 106 | 21 | 504.76 | cn_uscc: 26, cn_resident_id: 25, email_address: 19, bank_account: 13 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_memo_adversarial_001.txt: `92310000MA0X1Y2Z3A` |
| mnpi_context | IN | conjunction_miss | 351 | 84 | 417.86 | blackout_period_reference: 110, information_barrier_marker: 77, insider_list_marker: 62, selective_disclosure_risk: 56 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_default_001.txt: `pre-clearance remained suspended` |
| mnpi_lexicon | ID | coverage_gap | 344 | 84 | 409.52 | nonpublic_marker: 114, material_event: 87, embargo_marker: 49, definitive_agreement: 28 | test/fixtures/legal-corpus-candidates/id/direct_identifiers/id_direct_identifiers_incident_report_adversarial_001.txt: `belum diumumkan ke publik` |
| mnpi_lexicon | UK | coverage_gap | 85 | 21 | 404.76 | nonpublic_marker: 35, material_event: 24, embargo_marker: 11, financial_percentage: 4 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `6–8%` |
| direct_identifier | PH | coverage_gap | 339 | 84 | 403.57 | named_person: 124, email_address: 98, bank_account: 53, ph_tin: 30 | test/fixtures/legal-corpus-candidates/ph/direct_identifiers/ph_direct_identifiers_incident_report_adversarial_001.txt: `PA1234567` |
| privacy_event | EU | coverage_gap | 83 | 21 | 395.24 | cross_border_transfer_marker: 49, data_minimisation_marker: 28, consent_withdrawal_marker: 4, minor_data_reference: 2 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `cross-border transfer` |
| mnpi_lexicon | JP | coverage_gap | 331 | 84 | 394.05 | material_event: 151, nonpublic_marker: 78, embargo_marker: 37, definitive_agreement: 23 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_incident_report_adversarial_001.txt: `tender offer` |
| mnpi_context | SA | conjunction_miss | 82 | 21 | 390.48 | blackout_period_reference: 22, selective_disclosure_risk: 20, insider_list_marker: 15, information_barrier_marker: 12 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `restrict to need‑to‑know` |
| mnpi_context | MY | conjunction_miss | 324 | 84 | 385.71 | selective_disclosure_risk: 82, blackout_period_reference: 81, information_barrier_marker: 67, contingent_mnpi_language: 45 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_incident_report_adversarial_001.txt: `re-wall-crossed` |
| mnpi_context | SG | conjunction_miss | 324 | 84 | 385.71 | selective_disclosure_risk: 77, information_barrier_marker: 76, blackout_period_reference: 69, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `may constitute MNPI` |
| mnpi_context | AE | conjunction_miss | 81 | 21 | 385.71 | information_barrier_marker: 21, selective_disclosure_risk: 20, blackout_period_reference: 13, insider_list_marker: 12 | test/fixtures/legal-corpus-candidates/ae/direct_identifiers/ae_direct_identifiers_memo_adversarial_001.txt: `distribution restricted per ECMA Rulebook 6.2` |
| privacy_event | SA | coverage_gap | 81 | 21 | 385.71 | cross_border_transfer_marker: 40, data_minimisation_marker: 35, consent_withdrawal_marker: 5, minor_data_reference: 1 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `ensure accuracy and minimization` |
