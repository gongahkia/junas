# Miss Concentration

This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.
Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.

## Summary

- Review profile: strict
- Miss count: 6946
- Buckets: coverage_gap: 4992, conjunction_miss: 1749, singling_out_miss: 162, needs_review: 34, true_inference_miss: 9
- Detector families: mnpi_context: 1750, mnpi_lexicon: 1359, direct_identifier: 1301, privacy_event: 1163, pseudonymised_linkable: 337, special_category: 332, online_device: 255, sector_mnpi: 253, quasi_identifier: 162, unknown: 34
- Jurisdictions: SG: 1079, IN: 487, CN: 442, EU: 425, MY: 375, JP: 369, PH: 366, SA: 364, AU: 351, KR: 349

## Top Cells

| Detector family | Jurisdiction | Bucket | Misses | Top rules | Example |
|---|---|---|---:|---|---|
| mnpi_context | SG | conjunction_miss | 324 | selective_disclosure_risk: 77, information_barrier_marker: 76, blackout_period_reference: 69, contingent_mnpi_language: 47 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `may constitute MNPI` |
| mnpi_lexicon | SG | coverage_gap | 217 | material_event: 79, nonpublic_marker: 71, definitive_agreement: 19, embargo_marker: 16 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `not generally available` |
| privacy_event | SG | coverage_gap | 170 | data_minimisation_marker: 104, cross_border_transfer_marker: 41, consent_withdrawal_marker: 18, minor_data_reference: 7 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_memo_adversarial_001.txt: `minimised` |
| privacy_event | CN | coverage_gap | 134 | cross_border_transfer_marker: 65, data_minimisation_marker: 46, minor_data_reference: 20, consent_withdrawal_marker: 3 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_memo_adversarial_001.txt: `Cross-border: vendor BrightCloud HK Ltd. will receive HR contact lists; per C...` |
| mnpi_context | HK | conjunction_miss | 117 | information_barrier_marker: 41, selective_disclosure_risk: 27, blackout_period_reference: 22, contingent_mnpi_language: 10 | test/fixtures/legal-corpus-candidates/hk/direct_identifiers/hk_direct_identifiers_memo_adversarial_001.txt: `update insider list` |
| direct_identifier | IN | coverage_gap | 116 | email_address: 36, in_pan: 21, in_gstin: 18, in_aadhaar: 15 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `91-9876543210` |
| direct_identifier | SG | coverage_gap | 116 | email_address: 68, named_person: 11, bank_account: 10, phone_number: 9 | test/fixtures/legal-corpus-candidates/sg/direct_identifiers/sg_direct_identifiers_incident_report_adversarial_001.txt: `dpo@harbourquay.com` |
| mnpi_context | US | conjunction_miss | 114 | selective_disclosure_risk: 58, information_barrier_marker: 23, blackout_period_reference: 15, contingent_mnpi_language: 7 | test/fixtures/legal-corpus-candidates/us/direct_identifiers/us_direct_identifiers_memo_adversarial_001.txt: `not to be shared with sell-side analysts` |
| mnpi_context | EU | conjunction_miss | 111 | insider_list_marker: 30, blackout_period_reference: 23, selective_disclosure_risk: 23, information_barrier_marker: 20 | test/fixtures/legal-corpus-candidates/eu/direct_identifiers/eu_direct_identifiers_memo_adversarial_001.txt: `maintain insider list entries` |
| mnpi_context | UK | conjunction_miss | 111 | blackout_period_reference: 28, information_barrier_marker: 28, selective_disclosure_risk: 22, insider_list_marker: 15 | test/fixtures/legal-corpus-candidates/uk/direct_identifiers/uk_direct_identifiers_memo_adversarial_001.txt: `UK MAR insider list` |
| privacy_event | IN | coverage_gap | 111 | data_minimisation_marker: 59, minor_data_reference: 33, consent_withdrawal_marker: 14, cross_border_transfer_marker: 5 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `under 18 years` |
| direct_identifier | SA | coverage_gap | 108 | sa_commercial_registration: 31, sa_iqama: 26, email_address: 24, named_person: 9 | test/fixtures/legal-corpus-candidates/sa/direct_identifiers/sa_direct_identifiers_memo_adversarial_001.txt: `2 45 6789 012` |
| direct_identifier | CN | coverage_gap | 105 | cn_uscc: 26, cn_resident_id: 25, email_address: 19, bank_account: 13 | test/fixtures/legal-corpus-candidates/cn/direct_identifiers/cn_direct_identifiers_memo_adversarial_001.txt: `92310000MA0X1Y2Z3A` |
| direct_identifier | KR | coverage_gap | 105 | named_person: 34, email_address: 33, kr_rrn: 19, bank_account: 8 | test/fixtures/legal-corpus-candidates/kr/direct_identifiers/kr_direct_identifiers_memo_adversarial_001.txt: `123-45-67890` |
| mnpi_context | IN | conjunction_miss | 102 | blackout_period_reference: 31, selective_disclosure_risk: 20, information_barrier_marker: 17, insider_list_marker: 17 | test/fixtures/legal-corpus-candidates/in/direct_identifiers/in_direct_identifiers_memo_adversarial_001.txt: `trading window to close` |
| mnpi_context | MY | conjunction_miss | 96 | blackout_period_reference: 26, information_barrier_marker: 25, selective_disclosure_risk: 23, contingent_mnpi_language: 10 | test/fixtures/legal-corpus-candidates/my/direct_identifiers/my_direct_identifiers_memo_adversarial_001.txt: `closed period under Paragraph 14.08 from 15/06/2026 to 29/06/2026` |
| direct_identifier | PH | coverage_gap | 94 | named_person: 33, email_address: 29, bank_account: 16, ph_tin: 10 | test/fixtures/legal-corpus-candidates/ph/direct_identifiers/ph_direct_identifiers_memo_adversarial_001.txt: `TIN 482-319-574-000` |
| mnpi_lexicon | ID | coverage_gap | 92 | nonpublic_marker: 31, material_event: 23, embargo_marker: 15, financial_percentage: 6 | test/fixtures/legal-corpus-candidates/id/direct_identifiers/id_direct_identifiers_memo_adversarial_001.txt: `Rencana akuisisi PT Lintas Dana Selaras` |
| mnpi_lexicon | JP | coverage_gap | 92 | material_event: 47, nonpublic_marker: 21, embargo_marker: 9, definitive_agreement: 6 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_memo_adversarial_001.txt: `proposed acquisition of Hikari Robotics KK via tender offer` |
| mnpi_context | JP | conjunction_miss | 85 | information_barrier_marker: 24, blackout_period_reference: 22, selective_disclosure_risk: 19, insider_list_marker: 12 | test/fixtures/legal-corpus-candidates/jp/direct_identifiers/jp_direct_identifiers_memo_adversarial_001.txt: `do not circulate enumerated facts or tender-offer facts until official disclo...` |
