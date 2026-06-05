# Miss Concentration

This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.
Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.

## Summary

- Review profile: strict
- Miss count: 21105
- Buckets: coverage_gap: 15937, conjunction_miss: 4518, singling_out_miss: 474, needs_review: 147, true_inference_miss: 29
- Detector families: direct_identifier: 4643, mnpi_context: 4519, mnpi_lexicon: 4029, privacy_event: 3566, pseudonymised_linkable: 1085, sector_mnpi: 972, special_category: 945, online_device: 725, quasi_identifier: 474, unknown: 147
- Jurisdictions by raw misses: IN: 1821, CN: 1621, SA: 1432, KR: 1418, JP: 1355, MY: 1320, ID: 1312, PH: 1309, US: 1303, VN: 1300
- Jurisdictions by misses per 100 docs: IN: 2167.86 per 100 docs (1821 raw), EU: 2023.81 per 100 docs (425 raw), CN: 1929.76 per 100 docs (1621 raw), SA: 1704.76 per 100 docs (1432 raw), KR: 1688.1 per 100 docs (1418 raw), JP: 1613.1 per 100 docs (1355 raw), UK: 1604.76 per 100 docs (337 raw), MY: 1571.43 per 100 docs (1320 raw), ID: 1561.9 per 100 docs (1312 raw), PH: 1558.33 per 100 docs (1309 raw)

## Top Cells

| Detector family | Jurisdiction | Bucket | Misses | Docs | Misses / 100 docs | Top rules | Example |
|---|---|---|---:|---:|---:|---|---|
| direct_identifier | IN | coverage_gap | 462 | 84 | 550.0 | email_address: 130, in_pan: 90, in_aadhaar: 72, in_gstin: 70 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_adversarial_001.txt: `1234 5678 9012` |
| privacy_event | CN | coverage_gap | 459 | 84 | 546.43 | cross_border_transfer_marker: 210, data_minimisation_marker: 141, minor_data_reference: 90, consent_withdrawal_marker: 18 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_incident_report_adversarial_001.txt: `mirrored to a Hong Kong analytics node` |
| direct_identifier | SA | coverage_gap | 449 | 84 | 534.52 | sa_commercial_registration: 147, email_address: 101, sa_iqama: 90, sa_national_id: 31 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_incident_report_adversarial_001.txt: `CR 1012345678` |
| mnpi_context | EU | conjunction_miss | 111 | 21 | 528.57 | insider_list_marker: 30, blackout_period_reference: 23, selective_disclosure_risk: 23, information_barrier_marker: 20 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `maintain insider list entries` |
| mnpi_context | UK | conjunction_miss | 111 | 21 | 528.57 | blackout_period_reference: 28, information_barrier_marker: 28, selective_disclosure_risk: 22, insider_list_marker: 15 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `UK MAR insider list` |
| direct_identifier | KR | coverage_gap | 430 | 84 | 511.9 | named_person: 125, email_address: 121, kr_rrn: 99, phone_number: 36 | test/fixtures/legal-corpus-candidates/kr/direct_identifiers/kr_direct_identifiers_incident_report_adversarial_001.txt: `421-87-31095` |
| privacy_event | IN | coverage_gap | 430 | 84 | 511.9 | data_minimisation_marker: 173, minor_data_reference: 149, consent_withdrawal_marker: 57, cross_border_transfer_marker: 51 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_adversarial_001.txt: `child (under 18)` |
| direct_identifier | CN | coverage_gap | 423 | 84 | 503.57 | cn_uscc: 127, email_address: 95, cn_resident_id: 87, cn_phone: 43 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_incident_report_adversarial_001.txt: `138-1234-5678` |
| mnpi_context | US | conjunction_miss | 395 | 84 | 470.24 | selective_disclosure_risk: 194, information_barrier_marker: 71, blackout_period_reference: 63, tipping_language: 28 | test/fixtures/legal-corpus-candidates/us/direct_identifiers/us_direct_identifiers_incident_report_adversarial_001.txt: `this was not discussed with any sell-side analyst prior to the current report...` |
| mnpi_context | IN | conjunction_miss | 351 | 84 | 417.86 | blackout_period_reference: 110, information_barrier_marker: 77, insider_list_marker: 62, selective_disclosure_risk: 56 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_incident_report_default_001.txt: `pre-clearance remained suspended` |
| direct_identifier | AE | coverage_gap | 349 | 84 | 415.48 | ae_trade_licence: 94, ae_emirates_id: 92, email_address: 91, bank_account: 25 | test/fixtures/legal-corpus-candidates/ae/direct_identifiers/ae_direct_identifiers_incident_report_adversarial_001.txt: `+971 4 555 0137` |
| mnpi_lexicon | ID | coverage_gap | 344 | 84 | 409.52 | nonpublic_marker: 114, material_event: 87, embargo_marker: 49, definitive_agreement: 28 | test/fixtures/legal-corpus-candidates/id/direct_identifiers/id_direct_identifiers_incident_report_adversarial_001.txt: `belum diumumkan ke publik` |
| mnpi_lexicon | UK | coverage_gap | 85 | 21 | 404.76 | nonpublic_marker: 35, material_event: 24, embargo_marker: 11, financial_percentage: 4 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `6–8%` |
| direct_identifier | PH | coverage_gap | 339 | 84 | 403.57 | named_person: 124, email_address: 98, bank_account: 53, ph_tin: 30 | test/fixtures/legal-corpus-candidates/ph/direct_identifiers/ph_direct_identifiers_incident_report_adversarial_001.txt: `PA1234567` |
| privacy_event | EU | coverage_gap | 83 | 21 | 395.24 | cross_border_transfer_marker: 49, data_minimisation_marker: 28, consent_withdrawal_marker: 4, minor_data_reference: 2 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `cross-border transfer` |
| mnpi_lexicon | JP | coverage_gap | 331 | 84 | 394.05 | material_event: 151, nonpublic_marker: 78, embargo_marker: 37, definitive_agreement: 23 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_incident_report_adversarial_001.txt: `tender offer` |
| mnpi_context | SG | conjunction_miss | 325 | 84 | 386.9 | selective_disclosure_risk: 77, information_barrier_marker: 76, blackout_period_reference: 69, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `may constitute MNPI` |
| mnpi_context | MY | conjunction_miss | 324 | 84 | 385.71 | selective_disclosure_risk: 82, blackout_period_reference: 81, information_barrier_marker: 67, contingent_mnpi_language: 45 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_incident_report_adversarial_001.txt: `re-wall-crossed` |
| mnpi_context | HK | conjunction_miss | 322 | 84 | 383.33 | information_barrier_marker: 89, selective_disclosure_risk: 69, blackout_period_reference: 66, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/hk/direct_identifiers/hk_direct_identifiers_incident_report_adversarial_001.txt: `may be price-sensitive under the SFO` |
| privacy_event | SA | coverage_gap | 318 | 84 | 378.57 | cross_border_transfer_marker: 164, data_minimisation_marker: 122, consent_withdrawal_marker: 26, minor_data_reference: 6 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_incident_report_adversarial_001.txt: `data minimised` |
