# Miss Concentration

This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.
Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.

## Summary

- Review profile: strict
- Miss count: 8800
- Buckets: coverage_gap: 6374, conjunction_miss: 2146, singling_out_miss: 204, needs_review: 47, true_inference_miss: 29
- Detector families: mnpi_context: 2147, mnpi_lexicon: 1778, direct_identifier: 1650, privacy_event: 1400, pseudonymised_linkable: 456, special_category: 431, sector_mnpi: 369, online_device: 318, quasi_identifier: 204, unknown: 47
- Jurisdictions by raw misses: HK: 1282, AU: 1264, SG: 1079, IN: 487, CN: 442, EU: 425, MY: 375, JP: 369, PH: 368, SA: 365
- Jurisdictions by misses per 100 docs: IN: 2319.05 per 100 docs (487 raw), CN: 2104.76 per 100 docs (442 raw), EU: 2023.81 per 100 docs (425 raw), MY: 1785.71 per 100 docs (375 raw), JP: 1757.14 per 100 docs (369 raw), PH: 1752.38 per 100 docs (368 raw), SA: 1738.1 per 100 docs (365 raw), KR: 1661.9 per 100 docs (349 raw), VN: 1657.14 per 100 docs (348 raw), AE: 1619.05 per 100 docs (340 raw)

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
| mnpi_context | MY | conjunction_miss | 96 | 21 | 457.14 | blackout_period_reference: 26, information_barrier_marker: 25, selective_disclosure_risk: 23, contingent_mnpi_language: 10 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_memo_adversarial_001.txt: `closed period under Paragraph 14.08 from 15/06/2026 to 29/06/2026` |
| direct_identifier | PH | coverage_gap | 95 | 21 | 452.38 | named_person: 33, email_address: 30, bank_account: 16, ph_tin: 10 | test/fixtures/legal-corpus-candidates/ph/direct_identifiers/ph_direct_identifiers_memo_adversarial_001.txt: `TIN 482-319-574-000` |
| mnpi_lexicon | ID | coverage_gap | 92 | 21 | 438.1 | nonpublic_marker: 31, material_event: 23, embargo_marker: 15, financial_percentage: 6 | test/fixtures/legal-corpus-candidates/id/direct_identifiers/id_direct_identifiers_memo_adversarial_001.txt: `Rencana akuisisi PT Lintas Dana Selaras` |
| mnpi_lexicon | JP | coverage_gap | 92 | 21 | 438.1 | material_event: 47, nonpublic_marker: 21, embargo_marker: 9, definitive_agreement: 6 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_memo_adversarial_001.txt: `proposed acquisition of Hikari Robotics KK via tender offer` |
| mnpi_context | JP | conjunction_miss | 85 | 21 | 404.76 | information_barrier_marker: 24, blackout_period_reference: 22, selective_disclosure_risk: 19, insider_list_marker: 12 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_memo_adversarial_001.txt: `do not circulate enumerated facts or tender-offer facts until official disclo...` |
| mnpi_lexicon | MY | coverage_gap | 85 | 21 | 404.76 | nonpublic_marker: 27, material_event: 25, definitive_agreement: 16, embargo_marker: 7 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_memo_adversarial_001.txt: `Subscription Agreement` |
| mnpi_lexicon | UK | coverage_gap | 85 | 21 | 404.76 | nonpublic_marker: 35, material_event: 24, embargo_marker: 11, financial_percentage: 4 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `6–8%` |
| mnpi_lexicon | IN | coverage_gap | 83 | 21 | 395.24 | nonpublic_marker: 47, material_event: 23, definitive_agreement: 6, embargo_marker: 4 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `unpublished order book` |
| privacy_event | EU | coverage_gap | 83 | 21 | 395.24 | cross_border_transfer_marker: 49, data_minimisation_marker: 28, consent_withdrawal_marker: 4, minor_data_reference: 2 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `cross-border transfer` |
| mnpi_context | SA | conjunction_miss | 82 | 21 | 390.48 | blackout_period_reference: 22, selective_disclosure_risk: 20, insider_list_marker: 15, information_barrier_marker: 12 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `restrict to need‑to‑know` |
