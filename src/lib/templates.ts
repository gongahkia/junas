/**
 * Legal Document Templates for Singapore Law
 * These templates provide starting points for common legal documents
 */

export interface LegalTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  prompt: string;
  icon?: string;
}

export const legalTemplates: LegalTemplate[] = [
  // Contracts & Agreements
  {
    id: 'nda',
    name: 'Non-Disclosure Agreement (NDA)',
    category: 'Contracts',
    description: 'Confidentiality agreement for protecting sensitive information',
    prompt: `Draft a comprehensive Non-Disclosure Agreement (NDA) compliant with Singapore contract law and common law principles of confidentiality with the following detailed requirements:

ESSENTIAL PARTIES INFORMATION:
1. Disclosing Party: [Full legal name, UEN/registration number, registered address]
2. Receiving Party: [Full legal name, UEN/registration number, registered address]
3. Representatives: Include provisions for employees, contractors, and agents of both parties

RECITALS AND PURPOSE:
4. Background: Detailed context explaining the business relationship and need for confidentiality
5. Purpose: Specific purpose(s) for which confidential information will be disclosed (must be precisely defined to ensure enforceability)

DEFINITION OF CONFIDENTIAL INFORMATION (Critical for enforceability):
6. Comprehensive definition including:
   - All information disclosed in any form (oral, written, electronic, visual)
   - Technical data, trade secrets, know-how, research, product plans
   - Business information: customer lists, pricing, marketing strategies, financial data
   - Information marked "Confidential" or identified as such within 30 days of oral disclosure
   - Exclusions: Information that is (i) publicly available through no breach, (ii) independently developed, (iii) rightfully received from third parties, (iv) already known prior to disclosure, (v) required by law to be disclosed (with notice requirement)

OBLIGATIONS OF RECEIVING PARTY (Must be specific and enforceable):
7. Non-Disclosure: Strict prohibition on disclosure except to authorized representatives on need-to-know basis
8. Non-Use: Use only for the specified purpose, prohibited from using for competitive advantage
9. Standard of Care: Must protect with same degree of care as own confidential information (minimum reasonable care standard)
10. Access Control: Limit access to employees/contractors who need to know and are bound by similar obligations
11. Security Measures: Implement reasonable physical, electronic, and procedural safeguards
12. Notification: Immediate notice if breach or unauthorized disclosure occurs
13. Return/Destruction: Upon request or termination, return or certify destruction of all confidential materials

DURATION AND TERM:
14. Confidentiality Period: [Recommend 3-5 years from date of disclosure, or perpetual for trade secrets per common law]
15. Survival: Obligations survive termination of business relationship

INTELLECTUAL PROPERTY:
16. No License: Clarify that disclosure does not grant any IP rights, licenses, or interests
17. Ownership: All confidential information remains property of disclosing party

REMEDIES AND ENFORCEMENT (Essential per Aquila Design v Cornhill Insurance principles):
18. Irreparable Harm: Acknowledge that breach causes irreparable harm not adequately compensable by damages
19. Injunctive Relief: Right to seek immediate injunctive relief and specific performance without proving damages
20. Damages: Right to claim monetary damages, including consequential damages
21. Cumulative Remedies: Remedies are cumulative, not exclusive
22. Costs: Prevailing party entitled to legal costs on indemnity basis

GENERAL PROVISIONS:
23. No Obligation to Disclose: Disclosing party may withhold information at discretion
24. No Warranty: Information provided "as is" without warranties of accuracy or completeness
25. Independent Contractor: Parties remain independent, no partnership/joint venture created
26. Severability: If any provision invalid, remainder remains enforceable
27. Waiver: No waiver unless in writing; waiver of one breach not waiver of others
28. Amendment: Must be in writing signed by both parties
29. Entire Agreement: Supersedes all prior agreements on the subject matter
30. Counterparts: May be executed in counterparts, each an original

GOVERNING LAW AND JURISDICTION:
31. Governing Law: Laws of the Republic of Singapore (excluding conflicts of law principles)
32. Jurisdiction: Non-exclusive jurisdiction of Singapore courts
33. Service of Process: Acceptance of service at registered addresses

COMPLIANCE NOTES:
- Ensure compliance with Personal Data Protection Act 2012 if personal data is disclosed
- Consider PDPA obligations for data protection, security, and transfer restrictions
- For trade secrets, note common law protections under breach of confidence principles (Coco v A N Clark (Engineers) Ltd test)
- Restrictions must be reasonable in scope, duration, and geographic extent to be enforceable

Please draft with formal contract language, proper definitions section, and execution blocks for authorized signatories.`,
  },
  {
    id: 'employment',
    name: 'Employment Contract',
    category: 'Employment',
    description: 'Standard employment agreement for Singapore employees',
    prompt: `Draft an Employment Contract in STRICT COMPLIANCE with the Employment Act (Cap. 91), Employment Regulations, and Ministry of Manpower (MOM) guidelines:

PARTIES AND COMMENCEMENT (Section 95, Employment Act):
1. Employer: [Full legal name, UEN, registered address, nature of business]
2. Employee: [Full name, NRIC/FIN, residential address, contact details]
3. Commencement Date: [Specific date]
4. Probation Period: [Maximum 6 months for non-executives; clearly state assessment criteria and confirmation process]
5. Place of Work: [Primary work location and any mobility clauses]

POSITION AND DUTIES (Key Appointment Terms):
6. Job Title: [Specific designation]
7. Reporting Line: [Direct supervisor and organizational structure]
8. Duties and Responsibilities: Detailed description of role, KPIs, and performance expectations
9. Variation of Duties: Right to assign additional/alternative duties commensurate with position
10. Exclusivity: Full-time employment clause (if applicable) prohibiting external employment without consent

COMPENSATION AND BENEFITS (Must comply with Employment Act Part IV):
11. Basic Salary: $[Amount] per month (clearly distinguish basic from allowances per Section 2)
12. Salary Payment: Last day of each month via bank transfer (Section 20 - must be at least once monthly)
13. CPF Contributions: Employer and employee contributions per CPF Act at prevailing rates
14. Itemized Pay Slip: Provided monthly showing basic salary, allowances, deductions, CPF (Section 96)
15. Allowances: [Transport: $X, Meal: $Y, Mobile: $Z - specify if conditional]
16. Annual Wage Supplement (AWS/13th Month): [If applicable, state quantum and payment terms]
17. Variable Bonus: [If applicable, state performance criteria - emphasize discretionary nature if not guaranteed]
18. Salary Review: [Annual review process, non-guaranteed]

WORKING HOURS (Part IV, Sections 38-41 Employment Act):
19. Normal Working Hours:
    - [X] hours per day, [Y] hours per week (Max 44 hours/week per Section 38)
    - Working days: Monday to Friday, [9am to 6pm] with [1 hour] lunch break
20. Rest Days: [Specify day, typically Sunday] - minimum one per week (Section 36)
21. Overtime (for non-workmen earning ≤$2,600 or workmen earning ≤$4,500):
    - Rate: 1.5x hourly basic rate (Section 37)
    - Calculation: Basic monthly salary ÷ 26 days ÷ working hours per day
    - Payment: Within 14 days of last day of salary period (Section 21)
22. Flexible Work Arrangements: [If applicable, specify telecommuting/hybrid terms]

LEAVE ENTITLEMENTS (Mandatory per Employment Act):
23. Annual Leave (Section 43):
    - Years 1: [7] days minimum (prorated for first year)
    - Years 2: [7] days
    - Years 3-4: [8] days
    - Years 5-6: [9] days
    - Years 7-8: [11] days
    - Years 9+: [14] days
    - Must be taken within 12 months after earning; max carry forward [X] days with consent
    - Leave encashment only upon termination for untaken leave
24. Sick Leave (Section 89):
    - First 6 months: Outpatient [5] days, Hospitalization [15] days (prorated)
    - After 6 months: Outpatient [14] days, Hospitalization [60] days annually
    - Medical certificate from company/registered medical practitioner required
    - Paid at regular salary if sufficient leave balance
25. Maternity Leave (Child Development Co-Savings Act):
    - Government-Paid Maternity Leave: First 8 weeks at 100% for first 2 children (last 4 weeks capped)
    - Employer-Paid Maternity Leave: Remaining 8 weeks at 100% for citizens' first/second child
    - Total: 16 weeks for first/second child (citizen), 12 weeks for third/fourth child
    - Eligibility: Employed for 3+ months, child is Singapore citizen, notification requirements
26. Paternity Leave (Child Development Co-Savings Act):
    - 2 weeks Government-Paid Paternity Leave
    - Must be taken within 12 months of child's birth
    - Eligibility: Married to child's mother, child is Singapore citizen
27. Shared Parental Leave: [If applicable, 4 weeks for mothers to share with fathers]
28. Childcare Leave: [6 days annually for parents with citizens below 7 years old]
29. Unpaid Infant Care/Extended Childcare Leave: [If applicable per Employment Act]
30. Compassionate Leave: [Specify if provided - not statutory]
31. National Service Leave: As per Enlistment Act

TERMINATION OF EMPLOYMENT (Part V, Sections 10-14):
32. Notice Period (Section 10-11):
    - By Employer: [X weeks/months] written notice or salary in lieu
    - By Employee: [X weeks/months] written notice
    - Minimum: Length of service <26 weeks = 1 day; 26 weeks-2 years = 1 week; 2-5 years = 2 weeks; 5+ years = 4 weeks
33. Probation Termination: [X days notice or payment in lieu during probation]
34. Payment Upon Termination: All salary, unused leave, pro-rated AWS/bonus (if contractual) paid within 7 days (Section 20)
35. Summary Dismissal Without Notice (Section 14 - Misconduct):
    - Wilful insubordination, dishonesty, habitual neglect, absence without leave, criminal breach of trust, etc.
    - Must follow due inquiry process per common law principles (Browne v Dunn; Re Nalpon Zero Geraldo Mario)
36. Return of Property: All company property, documents, equipment returned upon exit
37. Post-Employment Interview: Exit clearance and handover procedures

CONFIDENTIALITY AND RESTRICTIVE COVENANTS:
38. Confidentiality: Perpetual obligation to protect trade secrets, confidential information, customer data
39. Non-Solicitation: [X months] prohibition on soliciting employees, customers, suppliers after termination
40. Non-Competition: [X months, specific geographic area, specific industry] - MUST be reasonable to be enforceable
    - Note: Courts strictly interpret restraint of trade clauses (Man Financial v Wong Barrel; Smile Inc Dental Surgeons v Lui Andrew Stewart)
    - Must protect legitimate proprietary interests only; cannot be merely to prevent competition
41. Non-Disparagement: Obligation not to make detrimental statements about company

INTELLECTUAL PROPERTY (Section 6, Copyright Act):
42. Work Product Assignment: All IP created in course of employment automatically vests in employer
43. Moral Rights Waiver: Waiver of attribution and integrity rights where permitted by law
44. Disclosure: Obligation to disclose all inventions, works, and IP created during employment
45. Assistance: Cooperation in registering and protecting employer's IP rights

CONDUCT AND POLICIES:
46. Code of Conduct: Adherence to company policies, handbook, and directives (attach as schedule)
47. Conflict of Interest: Disclosure of conflicts; prohibition on competing business interests
48. Data Protection: Compliance with Personal Data Protection Act 2012
49. Anti-Bribery: Compliance with Prevention of Corruption Act
50. Workplace Safety: Compliance with Workplace Safety and Health Act

DISCIPLINARY PROCEDURES (MOM Guidelines):
51. Progressive Discipline: Verbal warning → written warning → final warning → dismissal
52. Right to Explanation: Fair opportunity to respond before disciplinary action
53. Appeal Process: Right to appeal disciplinary decisions to [designated authority]

BENEFITS AND INSURANCE:
54. Medical Benefits: [Specify coverage - outpatient, hospitalization, dental, optical]
55. Work Injury Compensation: Coverage per Work Injury Compensation Act
56. Group Insurance: [If applicable - group term life, personal accident]

GENERAL PROVISIONS:
57. Entire Agreement: Supersedes all prior terms (written/oral); amendments must be in writing
58. Severability: Invalid provisions severed; remainder remains valid
59. Waiver: No waiver unless written; single waiver not continuing waiver
60. Assignment: Employee cannot assign contract; employer may assign subject to TUPE principles
61. Governing Law: Singapore law
62. Jurisdiction: Singapore courts
63. Language: English prevails if translated

MANDATORY COMPLIANCE:
- Employment Act applies to employees earning ≤$4,500 (workmen) or ≤$2,600 (non-workmen) - certain provisions apply to all
- Key Employment Terms (KET): Must provide within 14 days of commencement per Section 95
- Itemized payslips: Mandatory per Section 96
- CPF contributions: Mandatory for Singapore Citizens/PRs per CPF Act
- Work Pass conditions: Ensure compliance if foreign employee (Employment of Foreign Manpower Act)
- Tripartite Guidelines: Fair employment practices, flexible work arrangements, progressive wages

Please draft with professional language, clear definitions, and execution blocks. Include schedule for detailed policies if referenced.`,
  },
  {
    id: 'service-agreement',
    name: 'Service Agreement',
    category: 'Contracts',
    description: 'Agreement for provision of services',
    prompt: `Draft a comprehensive Service Agreement compliant with Singapore contract law and commercial practices:

PARTIES AND EFFECTIVE DATE:
1. Service Provider: [Full legal name, UEN, registered address, business description]
2. Client: [Full legal name, UEN, registered address]
3. Effective Date: [Date] (and relationship to execution date if different)
4. Background/Recitals: Context and purpose of engagement

SCOPE OF SERVICES (Must be precisely defined):
5. Services Description: Detailed specification of services including:
   - Specific deliverables and milestones with acceptance criteria
   - Service levels and performance standards (SLAs)
   - Response times and turnaround commitments
   - Locations where services will be performed
   - Resources and personnel to be deployed
6. Excluded Services: Explicitly state what is NOT included
7. Change Orders: Process for requesting and approving scope changes (written authorization, cost adjustments)

TERM AND RENEWAL:
8. Initial Term: [X months/years] from Effective Date
9. Renewal: [Automatic renewal for successive [X] periods unless either party gives [Y] days' written notice]
10. Termination for Convenience: Either party may terminate on [X] days' written notice [with/without penalty]
11. Effect of Expiry/Termination: Obligations surviving termination

FEES, PAYMENT TERMS, AND EXPENSES:
12. Service Fees:
    - Fixed fee: $[Amount] per [month/quarter/project]
    - Or Time-based: $[Rate] per hour/day
    - Or Milestone-based: Payment schedule tied to deliverables
13. Payment Terms: Net [30] days from date of invoice
14. Late Payment: Interest at [X]% per month or Section 12, Civil Law Act rate (whichever higher) on overdue amounts
15. Invoicing: Monthly invoicing with itemization requirements
16. Expenses: [Reimbursable with prior approval / Included in fees] - specify approval thresholds
17. Taxes: All fees exclusive of GST; client responsible for applicable taxes

PERFORMANCE STANDARDS AND SERVICE LEVELS:
18. Service Level Agreement (SLA):
    - Availability: [X]% uptime
    - Response time: [Y] hours for support requests
    - Resolution time: [Z] hours/days for issues by severity
    - Performance metrics and measurement methodology
19. Service Credits/Remedies: Credits or refunds if SLAs not met
20. Monitoring and Reporting: Regular reports on performance against SLAs

OBLIGATIONS OF SERVICE PROVIDER:
21. Service Delivery: Provide services professionally, skillfully, and diligently
22. Compliance: Comply with all applicable laws, regulations, and industry standards
23. Personnel: Provide qualified personnel; right to replace if unsuitable
24. Equipment and Materials: Responsibility for tools, equipment, materials needed
25. Insurance: Maintain professional indemnity, public liability insurance [minimum $X coverage]
26. Data Protection: Comply with Personal Data Protection Act 2012 if handling personal data

OBLIGATIONS OF CLIENT:
27. Cooperation: Provide timely access, information, approvals needed for service delivery
28. Facilities: Provide workspace, equipment, systems access as required
29. Payment: Timely payment of fees
30. Acceptance: Review and accept/reject deliverables within [X] days per acceptance criteria

INTELLECTUAL PROPERTY RIGHTS:
31. Background IP: Each party retains ownership of pre-existing IP
32. Foreground IP/Work Product:
    - Option A: Client owns all IP created under agreement (with full assignment)
    - Option B: Service Provider retains IP; Client receives license [exclusive/non-exclusive, perpetual/term]
33. Third-Party IP: Service Provider warrants authority to use/sublicense any third-party IP
34. IP Warranties: Service Provider warrants work product does not infringe third-party IP rights

CONFIDENTIALITY (Per common law breach of confidence principles):
35. Definition: Proprietary business, technical, financial information disclosed by either party
36. Obligations: Non-disclosure, non-use except for agreement purposes, reasonable security measures
37. Exceptions: Publicly available, independently developed, rightfully received, legally compelled disclosure
38. Duration: [X years] after termination or perpetual for trade secrets
39. Return: Return or destroy confidential information upon termination

WARRANTIES AND REPRESENTATIONS:
40. Authority: Each party has authority to enter agreement
41. No Conflicts: Agreement does not violate other obligations
42. Workmanlike Performance: Services performed professionally per industry standards
43. Compliance with Laws: Services comply with applicable laws
44. No Infringement: Work product does not infringe third-party rights
45. Disclaimer: EXCEPT AS EXPRESSLY STATED, NO WARRANTIES (EXPRESS OR IMPLIED) INCLUDING MERCHANTABILITY, FITNESS FOR PURPOSE

LIABILITY AND INDEMNIFICATION:
46. Limitation of Liability:
    - NEITHER PARTY LIABLE FOR INDIRECT, CONSEQUENTIAL, SPECIAL, PUNITIVE DAMAGES
    - Liability cap: [X times fees paid in preceding 12 months / $Y amount]
    - Exceptions to cap: Gross negligence, willful misconduct, IP infringement, confidentiality breach, indemnification obligations
47. Indemnification by Service Provider: Indemnify client against third-party claims for IP infringement, personal injury, property damage caused by services
48. Indemnification by Client: Indemnify provider against claims arising from client's misuse of services/deliverables
49. Indemnity Procedures: Notice, control of defense, cooperation requirements

TERMINATION:
50. Termination for Cause: Immediate termination on written notice if:
    - Material breach unremedied for [30] days after written notice
    - Insolvency, bankruptcy, winding up proceedings
    - Breach of confidentiality or IP provisions
51. Termination for Convenience: [X] days' written notice [with/without termination fee]
52. Effect of Termination:
    - Client pays for services performed to termination date plus reasonable wind-down costs
    - Return of property and confidential information
    - Survival of confidentiality, IP, indemnity, liability, dispute resolution clauses
53. Post-Termination Assistance: [If applicable, transition services at [standard/agreed rates]]

DISPUTE RESOLUTION (Singapore International Arbitration Centre - SIAC):
54. Negotiation: Good faith negotiations for [30] days
55. Mediation: Mediation at Singapore Mediation Centre for [X] days
56. Arbitration: SIAC Rules, seat in Singapore, [1/3] arbitrator(s), English language
57. Injunctive Relief: Right to seek interim relief from Singapore courts
58. Costs: Prevailing party entitled to reasonable legal costs

GENERAL PROVISIONS:
59. Entire Agreement: Supersedes all prior agreements; amendments in writing only
60. Assignment: No assignment without consent except to affiliates or in merger/acquisition
61. Subcontracting: Service Provider may subcontract with consent; remains responsible
62. Independent Contractor: Parties are independent contractors, not partners/JV/employer-employee
63. Force Majeure: Excuse for non-performance due to unforeseeable events beyond reasonable control
64. Notices: Written notice to registered addresses or designated email; deemed received [X] days after dispatch
65. Severability: Invalid provisions severed; remainder enforceable
66. Waiver: No waiver unless written; single waiver not continuing
67. Counterparts: May execute in counterparts
68. No Third-Party Beneficiaries: Agreement only for parties' benefit
69. Governing Law: Singapore law (excluding conflicts principles)
70. Jurisdiction: Non-exclusive jurisdiction of Singapore courts

REGULATORY COMPLIANCE:
- Personal Data Protection Act 2012: If processing personal data, include data processing addendum with roles (controller/processor), purposes, security measures, breach notification
- Cybersecurity Act 2018: If critical information infrastructure, ensure compliance
- GST: Service provider must charge GST if registered
- Consumer Protection (Fair Trading) Act: Ensure no unfair practices if consumer services

Please draft with clear headings, defined terms section, schedules for SLAs and fee schedules, and execution blocks for authorized signatories.`,
  },

  // Corporate Documents
  {
    id: 'shareholders-agreement',
    name: 'Shareholders Agreement',
    category: 'Corporate',
    description: 'Agreement governing shareholder rights and obligations',
    prompt: `Draft a comprehensive Shareholders Agreement for a Singapore private limited company in STRICT COMPLIANCE with the Companies Act (Cap. 50):

PARTIES AND COMPANY DETAILS:
1. Company: [Full company name, UEN, incorporation date, registered office]
2. Shareholders: [List all shareholders with NRIC/UEN, addresses, and current shareholdings]
3. Effective Date: [Date]
4. Recitals: Background of company formation and purpose of agreement

SHARE CAPITAL AND STRUCTURE (Section 13, Companies Act):
5. Authorized Share Capital: [Number] shares of $[X] each
6. Issued and Paid-Up Capital: Current shareholding breakdown by shareholder and class
7. Classes of Shares: [Ordinary/Preference] - rights, preferences, privileges per Section 64
8. Share Certificates: Issuance and custody per Section 81
9. Register of Members: Maintenance per Section 190

MANAGEMENT AND BOARD OF DIRECTORS (Part VII, Companies Act):
10. Board Composition:
    - Total directors: [Number] (minimum 1 resident director per Section 145)
    - Appointment rights: [Each shareholder entitled to nominate X directors proportionate to shareholding]
    - Nominee directors: Specific nomination rights for major shareholders
    - Independent directors: [If applicable, number and selection process]
11. Chairman: [Appointment process, casting vote rights]
12. Director Qualifications: Must meet Section 145 requirements (minimum 21 years old, not disqualified)
13. Director Removal: Per Section 152 - ordinary resolution; agreement may impose higher threshold
14. Director Remuneration: Determination process (per Section 169 - requires shareholder approval if exceeded $5,000 p.a.)
15. Quorum: [X] directors minimum for board meetings (Section 153)
16. Board Meetings: Notice periods [X days], frequency [quarterly minimum], voting procedures
17. Written Resolutions: Permitted if all directors consent (Section 165B)

RESERVED MATTERS (Require Special Approval):
18. Matters Requiring Unanimous Shareholder Approval:
    - Amendment to Constitution (Section 26 - special resolution 75%)
    - Alteration of share capital (Section 73)
    - Voluntary winding up (Section 160 - special resolution)
    - Sale of substantial assets (>50% of company assets)
    - Change in nature of business
    - Related party transactions above $[threshold]
    - Borrowing exceeding $[amount]
    - Provision of guarantees/indemnities
    - Merger, acquisition, or restructuring
    - Disposal of IP rights
    - Admission of new shareholders
19. Matters Requiring Supermajority ([75%] Shareholder Approval):
    - Issuance of new shares (subject to pre-emption)
    - Declaration of dividends above [X]% of profits
    - Appointment/removal of auditors
    - Entry into joint ventures or partnerships
    - Capital expenditure exceeding $[amount]

VOTING RIGHTS (Section 179, Companies Act):
20. General Meetings: Annual General Meeting per Section 175 (within 6 months of financial year-end)
21. Extraordinary General Meetings: Per Section 176 - on requisition or director discretion
22. Notice: [21 days for special resolution, 14 days for ordinary resolution] per Section 177
23. Quorum: [2 members or % of shares] per Section 179
24. Voting: One vote per share unless otherwise stated; proxy voting permitted per Section 181
25. Written Resolutions: Permitted if passed by required majority (Section 184A)
26. Casting Vote: [Chairman has/does not have casting vote]

TRANSFER OF SHARES (Must comply with Section 126, Companies Act):
27. Transfer Restrictions: No transfer without compliance with this agreement (private company right per Section 22)
28. Right of First Refusal (ROFR):
    - Transferring shareholder must give notice to other shareholders
    - Offer price and terms specified
    - Existing shareholders have [30] days to accept pro rata to existing holdings
    - If not fully subscribed, offering shareholder may sell to third party on same/better terms
29. Transfer to Permitted Transferees: Exempt from ROFR:
    - Family members (spouse, children, parents, siblings)
    - Trusts for shareholder/family benefit
    - Companies wholly owned by shareholder
    - Upon death to personal representatives/beneficiaries
30. Board Approval: Directors may refuse registration if transfer violates agreement (Section 126)
31. Drag-Along Rights: If [X%] shareholders approve sale, minority must sell on same terms
32. Tag-Along Rights: If majority sells, minority has right to sell proportionately on same terms
33. Transfer Procedures: Instrument of transfer, stamp duty ($0.20 per $100 or 0.2%), registration

PRE-EMPTION RIGHTS ON NEW ISSUANCES (Section 161, Companies Act):
34. Statutory Pre-emption: Section 161 requires offer to existing shareholders pro rata unless disapplied
35. Contractual Pre-emption: Agreement strengthens Section 161:
    - All new share issues offered to existing shareholders pro rata
    - Notice period [30] days with subscription price and terms
    - Unsubscribed shares may be offered to third parties at no better price
36. Exemptions: Employee share option schemes, bonus issues, rights issues
37. Anti-Dilution Protection: Adjustment mechanisms if shares issued below fair value

DIVIDEND POLICY (Section 403, Companies Act):
38. Solvency Test: Dividends only if company solvent per Section 403 (able to pay debts, assets exceed liabilities)
39. Distribution: Directors recommend, shareholders approve by ordinary resolution
40. Timing: [Annual dividend after AGM, interim dividends at directors' discretion]
41. Retained Earnings: [Minimum X% retained for working capital/expansion]
42. Payment: Within [30] days of declaration, pro rata to shareholdings

DEADLOCK RESOLUTION (Critical for Private Companies):
43. Mediation: Good faith mediation at Singapore Mediation Centre for [30] days
44. Independent Expert: Binding determination by [accountant/valuer] on financial disputes
45. Shotgun Clause: If deadlock persists, either shareholder may trigger:
    - Offering shareholder names price for their shares OR to buy other's shares
    - Receiving shareholder must buy OR sell within [60] days at that price
46. Winding Up: Last resort per Section 254(1)(i) - just and equitable winding up

EXIT MECHANISMS:
47. Initial Public Offering (IPO): Process for listing on Singapore Exchange; agreement terminates upon listing
48. Trade Sale: Process for selling entire company to third party (requires [X%] approval)
49. Put Options: [If applicable, minority can require buyback after [Y] years or milestones not met]
50. Call Options: [If applicable, majority can buy out minority after [Y] years or upon cause]
51. Valuation: Fair market value determined by [independent valuer using X methodology, e.g., NAV, P/E multiples]
52. Payment Terms: [Lump sum / installments over X years] with interest at [Y%]

RESTRICTIVE COVENANTS (Must be reasonable to be enforceable):
53. Non-Compete: During shareholding and [X years] after, shareholders shall not engage in competing business within [geographic area]
54. Non-Solicitation: Prohibition on soliciting employees, customers, suppliers for [X years]
55. Confidentiality: Perpetual protection of company trade secrets, financial information, business plans
56. Reasonableness: Must protect legitimate business interests; courts strictly construe restraints (Smile Inc v Lui Andrew Stewart)

FINANCING AND LOANS:
57. Further Funding: Pro rata participation in future funding rounds; consequences of non-participation
58. Shareholder Loans: [If applicable, terms of any shareholder loans - interest rate, repayment, subordination]
59. Guarantees: Shareholders may be required to guarantee company borrowings [up to $X per shareholder]

WARRANTIES AND REPRESENTATIONS:
60. Ownership: Each shareholder warrants they legally and beneficially own their shares free from encumbrances
61. Authority: Each shareholder has authority to enter agreement
62. Compliance: Company in compliance with all laws and regulatory requirements
63. Financial Statements: [If relevant, accuracy of latest accounts]
64. No Litigation: No pending or threatened litigation against company

INFORMATION RIGHTS (Minority Protection):
65. Financial Statements: Audited annual accounts per Section 201 within 5 months of financial year-end
66. Management Accounts: Quarterly unaudited accounts provided within [30] days
67. Inspection Rights: Right to inspect books and records per Section 199
68. Strategic Information: Business plans, budgets, material contracts shared with all shareholders
69. Board Minutes: Copies of board resolutions and minutes provided to shareholders

GENERAL PROVISIONS:
70. Entire Agreement: Supersedes all prior agreements; amendments must be in writing and unanimous
71. Constitution Relationship: To extent of conflict, this agreement prevails as between shareholders
72. Binding on Successors: Agreement binds personal representatives, successors, permitted transferees
73. Notices: Written notice to registered addresses; deemed received [X] days after dispatch
74. Severability: Invalid provisions severed; remainder remains enforceable
75. Waiver: No waiver unless written; single waiver not continuing
76. Counterparts: May execute in counterparts
77. Governing Law: Singapore law
78. Jurisdiction: Non-exclusive jurisdiction of Singapore courts
79. Arbitration: [Alternative: Disputes to arbitration under SIAC Rules if preferred]

COMPANIES ACT COMPLIANCE NOTES:
- Section 25: Constitution binds company and members; shareholders agreement creates contractual obligations
- Section 76A: Financial assistance for share acquisition prohibited unless exemption applies
- Section 126: Company may refuse to register transfer if not duly stamped or violates agreement
- Section 64: Variation of class rights requires special resolution of affected class
- Section 216: Minority oppression remedy if unfairly prejudicial conduct
- Section 254: Court may wind up if just and equitable or unable to carry on business
- Ensure compliance with Foreign Shareholding Restrictions if applicable (Economic Expansion Incentives Act)

Please draft with formal language, clear definitions, schedules for shareholding structure and board composition, and execution blocks.`,
  },
  {
    id: 'resolution',
    name: 'Board Resolution',
    category: 'Corporate',
    description: 'Template for board resolutions',
    prompt: `Draft a Board Resolution in STRICT COMPLIANCE with the Companies Act (Cap. 50), particularly Sections 153, 157A, 165B:

COMPANY INFORMATION:
1. Full Company Name: [Company Name Pte Ltd]
2. Company Registration Number (UEN): [XXXXXX-X]
3. Registered Office: [Address]
4. Type of Resolution: [Board Meeting Resolution / Written Board Resolution per Section 165B]

MEETING DETAILS (If Physical/Virtual Meeting):
5. Date of Meeting: [DD/MM/YYYY]
6. Time: [HH:MM AM/PM]
7. Location: [Physical address / Virtual platform details]
8. Notice: Confirm notice of [X] days given per Constitution and Section 153
9. Chairperson: [Name, NRIC/FIN]

ATTENDANCE AND QUORUM (Section 153):
10. Directors Present:
    - [Name 1, NRIC, Director]
    - [Name 2, NRIC, Director]
    - [Name 3, NRIC, Director]
11. Directors Absent (with apologies):
    - [If any]
12. Quorum: Confirm quorum of [X] directors met per Article [Y] of Constitution (Section 153 requires quorum provisions in Constitution)
13. Secretary/Minute Taker: [Name]

WRITTEN RESOLUTION DETAILS (If Written Resolution per Section 165B):
14. Written Resolution Circulated: [DD/MM/YYYY]
15. Directors Consenting in Writing:
    - [Name 1, NRIC, Signature, Date]
    - [Name 2, NRIC, Signature, Date]
    - [All directors must consent for written resolution]
16. Effective Date: [Date last director signs]

CONFLICTS OF INTEREST DISCLOSURE (Section 156):
17. Directors Required to Declare Interest: [Per Section 156, directors must disclose conflicts in proposed transaction/arrangement]
18. Interested Directors: [Name if any - must not vote per Section 156]
19. Declaration Recorded: [Details of interest disclosed and recorded in minutes]

RESOLUTIONS PASSED (Choose relevant subject):

FOR GENERAL AUTHORIZATIONS:
"IT WAS RESOLVED THAT:
The [Managing Director/CEO/specified officer] be and is hereby authorized to:
[Specific action - e.g., enter into contract, sign documents, open bank account, etc.]
on terms and conditions as they deem fit in the interests of the Company."

FOR BANKING RESOLUTIONS (Opening Account/Changing Signatories):
"IT WAS RESOLVED THAT:
1. The Company open a [Current/Savings] account with [Bank Name]
2. The authorized signatories be: [Name 1, NRIC] and [Name 2, NRIC]
3. Signing authority: [Single signature / Dual signature] for transactions
4. Transaction limits: [Single signature up to $X, Dual signature above $X]
5. [Name/Position] be authorized to execute all account opening documents
6. The bank's standard terms and conditions be accepted"

FOR APPOINTMENT OF DIRECTOR (Section 145):
"IT WAS RESOLVED THAT:
1. [Full Name, NRIC/FIN, Address] be and is hereby appointed as Director of the Company with effect from [Date]
2. [Name] has consented to act as Director and meets requirements of Section 145 (at least 21 years old, not disqualified)
3. [If relevant: Name is/is not ordinarily resident in Singapore per Section 145(1) requirement of at least 1 resident director]
4. The Company Secretary file notice of appointment (Form 45) with ACRA within 14 days per Section 145(4)"

FOR REMOVAL OF DIRECTOR (Section 152):
"IT WAS RESOLVED THAT:
1. [Full Name, NRIC] be and is hereby removed as Director with effect from [Date] in accordance with Section 152
2. [Name] be given notice as required by Constitution
3. The Company Secretary file notice of cessation (Form 45A) with ACRA within 14 days"

FOR ISSUANCE OF SHARES (Section 161):
"IT WAS RESOLVED THAT:
1. The Company issue [Number] new ordinary shares at $[X] per share to [Allottee Name, NRIC]
2. The pre-emption rights under Section 161 have been [complied with / waived by shareholders]
3. The Directors certify the issuance complies with Section 76 (shares not issued at discount)
4. The shares rank pari passu with existing ordinary shares
5. Share certificates be issued and Register of Members updated per Sections 81, 190
6. The Company Secretary file Form 9 (Return of Allotment) with ACRA within 1 month per Section 68"

FOR DECLARATION OF DIVIDENDS (Section 403):
"IT WAS RESOLVED THAT:
1. Subject to shareholder approval, an [interim/final] dividend of $[X] per share be declared
2. The Directors certify the Company is solvent and able to pay its debts per Section 403
3. Total dividend payment: $[Amount]
4. Payment date: [Date] (within [30] days)
5. Dividend payable to shareholders on register as at [Record Date]"

FOR APPROVAL OF FINANCIAL STATEMENTS (Section 201):
"IT WAS RESOLVED THAT:
1. The audited Financial Statements for the financial year ended [DD/MM/YYYY] be and are hereby approved
2. The Financial Statements comply with Singapore Financial Reporting Standards and Companies Act Section 201
3. The Directors' Statement be approved and signed by [2 directors per Section 201(15)]
4. The Financial Statements be presented to shareholders at the AGM"

FOR APPROVAL OF MATERIAL CONTRACTS:
"IT WAS RESOLVED THAT:
1. The Company enter into [Contract Description] with [Counterparty Name]
2. The material terms are: [Brief summary - value, duration, key obligations]
3. The contract is in the interests of the Company and on arm's length commercial terms
4. [Name/Position] be authorized to execute the contract and all related documents on behalf of the Company"

FOR APPOINTMENT OF AUDITORS (Section 205):
"IT WAS RESOLVED THAT:
1. [Audit Firm Name, Registration Number] be appointed as Auditors of the Company
2. The appointment to hold office until conclusion of next AGM
3. The remuneration be fixed at $[Amount] or as agreed between Directors and Auditors
4. The Auditors have confirmed independence and meet Section 205 requirements
5. Subject to shareholder approval at AGM per Section 205(1)"

FOR LOANS/BORROWINGS:
"IT WAS RESOLVED THAT:
1. The Company borrow up to $[Amount] from [Lender]
2. Interest rate: [X]% per annum
3. Security: [Unsecured / Secured by charge over specified assets]
4. Terms: [Repayment schedule, covenants]
5. [Name/Position] be authorized to execute loan agreement and security documents
6. [If creating charge: Particulars be filed with ACRA within 30 days per Section 131]"

FOR REGISTERED OFFICE CHANGE (Section 143):
"IT WAS RESOLVED THAT:
1. The Registered Office be changed from [Old Address] to [New Address] with effect from [Date]
2. The Company Secretary file Form 46 with ACRA within 14 days per Section 143
3. All statutory registers be updated accordingly"

FOR COMPANY SECRETARY APPOINTMENT/REMOVAL (Section 171):
"IT WAS RESOLVED THAT:
1. [Name] be [appointed/removed] as Company Secretary with effect from [Date]
2. [For appointment: Name meets Section 171 qualifications - ordinarily resident in Singapore, natural person]
3. The Company Secretary file Form 49 with ACRA within 14 days per Section 171(1B)"

DIRECTORS' DUTIES ACKNOWLEDGMENT (Section 157):
"The Directors acknowledge their statutory duties under Sections 157-157D:
- Act honestly and use reasonable diligence
- Act in good faith in the interests of the Company
- Avoid conflicts of interest
- Not make improper use of information or position"

FILING AND ADMINISTRATIVE ACTIONS:
"IT WAS FURTHER RESOLVED THAT:
1. The Company Secretary be authorized to file all necessary forms with ACRA
2. Statutory registers be updated to reflect the above resolutions
3. Minutes of this meeting/resolution be entered in the Minute Book per Section 188"

CERTIFICATION (Required for certain resolutions):
"The Directors hereby certify that:
[As applicable: solvency for dividends/capital reduction, pre-emption compliance for share issuance, etc.]"

CLOSURE:
"There being no other business, the meeting was declared closed at [Time]."
OR
"This written resolution is effective on [Date last director signs]."

EXECUTION:
Signed by Directors:

________________________
[Director 1 Name]
[NRIC]
Director
Date:

________________________
[Director 2 Name]
[NRIC]
Director
Date:

Confirmed:
________________________
Company Secretary
[Name]
Date:

COMPLIANCE NOTES:
- Section 153: Quorum and meeting procedures per Constitution
- Section 156: Directors must disclose conflicts; interested directors cannot vote
- Section 157A(3): Directors must keep proper records of resolutions
- Section 165B: Written resolutions valid if ALL directors sign (unlike shareholders where majority suffices per 184A)
- Section 188: Minutes must be kept; prima facie evidence of proceedings
- Directors' Resolutions Circular: Must file with ACRA for specific matters (director changes, registered office, etc.)
- Retain minutes for at least 5 years from date of meeting/resolution

Please customize for specific resolution subject and ensure all statutory requirements met.`,
  },

  // Property & Leases
  {
    id: 'tenancy-agreement',
    name: 'Tenancy Agreement',
    category: 'Property',
    description: 'Residential or commercial lease agreement',
    prompt: `Draft a comprehensive Tenancy Agreement compliant with Singapore property law, including relevant statutes and regulations:

TYPE OF TENANCY: [RESIDENTIAL PRIVATE / HDB / COMMERCIAL]

PARTIES:
1. Landlord: [Full name, NRIC/UEN, address, contact details]
   - If multiple landlords: All names and share of ownership
   - If company landlord: Include UEN and authorized representative
2. Tenant: [Full name, NRIC/FIN, address, contact details]
   - If multiple tenants: All names (joint and several liability)
   - If company tenant: Include UEN and authorized representative
3. Agent (if applicable): [Name, CEA registration number]

PROPERTY DESCRIPTION:
4. Premises: [Full address including unit number, postal code]
5. Property Type: [HDB flat / Private condominium / Landed property / Commercial shop / Office unit / Industrial unit]
6. Floor Area: [Approximately X square feet/meters]
7. Furnishing: [Unfurnished / Partially furnished / Fully furnished] - attach inventory list as Schedule
8. Facilities (for condominiums): Access to [swimming pool, gym, parking lot number X, etc.]
9. Parking: [X car park lot(s) - lot number(s)]

TERM AND COMMENCEMENT (Critical for enforceability):
10. Commencement Date: [DD/MM/YYYY]
11. Expiry Date: [DD/MM/YYYY]
12. Lease Period: [X] months/years fixed term
13. Option to Renew: [Tenant has option to renew for [X] period(s) on [same terms / revised rent] with [X] months' written notice]
14. Break Clause: [If applicable - either party may terminate on [X] months' notice after minimum [Y] months, with/without penalty]

RENT AND DEPOSIT:
15. Monthly Rent: $[Amount] payable in advance by [1st/7th] day of each month
16. First Payment: First month's rent of $[Amount] payable upon signing
17. Payment Method: Bank transfer to Landlord's account [Bank, Account Number] or [PayNow/other]
18. Late Payment: Interest at [X]% per month on overdue rent; grace period [X] days
19. Security Deposit: [Typically 1-2 months for residential, 2-3 months for commercial] = $[Amount]
    - Purpose: Security for rent, damages, breaches
    - Held by: [Landlord / Agent in stakeholder account]
    - Return: Within [14-30] days after expiry and vacant possession, less deductions for damages/arrears
    - Interest: [Deposit does not bear interest unless otherwise stated]
20. Stamp Duty: $[Calculate: Average annual rent × 4 × 0.4%]
    - Responsibility: [Typically shared equally between Landlord and Tenant, or specify split]
    - Timing: Within 14 days of execution (Stamp Duties Act)
    - E-Stamping: Agreement must be stamped with IRAS; unstamped agreements inadmissible as evidence

PERMITTED USE (Critical for compliance):
FOR RESIDENTIAL:
21. Use: Solely for residential occupation by Tenant and [X] persons maximum
22. Occupants: [List names of all occupants including family members]
23. Prohibited Uses:
    - No commercial, business, or trade activities
    - No illegal activities or immoral purposes
    - No subletting without written consent (especially for HDB - subject to MOM approval for foreign tenants)
    - No overcrowding beyond maximum occupancy
24. HDB-Specific (if HDB flat):
    - Compliance with HDB regulations and eligibility rules
    - Minimum Occupation Period (MOP) fulfilled by owner
    - Tenant citizenship requirements: [Citizens, PRs, foreigners with MOM approval]
    - Maximum rental period: [HDB flats maximum 3 years for non-citizens]
    - HDB registration: Landlord must inform HDB within 7 days of commencement

FOR COMMERCIAL:
21. Use: For the purposes of [specific business activity] only
22. Licensing: Tenant responsible for obtaining all licenses, permits, approvals (e.g., URA Change of Use, food license, etc.)
23. Compliance: Must comply with URA guidelines, zoning restrictions, JTC regulations (if industrial)
24. Prohibited Uses: [Specify restricted activities]

MAINTENANCE AND REPAIRS (Section 63, Conveyancing and Law of Property Act):
25. Landlord's Obligations:
    - Maintain structural integrity (walls, roof, foundation)
    - Ensure compliance with building codes and safety regulations
    - Maintain common property (if applicable)
    - Major repairs: [Air-conditioning compressor, water heater, built-in appliances]
26. Tenant's Obligations:
    - Keep premises in clean and tenantable condition
    - Minor repairs and maintenance: [Light bulbs, tap washers, air-con servicing, pest control]
    - Repair damage caused by Tenant's negligence or misuse
    - Fair wear and tear excepted
27. Notification: Tenant must promptly notify Landlord of defects requiring repair
28. Access: Tenant must permit Landlord reasonable access for inspections and repairs with [24/48] hours' notice

UTILITIES AND OUTGOINGS:
29. Utilities: Tenant responsible for [electricity, water, gas, internet, TV license]
30. Service & Conservancy Charges: [Tenant / Landlord] responsible for monthly S&C charges
31. Property Tax: Landlord responsible (owner-occupier rate if tenant pays, non-owner occupier rate if Landlord pays)
32. Account Transfer: Tenant to open utility accounts in own name; revert to Landlord upon expiry
33. Arrears: Tenant liable for all arrears; Landlord may deduct from deposit

INSURANCE:
34. Building Insurance: Landlord maintains fire and structural insurance
35. Contents Insurance: Tenant strongly advised to obtain insurance for personal belongings
36. Public Liability: [Tenant to obtain public liability insurance of $[X] for commercial tenancies]
37. Proof: Tenant to provide proof of insurance if required

ALTERATIONS AND ADDITIONS:
38. Prohibition: No structural alterations, additions, or modifications without Landlord's prior written consent
39. Minor Alterations: [Painting, picture hanging with consent; Tenant to reinstate upon expiry if required]
40. Approval: Any alterations requiring HDB/MCST/URA approval must be obtained by Tenant at Tenant's cost
41. Reinstatement: Tenant to reinstate premises to original condition upon expiry (fair wear and tear excepted)

ASSIGNMENT AND SUBLETTING:
42. Assignment: Tenant may not assign this Agreement without Landlord's written consent
43. Subletting:
    - For private residential: Subletting with Landlord's written consent; must comply with URA rules (minimum 3 months)
    - For HDB: Subletting requires HDB approval; owner must maintain own occupation
    - For commercial: [Permitted / Prohibited]
44. Conditions: If subletting permitted, Tenant remains liable for all obligations; subtenant must comply with terms

LANDLORD'S COVENANTS:
45. Quiet Enjoyment: Tenant entitled to quiet enjoyment of premises without interruption from Landlord
46. Valid Title: Landlord warrants authority to lease and premises free from encumbrances affecting tenancy
47. Statutory Compliance: Premises comply with building, fire safety, and other statutory requirements

TENANT'S COVENANTS:
48. Rent Payment: Pay rent punctually without demand, deduction, or set-off
49. Compliance: Comply with all laws, by-laws, MCST rules, HDB regulations, URA guidelines
50. Good Conduct: Not cause nuisance, disturbance, or annoyance to neighbors
51. Rules & Regulations: Abide by condominium MCST by-laws / HDB regulations
52. Indemnity: Indemnify Landlord against claims arising from Tenant's use/occupation

TERMINATION AND RENEWAL:
53. Natural Expiry: Agreement ends on Expiry Date; no automatic renewal unless option exercised
54. Early Termination by Tenant: [X] months' written notice and payment of [X] months' rent as penalty / or diplomatic clause if expatriate
55. Early Termination by Landlord: Only for material breach after notice or if premises required for own use with [X] months' notice
56. Breach: Either party may terminate immediately upon material uncured breach (e.g., rent arrears >14 days, illegal use)
57. Handover: Tenant to deliver vacant possession in good condition on expiry with all keys, access cards

DEFAULT AND REMEDIES:
58. Landlord's Remedies for Tenant Default:
    - Forfeit deposit and claim additional damages
    - Re-enter premises and terminate tenancy
    - Sue for rent arrears and damages
    - Distress for rent (commercial tenancies)
59. Tenant's Remedies for Landlord Default:
    - Rent abatement for uninhabitable conditions
    - Right to repair and deduct costs (with notice)
    - Claim for damages
60. Statutory Protection: Residential tenants may seek relief under Rental Housing Act (if enacted)

NOTICES:
61. Service: All notices in writing to addresses stated or as updated
62. Methods: Hand delivery, registered post, email to designated addresses
63. Deemed Receipt: [2] days after posting / immediate if hand-delivered

GENERAL PROVISIONS:
64. Entire Agreement: Supersedes all prior agreements; amendments in writing only
65. Severability: Invalid provisions severed; remainder enforceable
66. Waiver: No waiver unless written; single waiver not continuing
67. Governing Law: Singapore law
68. Jurisdiction: Singapore courts
69. Counterparts: May execute in counterparts

SPECIAL CONDITIONS (if applicable):
70. Diplomatic Clause: [For expatriate tenants - early termination with [X] months' notice if employment terminated/relocated]
71. Renewal Terms: [Specify rent review mechanism, e.g., market rate, X% increase]
72. Agency Commission: [Typically 1 month's rent, split between parties or borne by Landlord]

SCHEDULES:
Schedule 1: Inventory and Condition Report (with photos)
Schedule 2: MCST By-Laws / House Rules (if applicable)
Schedule 3: Utility Readings at Commencement

REGULATORY COMPLIANCE:
- Stamp Duties Act: Must stamp within 14 days; duty 0.4% of 4× average annual rent
- URA Guidelines: Residential properties minimum 3 consecutive months rental; commercial as per zoning
- HDB Regulations: Inform HDB within 7 days; comply with ethnic quotas, citizenship requirements, owner occupation
- Controller of Residential Property Act: Foreigners need approval for certain landed properties
- Property Tax Act: Tax payable by owner; rates differ based on occupancy
- Fire Safety Act: Landlord must ensure fire safety compliance
- Personal Data Protection Act: Protect personal information exchanged

Please draft with formal language, clear definitions, execution blocks, and attach all schedules. Both parties should seek independent legal advice before signing.`,
  },

  // Commercial Agreements
  {
    id: 'loan-agreement',
    name: 'Loan Agreement',
    category: 'Finance',
    description: 'Agreement for lending money',
    prompt: `Draft a comprehensive Loan Agreement compliant with Singapore law, with CRITICAL attention to the Moneylenders Act 2008:

CRITICAL MONEYLENDERS ACT COMPLIANCE WARNING:
The Moneylenders Act 2008 STRICTLY REGULATES moneylending in Singapore. Unlicensed moneylending is a CRIMINAL OFFENCE.

EXEMPTIONS from Moneylenders Act (Section 2, Excluded Moneylenders):
- Banks licensed under Banking Act / MAS Act
- Finance companies licensed under Finance Companies Act
- Pawnbrokers licensed under Pawnbrokers Act
- Bodies corporate lending to subsidiaries/related corporations
- Insurance companies
- Persons lending to employees at <4% interest
- Individuals/bodies lending solely to accredited investors or other exempt persons
- Lending <$100,000 to relatives or private arrangements (if not systematic business)

IF LENDER IS NOT EXEMPT: Must be licensed under Moneylenders Act or loan may be UNENFORCEABLE and parties may face criminal penalties.

PARTIES:
1. Lender: [Full name/company name, NRIC/UEN, address]
   - Status: [Licensed Moneylender License No. / Bank / Exempt under Section 2 as [category]]
   - If individual: Confirm lending is not systematic business of moneylending
2. Borrower: [Full name/company name, NRIC/UEN, address, occupation/business]
   - If company: Directors to provide personal guarantees (attach separate Guarantee Deed)
3. Guarantor(s): [If applicable - Name, NRIC, address] (attach Deed of Guarantee as Schedule)

LOAN DETAILS:
4. Principal Amount: $[Amount] (in words: [Amount in words])
5. Purpose: [Specify: business expansion, working capital, personal use, property purchase, etc.]
   - Restriction: Borrower shall use loan solely for stated purpose
6. Disbursement:
   - Date: [DD/MM/YYYY] or upon satisfaction of conditions precedent
   - Method: Bank transfer to Borrower's account [Bank, Account Number]
   - Tranches: [If applicable, staggered disbursement schedule]

INTEREST RATE (Critical for Moneylenders Act compliance):
7. Interest Rate: [X]% per annum
   - For Licensed Moneylenders: CAPPED at 4% per month (48% per annum) per Moneylenders Rules 2009, Rule 11
   - Calculation Method: [Simple interest / Reducing balance] on outstanding principal
   - Interest Period: [Monthly / Quarterly] in arrears
8. Default Interest: [Y]% per annum on overdue amounts (total interest+default interest cannot exceed cap)
9. Moneylenders Act Cap: Per Section 23, aggregate of interest, late fees, and permitted fees CANNOT exceed principal for unsecured loans
10. Total Interest Over Loan Term: $[Amount] (clearly disclosed per transparency requirements)

REPAYMENT TERMS:
11. Repayment Period: [X] months/years from Disbursement Date
12. Repayment Schedule:
    - [Monthly/Quarterly] installments of $[Amount] (principal + interest)
    - First payment due: [Date]
    - Subsequent payments: [Xth] day of each [month/quarter]
13. Payment Method: Bank transfer / GIRO to Lender's account [Details]
14. Prepayment: Borrower may prepay in full/part [with/without penalty]
    - Prepayment Penalty: [X% of prepaid amount or Nil] - For Licensed Moneylenders: capped per Moneylenders Rules
15. Final Payment: All outstanding principal, interest, fees due on [Maturity Date]

FEES AND CHARGES (Moneylenders Act Restrictions):
16. Upfront Fees:
    - Arrangement/Processing Fee: $[Amount] or [X]% of principal (For Licensed Moneylenders: Max 10% of principal per Rule 12)
    - Legal Fees: [If applicable, borne by Borrower with cap]
    - Valuation Fees: [If secured loan]
17. Late Payment Fee: $[Amount] per late payment (For Licensed Moneylenders: Max $60 per month per Rule 13)
18. Permitted Fees ONLY: No other fees chargeable; hidden fees PROHIBITED
19. Total Fees Disclosure: Total fees over loan term = $[Amount]

SECURITY AND COLLATERAL:
20. Security Type: [Unsecured / Secured]
21. If Secured:
    - Collateral: [Description - property, shares, fixed deposit, equipment, etc.]
    - Valuation: Independent valuation at $[Amount]; Loan-to-Value ratio [X]%
    - Documentation: [Mortgage / Charge / Pledge] to be executed concurrently
    - Registration: [If property charge, register with Singapore Land Authority; if company charge, file with ACRA within 30 days per Section 131 Companies Act]
    - Insurance: Borrower to maintain insurance covering collateral value; Lender named as loss payee
22. Personal Guarantee: [If applicable, directors/third parties to execute Guarantee Deed - attach as Schedule]

REPRESENTATIONS AND WARRANTIES (By Borrower):
23. Authority: Legal capacity and authority to borrow and execute agreement
24. Financial Information: All financial information provided is accurate and complete
25. No Litigation: No pending/threatened litigation that would impair repayment ability
26. Compliance: In compliance with all laws; not subject to insolvency proceedings
27. Use of Proceeds: Loan used solely for stated purpose; not for illegal activities
28. No Default: Not in default under other loan agreements

CONDITIONS PRECEDENT (Before Disbursement):
29. Execution of Agreement and security documents
30. Receipt of satisfactory due diligence, credit checks, financial statements
31. Proof of intended use of loan proceeds
32. Insurance policies (if secured loan)
33. Board resolutions authorizing borrowing (if corporate Borrower)
34. Payment of upfront fees

AFFIRMATIVE COVENANTS (Borrower shall):
35. Use loan proceeds solely for stated purpose
36. Maintain books and records; provide financial statements [annually/quarterly]
37. Pay all taxes, fees, and obligations when due
38. Maintain insurance on collateral (if secured)
39. Notify Lender of material adverse changes, litigation, defaults
40. Maintain corporate existence and good standing (if company)
41. Comply with all applicable laws

NEGATIVE COVENANTS (Borrower shall not, without Lender consent):
42. Incur additional debt beyond $[Amount]
43. Create additional security interests on assets
44. Dispose of substantial assets
45. Change nature of business or undergo restructuring
46. Declare dividends if in default
47. Engage in transactions with related parties on non-arm's length terms

EVENTS OF DEFAULT (Entitle Lender to accelerate loan):
48. Non-Payment: Failure to pay any installment within [X] days of due date
49. Breach of Covenants: Material breach of any covenant unremedied for [X] days
50. Misrepresentation: Any representation/warranty proves false or misleading
51. Cross-Default: Default under other loan agreements
52. Insolvency: Bankruptcy, winding up, receivership, insolvency proceedings
53. Material Adverse Change: Significant deterioration in Borrower's financial condition
54. Loss of Licenses: Loss of critical business licenses or approvals
55. Judgment: Unsatisfied judgment against Borrower exceeding $[Amount]

REMEDIES UPON DEFAULT:
56. Acceleration: All outstanding principal, interest, fees immediately due and payable
57. Enforcement of Security: Lender may enforce security and sell collateral
58. Legal Action: Sue for outstanding amounts plus costs on indemnity basis
59. Set-Off: Lender may set off amounts owed from any deposits/accounts
60. Appointment of Receiver: [If secured, right to appoint receiver over collateral]
61. Default Interest: Charge default interest on all overdue amounts

FEES, COSTS, AND EXPENSES:
62. Borrower pays all costs: Legal fees, stamp duty, registration fees, enforcement costs
63. Stamp Duty: Loan agreements subject to stamp duty of $0.40 per $1000 or fractional part (Stamp Duties Act)
    - Responsibility: [Borrower / shared equally]
    - Timing: Within 14 days of execution
64. Recovery Costs: Borrower liable for all costs of enforcement including legal fees on indemnity basis

NOTICE AND COMMUNICATION:
65. Notices: Written notice to addresses stated; deemed received [2] days after posting
66. Change of Address: Parties must notify of address changes
67. Methods: Registered post, hand delivery, email to designated addresses

GENERAL PROVISIONS:
68. Entire Agreement: Supersedes all prior agreements; amendments in writing only
69. Severability: Invalid provisions severed; remainder enforceable
70. Waiver: No waiver unless written; single waiver not continuing
71. Assignment: Lender may assign; Borrower may not assign without consent
72. Currency: All amounts in Singapore Dollars
73. Business Days: If payment date falls on non-business day, payable on next business day without additional interest
74. Governing Law: Singapore law
75. Jurisdiction: Non-exclusive jurisdiction of Singapore courts
76. Arbitration: [Alternative: Disputes to SIAC arbitration if preferred]

CONSUMER CREDIT PROTECTIONS (If applicable):
77. Cooling-Off Period: [For certain consumer loans, right to cancel within specified period]
78. Debt Collection: Per Moneylenders Rules, licensed moneylenders prohibited from harassment, restricted visitation hours
79. Disclosure Requirements: Lender must provide Note of Contract per Moneylenders Rules within 7 days

MANDATORY DISCLOSURE (For Licensed Moneylenders per Moneylenders Rules):
80. Effective Interest Rate (EIR): [X]% (includes all fees and interest)
81. Total Amount Repayable: $[Principal + Interest + Fees]
82. Statement of Account: Provided within 7 days on request
83. Contact Information: [Lender's licensed business address, phone, email, license number]

EXECUTION BLOCKS:
Signed by LENDER:

________________________
[Name]
[NRIC/UEN]
[Position if company]
Date:

Signed by BORROWER:

________________________
[Name]
[NRIC/UEN]
[Position if company]
Date:

Witnessed by:

________________________
[Witness Name, NRIC]
Date:

SCHEDULES:
Schedule 1: Repayment Schedule with dates and amounts
Schedule 2: Deed of Guarantee (if applicable)
Schedule 3: Security Documents (Mortgage/Charge)

STATUTORY COMPLIANCE NOTES:
- Moneylenders Act 2008: PROHIBITS unlicensed moneylending; breaches subject to fines up to $300,000 and/or imprisonment up to 4 years
- Moneylenders Rules 2009: Cap on interest (4% per month), fees (10% upfront, $60 late fee), total interest cannot exceed principal for unsecured loans
- Stamp Duties Act: Must stamp within 14 days; unstamped documents inadmissible as evidence
- Companies Act Section 131: Register charges within 30 days
- Banking Act: Only licensed banks may accept deposits from public
- Personal Data Protection Act: Protect Borrower's personal information

CRITICAL WARNING: Both parties should seek independent legal and financial advice. If Lender is not exempt under Moneylenders Act, they MUST obtain moneylender license before entering this agreement.`,
  },
  {
    id: 'partnership',
    name: 'Partnership Agreement',
    category: 'Corporate',
    description: 'Agreement for business partnership',
    prompt: `Draft a comprehensive Partnership Agreement governed by the Partnership Act (Cap. 391) and compliant with Singapore law:

PARTNERSHIP INFORMATION:
1. Partnership Name: [Trading Name]
   - Note: Not a separate legal entity; partners personally liable
   - Registration: Register with ACRA if using business name under Business Names Registration Act
2. Type of Partnership: [General Partnership / Limited Partnership / Limited Liability Partnership]
   - For LLP: Separately governed by Limited Liability Partnerships Act - use LLP Agreement template instead
3. Principal Place of Business: [Address]
4. Nature of Business: [Detailed description of business activities]

PARTNERS (Section 1, Partnership Act - minimum 2, maximum 20 except for professional firms):
5. Partner Details:
   - Partner 1: [Full name, NRIC, address, contact, capital contribution $X, profit share Y%]
   - Partner 2: [Full name, NRIC, address, contact, capital contribution $X, profit share Y%]
   - [Continue for all partners]
6. Types of Partners (if applicable):
   - Active/Managing Partners: [Names] - full management rights
   - Sleeping/Dormant Partners: [Names] - capital only, no management
   - For Limited Partnership: General Partners [Names] (unlimited liability) and Limited Partners [Names] (liability limited to capital)

COMMENCEMENT AND DURATION:
7. Commencement Date: [DD/MM/YYYY]
8. Duration: [Fixed term of X years / At-will partnership continuing until dissolved]
9. Financial Year End: [DD/MM] annually

CAPITAL CONTRIBUTIONS (Section 24, Partnership Act):
10. Initial Capital:
    - Total: $[Amount]
    - Individual Contributions: [Partner 1: $X, Partner 2: $Y, etc.]
    - Payment: Due by [Date] via [bank transfer to partnership account]
11. Additional Capital: If required, partners contribute proportionately to profit-sharing ratios; failure to contribute may result in [reduced profit share / forced buyout]
12. Capital Accounts: Separate capital account maintained for each partner showing contributions, drawings, profit/loss share
13. Interest on Capital: [X% per annum / No interest] payable on capital balances
14. Drawings: Partners may draw up to $[Amount] per month against anticipated profits; excess requires all partners' consent

PROFIT AND LOSS SHARING (Section 24, Partnership Act - default equal unless otherwise agreed):
15. Profit Distribution: [Partner 1: Y%, Partner 2: Z%, etc.] OR [Equal shares]
16. Loss Allocation: [Same ratio as profits / specify if different]
17. Distribution Timing: [Quarterly / Annually] after retention of [X%] for reserves/working capital
18. Undistributed Profits: Credited to partners' capital accounts
19. Priority Payments: Before profit distribution:
    - Interest on capital (if applicable)
    - Salaries to active partners (if specified)
    - Remainders distributed per profit-sharing ratios

MANAGEMENT AND DECISION-MAKING (Section 24(5), (8) - ordinary matters by majority; changes require unanimous consent):
20. Management Structure:
    - Managing Partner(s): [Names] with authority for day-to-day operations
    - All partners may participate in management unless otherwise restricted
21. Ordinary Decisions (Majority Vote):
    - Routine business operations, contracts <$[Amount], hiring non-senior staff
22. Unanimous Decisions Required (Section 24(8)):
    - Admission of new partners
    - Change in nature of business
    - Disposal of partnership assets beyond ordinary course
    - Expulsion of a partner (unless expressly agreed otherwise)
    - Amendment of this Agreement
    - Borrowing exceeding $[Amount]
    - Relocation of principal business
23. Partner Meetings: [Monthly/Quarterly] meetings; quorum [X] partners; written notice [Y] days in advance
24. Voting: One vote per partner [OR weighted by capital contribution / profit share]
25. Written Resolutions: Valid if signed by required majority/unanimity

DUTIES AND RESTRICTIONS OF PARTNERS (Sections 28-30, Partnership Act - fiduciary duties):
26. Fiduciary Duties (Section 29):
    - Act in good faith for partnership benefit
    - Render true accounts and full information
    - Account for any benefit derived from partnership transactions
    - Not compete with partnership without consent
27. Time and Attention: Partners to devote [full-time / specified hours] to partnership business
28. Prohibited Acts Without Consent:
    - Engage in competing business
    - Use partnership property/confidential information for personal benefit
    - Enter partnership obligations outside ordinary business
    - Admit liability in legal proceedings
    - Compromise partnership debts
29. Authority Limits: Individual partners may bind partnership within ordinary business (Section 5); limits on authority: [contracts >$X require all partners' consent]
30. Indemnity: Partners indemnify partnership for losses from unauthorized acts or breach of duties

BANKING AND ACCOUNTS (Section 24(9), Partnership Act - partnership books at registered office):
31. Bank Account: [Bank name, account number] requiring [single / dual / all] partner signatures for transactions [above $X]
32. Accounting Records: Maintain proper books per Singapore Financial Reporting Standards; accessible to all partners (Section 24(9))
33. Financial Statements: Audited annual accounts prepared within [X] months of year-end
34. Tax Returns: File partnership tax returns with IRAS; partners individually taxed on profit shares (partnership not a taxable entity)

ADMISSION OF NEW PARTNERS (Section 24(7) - requires unanimous consent):
35. Admission Procedure: Unanimous consent of existing partners required
36. Terms: New partner's capital contribution, profit share, rights determined by amended agreement
37. Liability: New partner liable for partnership debts only from admission date unless agrees otherwise (Section 17)
38. Amendment: Agreement amended to reflect new partner's terms

RETIREMENT/WITHDRAWAL OF PARTNERS (Sections 25-26, Partnership Act):
39. Voluntary Retirement: Partner may retire on [X months] written notice [or immediate if unanimous consent]
40. Compulsory Retirement: Upon [death, bankruptcy, mental incapacity, breach of agreement, age X]
41. Valuation: Retiring partner's share valued at [net asset value / fair market value] by independent valuer as at retirement date
42. Payment: Buyout paid in [lump sum / installments over X years] with interest at [Y%]
43. Outgoing Partner's Liability: Continues for debts incurred while a partner unless novation with creditors (Section 36)
44. Notice to Creditors: Partnership must advertise retirement in Government Gazette to limit outgoing partner's future liability (Section 36)

EXPULSION OF PARTNERS (Requires express provision):
45. Grounds for Expulsion:
    - Material breach of agreement unremedied after [X] days' notice
    - Bankruptcy or insolvency
    - Criminal conviction involving dishonesty
    - Gross misconduct or neglect
    - Incapacity for >6 months
46. Procedure: [Supermajority / Unanimous] vote of other partners; fair hearing opportunity
47. Consequences: Treated as compulsory retirement; valuation and payment per retirement provisions

DISSOLUTION OF PARTNERSHIP (Sections 32-44, Partnership Act):
48. Dissolution Events (Automatic per Section 33 unless otherwise agreed):
    - Expiry of fixed term
    - Completion of specified purpose
    - Death or bankruptcy of any partner (can be excluded by agreement - partnership continues)
    - Illegality of partnership business
    - Court order under Section 35 (just and equitable, incapacity, misconduct, losses, etc.)
49. Voluntary Dissolution: By unanimous consent at any time
50. Dissolution Procedure (Sections 38-44):
    - Cease new business; wind up existing affairs
    - Realize partnership assets
    - Pay debts and liabilities (external creditors have priority)
    - Distribute surplus: Return capital contributions, then remaining per profit-sharing ratios (Section 44)
51. Appointment of Liquidator: [If necessary, partners may appoint liquidator or apply to court]

RESTRICTIVE COVENANTS (Must be reasonable):
52. Non-Compete: During partnership and [X years] after withdrawal/expulsion, partners shall not engage in [competing business] within [geographic area]
53. Non-Solicitation: [X years] prohibition on soliciting partnership clients, suppliers, employees
54. Confidentiality: Perpetual obligation to protect partnership trade secrets, financial information, client lists
55. Enforceability: Must protect legitimate interests; courts strictly interpret restraints of trade

DISPUTE RESOLUTION:
56. Good Faith Negotiation: [30] days of direct negotiations
57. Mediation: Singapore Mediation Centre mediation for [30] days
58. Arbitration: SIAC arbitration under SIAC Rules, seat in Singapore, 1 arbitrator, English language
59. Injunctive Relief: Right to seek urgent interim relief from Singapore courts
60. Costs: Prevailing party entitled to reasonable costs

DEATH OF PARTNER (Section 33, Partnership Act - dissolves partnership unless excluded):
61. Continuation: Partnership continues with remaining partners; deceased partner's estate treated as retired partner
62. Valuation: Share valued as at date of death
63. Payment to Estate: [Lump sum within X months / Installments] with interest
64. Life Insurance: Partners to maintain life insurance of $[Amount] to fund buyout; policies held in trust for partnership

INSURANCE:
65. Partnership Insurance: Professional indemnity, public liability, property, business interruption insurance
66. Key Person Insurance: On lives of key partners to protect partnership
67. Premium Payment: Shared per profit-sharing ratios

INTELLECTUAL PROPERTY:
68. Partnership IP: All IP created in partnership business vests in partnership
69. Existing IP: Partners' pre-existing IP remains individual property; licensed to partnership
70. Post-Dissolution: IP rights distributed or licensed per dissolution terms

GENERAL PROVISIONS:
71. Entire Agreement: Supersedes all prior agreements; amendments in writing signed by all
72. Severability: Invalid provisions severed; remainder enforceable
73. Waiver: No waiver unless written; single waiver not continuing
74. Notices: Written notice to registered addresses; deemed received [2] days after posting
75. Governing Law: Partnership Act (Cap. 391) and Singapore law
76. Jurisdiction: Non-exclusive jurisdiction of Singapore courts
77. Counterparts: May execute in counterparts

COMPLIANCE AND REGULATORY:
- Partnership Act (Cap. 391): Governs all partnerships; partners have unlimited joint and several liability for partnership debts
- Business Names Registration Act: Register if using business name other than partners' names
- Income Tax Act: Partnership files informational return; partners taxed individually on profit shares
- ACRA Registration: Register partnership changes (partners, address) within 14 days
- For Professionals: Comply with professional regulatory requirements (e.g., Law Society for law firms)

EXECUTION:
Signed by Partners:

________________________
[Partner 1 Name, NRIC]
Date:

________________________
[Partner 2 Name, NRIC]
Date:

[Continue for all partners]

Please draft with clear schedules for capital contributions, profit-sharing, and attach partnership registration documents.`,
  },

  // Dispute Resolution
  {
    id: 'settlement-agreement',
    name: 'Settlement Agreement',
    category: 'Dispute Resolution',
    description: 'Agreement to settle disputes',
    prompt: `Draft a comprehensive Settlement Agreement to resolve disputes in accordance with Singapore law and court procedures:

PARTIES:
1. Plaintiff/Claimant: [Full name/company name, NRIC/UEN, address]
   [If litigation commenced: "Plaintiff in [Court] Suit No. [X/YYYY]"]
2. Defendant/Respondent: [Full name/company name, NRIC/UEN, address]
   [If litigation commenced: "Defendant in [Court] Suit No. [X/YYYY]"]
3. Other Parties: [If multi-party dispute, list all parties]

RECITALS (Background of Dispute):
A. Nature of Dispute: [Describe: breach of contract, tort claim, employment dispute, shareholder dispute, etc.]
B. Facts: [Brief chronology of events giving rise to dispute]
C. Legal Proceedings: [If applicable: "Writ of Summons filed on [Date] in [High Court/State Courts/Employment Claims Tribunals] as Suit No. [X/YYYY]" OR "Pre-litigation dispute"]
D. Claims: [Plaintiff's claims for damages/specific performance/injunction of $[Amount] or other relief]
E. Defence: [Defendant's defences and/or counterclaims]
F. Mediation: [If applicable: "Parties attended mediation at [Singapore Mediation Centre/Court Dispute Resolution] on [Date]"]
G. Settlement Intent: Parties desire to settle all disputes amicably without admission of liability

SETTLEMENT TERMS:
1. Settlement Payment (if applicable):
   - Amount: $[Amount] (in words: [Amount in words])
   - Payer: [Party name]
   - Payee: [Party name]
   - Payment Terms:
     * [Lump sum / Installments]: $[X] on [Date], $[Y] on [Date], etc.
     * Method: Bank transfer to [Account details] / Cashier's order
     * Receipt: Within [X] days of each payment
2. Non-Monetary Terms:
   - Specific Performance: [If applicable: Defendant to deliver goods, transfer property, etc.]
   - Injunctive Relief: [If applicable: Cease specified conduct, remove defamatory content, etc.]
   - Reinstatement: [For employment: Employee reinstated to position of [X] effective [Date]]
   - Apology: [If applicable: Public/private apology in specified form]
   - Return of Property: [List items to be returned]
3. Timelines: All obligations to be performed by [Date(s)]

RELEASE AND DISCHARGE (Critical for finality):
4. Mutual Release: Upon full performance of settlement terms:
   - Each party fully and forever releases the other from all claims, demands, actions, causes of action (whether known or unknown, suspected or unsuspected) arising from or related to [the contract dated X / the incident on Y / the employment relationship / etc.]
   - Release extends to parties' officers, directors, employees, agents, successors, assigns
5. Scope of Release: [Broad general release / Narrow release limited to specific claims]
6. Claims Released: Including but not limited to:
   - [Breach of contract, negligence, defamation, wrongful dismissal, etc. - specify]
   - All statutory claims under [relevant Acts]
   - All common law claims
7. Claims Expressly Reserved: [If any claims not being settled, explicitly exclude]
8. Waiver of Unknown Claims: Parties acknowledge they may discover facts different from those believed true and agree release remains effective

NO ADMISSION OF LIABILITY:
9. Without Prejudice: This Agreement is a compromise without admission of liability, wrongdoing, or fault by any party
10. Not Precedent: Settlement not to be construed as admission or used as evidence in any other proceedings except enforcement of this Agreement
11. Not Evidence: Inadmissible in any proceedings except enforcement actions per Section 23, Evidence Act (without prejudice communications)

CONFIDENTIALITY (Enforceable as contractual obligation):
12. Confidential Terms: Terms of this Agreement (including settlement amount) shall remain strictly confidential
13. Non-Disclosure: Parties shall not disclose to any third party except:
    - Legal/financial advisors under confidentiality obligations
    - As required by law, court order, regulatory authority (with advance notice if possible)
    - For enforcement purposes
    - Accountants for tax/audit purposes
14. Public Statement: [If applicable: Agreed joint statement: "[Text]" - no other public comment]
15. Consequences of Breach: Confidentiality breach entitles innocent party to liquidated damages of $[Amount] and/or injunctive relief

DISCONTINUANCE/WITHDRAWAL OF PROCEEDINGS (If litigation commenced):
16. Discontinuance: Plaintiff to file Notice of Discontinuance in [Court] Suit No. [X/YYYY] within [7] days of full settlement payment
17. Costs: [Each party to bear own costs / Defendant to pay Plaintiff's costs of $[Amount]]
18. Consent Order: [Alternative: Parties to apply for Consent Order on terms of settlement - provides enforcement mechanism through court]
19. Stay of Proceedings: Pending settlement, proceedings stayed by consent
20. Other Proceedings: [Any related proceedings, complaints to authorities, police reports to be withdrawn]

DEFAULT AND ENFORCEMENT:
21. Default: If any party fails to comply with settlement terms:
    - Innocent party may enforce this Agreement as a contract
    - Specific performance and/or damages available
    - Legal costs on indemnity basis payable by defaulting party
22. Consent Judgment: [If Consent Order obtained, may enforce as court judgment - immediate execution/garnishment]
23. Reservation of Rights: Upon default, innocent party may [elect to enforce settlement OR revive original claims with settlement payments deductible from final judgment]

REPRESENTATIONS AND WARRANTIES:
24. Authority: Each party has full authority to enter this Agreement
25. No Insolvency: No insolvency proceedings pending or threatened
26. Binding Effect: Agreement binding on parties and successors/assigns
27. Independent Advice: Each party has had opportunity to obtain independent legal advice
28. Voluntary: Agreement entered into freely, voluntarily, without duress or undue influence

GENERAL PROVISIONS:
29. Entire Agreement: Supersedes all prior negotiations, agreements (except those expressly preserved); amendments in writing only
30. Severability: Invalid provisions severed; remainder enforceable
31. Waiver: No waiver unless written; single waiver not continuing
32. Assignment: May not assign rights/obligations without consent [except to successors in business]
33. Further Assurance: Parties to execute all documents reasonably necessary to give effect to settlement
34. Time of Essence: Time is of the essence for all payment and performance obligations
35. Counterparts: May execute in counterparts (including electronic signatures)
36. Notices: Written notice to addresses stated; deemed received [2] days after registered post / immediate if hand-delivered/email
37. Governing Law: Singapore law
38. Jurisdiction: Non-exclusive jurisdiction of Singapore courts for enforcement
39. Stamp Duty: [If settlement involves property/shares: address stamp duty obligations]

TAX TREATMENT (Parties to obtain independent advice):
40. Tax Obligations: Each party responsible for own tax obligations arising from settlement
41. Characterization: [Specify if settlement payment is compensation for loss, return of capital, income, etc. - affects tax treatment]
42. Gross-Up: [If applicable: Settlement amount is net of tax; payer to gross up for any withholding]

SPECIAL PROVISIONS (as applicable):
43. Non-Disparagement: Parties shall not make disparaging remarks about each other
44. Reference: [For employment settlements: Agreed form of employment reference attached as Schedule]
45. Indemnity: [If applicable: One party indemnifies other against specified claims]
46. Ongoing Relationship: [If parties continue business relationship: Terms of future dealings]

EXECUTION:
This Agreement is executed as a Deed [if required for enforceability/no consideration] OR as a Contract.

Signed by [PLAINTIFF]:

________________________
[Name]
[NRIC/UEN]
[Position if company]
Date:

Signed by [DEFENDANT]:

________________________
[Name]
[NRIC/UEN]
[Position if company]
Date:

Witnessed by:

________________________
[Name, NRIC]
[Address]
Date:

SCHEDULES:
Schedule 1: Payment Schedule (if installments)
Schedule 2: Agreed Public Statement (if applicable)
Schedule 3: Form of Discontinuance (if litigation)
Schedule 4: Employment Reference (if applicable)

LEGAL CONSIDERATIONS:
- Evidence Act Section 23: Without prejudice communications inadmissible except for enforcement
- Contracts (Rights of Third Parties) Act: Consider if third parties have enforcement rights
- Limitation Act: Settlement tolls limitation periods for released claims
- Enforceable as contract once executed; if deed, enforceable even without consideration
- Consider tax implications: capital vs income treatment affects tax obligations (seek advice)
- For employment disputes: Ensure compliance with Employment Act if applicable (cannot contract out of statutory rights)
- For consumer disputes: Consumer Protection (Fair Trading) Act may limit certain waiver clauses

IMPORTANT NOTES:
- Both parties should obtain independent legal advice before signing
- Ensure all decision-makers approve (e.g., company directors, insurers if insured claim)
- If litigation commenced, strictly comply with court rules for discontinuance/consent orders
- Maintain confidentiality to preserve enforceability of confidentiality clause
- Consider whether Consent Order preferable to private settlement (court enforcement mechanism vs. confidentiality)

Please draft with clear, unambiguous terms. Ambiguity construed against drafter (contra proferentem rule).`,
  },

  // IP & Technology
  {
    id: 'ip-assignment',
    name: 'IP Assignment Agreement',
    category: 'Intellectual Property',
    description: 'Agreement for transferring intellectual property rights',
    prompt: `Draft a comprehensive Intellectual Property Assignment Agreement compliant with Singapore IP legislation:

PARTIES:
1. Assignor: [Full name/company name, NRIC/UEN, address]
   - Capacity: [Individual creator / Company owner / Inventor]
2. Assignee: [Full name/company name, NRIC/UEN, address]
   - Purpose: [Business operations / Product development / Investment]

TYPE OF IP BEING ASSIGNED (Select applicable):
3. Copyright Works (Copyright Act Cap. 63)
4. Patents (Patents Act Cap. 221)
5. Trademarks/Service Marks (Trade Marks Act Cap. 332)
6. Registered Designs (Registered Designs Act Cap. 266)
7. Trade Secrets and Confidential Information (common law)
8. Domain Names
9. Plant Varieties (Plant Varieties Protection Act)

DETAILED DESCRIPTION OF IP:

FOR COPYRIGHT (Section 7A, Copyright Act):
10. Type of Work: [Literary / Dramatic / Musical / Artistic / Cinematograph / Sound Recording / Broadcast / Cable Programme / Published Edition]
11. Title/Description: [Detailed description]
12. Date of Creation: [DD/MM/YYYY]
13. Author(s): [Names of creators]
14. First Publication: [Date and place if published]
15. Ownership Chain: [How Assignor acquired rights - as original author / prior assignment / employment]
16. Registration: [Copyright registration with IPOS (optional but evidential value)]

FOR PATENTS (Section 20, Patents Act):
17. Patent Details:
    - Application Number: [If filed: Application No. XXXXXXXX filed DD/MM/YYYY]
    - Patent Number: [If granted: Patent No. XXXXXXXX granted DD/MM/YYYY]
    - Title of Invention: [Formal title]
    - Inventors: [Names and addresses]
18. Description: [Technical description of invention]
19. Claims: [Number of claims in patent specification]
20. Priority Date: [Date establishing priority]
21. Status: [Pending / Granted / About to be filed]
22. Corresponding Foreign Applications: [List PCT, US, EU, other jurisdictions]

FOR TRADEMARKS (Section 38, Trade Marks Act):
23. Trademark Details:
    - Mark: [Word mark "X" / Logo (attach image) / Combined mark / Shape / Sound mark]
    - Application Number: [T XXXXXXXX filed DD/MM/YYYY]
    - Registration Number: [If registered: T XXXXXXXX registered DD/MM/YYYY, valid until DD/MM/YYYY]
24. Classes: Nice Classification Class(es) [X, Y, Z] covering [goods/services]
25. Specification of Goods/Services: [As registered/applied]
26. Status: [Pending / Registered / Opposition pending]
27. Associated Goodwill: [Assignment includes goodwill per Section 38(2) - mandatory for assignment validity]

FOR REGISTERED DESIGNS (Section 20, Registered Designs Act):
28. Design Details:
    - Registration Number: [D XXXXXXXX]
    - Registration Date: [DD/MM/YYYY]
    - Expiry: [5 years renewable to 15 years maximum]
29. Description: [Description of features of shape, configuration, pattern, ornament]
30. Representations: [Attach drawings/photographs]
31. Article: [Type of article to which design applies]

FOR TRADE SECRETS:
32. Description: [Confidential business information, technical know-how, customer lists, formulae, processes, methods]
33. Commercial Value: Derives value from being secret; reasonable steps taken to maintain secrecy
34. Documentation: [List documents containing trade secrets]

ASSIGNMENT AND TRANSFER:
35. Assignment of Rights: Assignor hereby assigns, transfers, and conveys to Assignee:
    - ALL rights, title, and interest in the IP
    - ALL intellectual property rights worldwide
    - RIGHT to sue for past, present, and future infringements
    - ALL associated goodwill (for trademarks - mandatory per Section 38(2), Trade Marks Act)
    - ALL rights to register, renew, enforce IP
36. Exclusive Rights: Assignment is exclusive; Assignor retains NO rights or licenses
37. Effective Date: Assignment effective from [Date] (or upon full payment of consideration if later)
38. Future IP: [If applicable: Assignment includes improvements, modifications, derivative works created by Assignor for [X] period]

CONSIDERATION:
39. Purchase Price: $[Amount] (in words: [Amount in words])
40. Payment Terms:
    - $[X] upon execution of this Agreement
    - $[Y] upon [milestone / registration / transfer completion]
41. Allocation: [If multiple IP assets, allocate price for tax purposes]
42. Alternative Consideration: [Share swap / License-back / Other consideration if not pure cash sale]

ASSIGNOR'S WARRANTIES AND REPRESENTATIONS (Critical for Assignee protection):
43. Ownership: Assignor is the sole legal and beneficial owner of the IP with full right to assign
44. Validity: IP is valid, subsisting, and enforceable
45. No Encumbrances: IP free from liens, charges, licenses, assignments, or third-party rights
46. No Infringement: IP does not infringe third-party rights; no infringement claims pending/threatened
47. Registration: [If registered IP: Registration valid, in force, all renewal fees paid]
48. No Prior Assignments: IP not previously assigned or licensed (except as disclosed)
49. No Challenges: No invalidity challenges or opposition proceedings
50. Authority: Full authority to enter and perform this Agreement
51. Creator's Rights: All creators/inventors have assigned rights or are employees whose work vests in Assignor
52. Disclosure: Full disclosure of all material facts affecting IP value

ASSIGNEE'S COVENANTS:
53. Use of IP: Assignee may use, exploit, modify, license, sell IP without restriction
54. Maintenance: Assignee responsible for maintaining, renewing, protecting IP (paying renewal fees, etc.)
55. Assignor's Rights: [If applicable: Assignor credited as author/inventor in accordance with moral rights]

FURTHER ASSURANCE (Essential for registration):
56. Cooperation: Assignor shall execute all documents and take all steps reasonably necessary to:
    - Record assignment with IPOS (for patents, trademarks, registered designs)
    - Perfect Assignee's title to IP
    - Assist in prosecution of pending applications
    - Assist in enforcement against infringers
57. Power of Attorney: [If appropriate: Assignor grants Assignee power of attorney to execute documents on Assignor's behalf]
58. Survival: Further assurance obligations survive completion and termination

MORAL RIGHTS (Copyright Act Section 189 - 193):
59. Moral Rights Waiver: To extent permitted by law, Assignor irrevocably waives moral rights:
    - Right of attribution/paternity (Section 189)
    - Right against false attribution (Section 191)
    - Right to integrity of work (Section 190)
60. Consent to Modifications: Assignor consents to Assignee modifying, adapting, translating works without attribution
61. Note: Moral rights personal to author and generally cannot be assigned, only waived

CONFIDENTIALITY:
62. Confidential Information: Trade secrets, know-how, technical information to remain confidential
63. Obligations: Both parties protect confidential information; use only for authorized purposes
64. Exceptions: Standard exceptions (public domain, independently developed, legally compelled)
65. Duration: Perpetual for trade secrets; [X years] for other confidential information

INDEMNIFICATION:
66. Assignor's Indemnity: Assignor indemnifies Assignee against:
    - Third-party claims that IP infringes their rights
    - Breach of warranties or representations
    - Claims arising from Assignor's pre-assignment use of IP
67. Assignee's Indemnity: Assignee indemnifies Assignor against claims arising from post-assignment use
68. Indemnity Procedures: Notice, conduct of defense, cooperation requirements
69. Cap: Assignor's liability capped at [consideration amount / $X / unlimited]

LIABILITY LIMITATIONS:
70. Disclaimer: EXCEPT WARRANTIES EXPRESSLY STATED, IP ASSIGNED "AS IS" WITHOUT WARRANTIES (EXPRESS OR IMPLIED) OF MERCHANTABILITY, FITNESS, TITLE, NON-INFRINGEMENT
71. Consequential Damages: Neither party liable for indirect, consequential, special damages
72. Exceptions: Caps do not apply to fraud, willful misconduct, indemnification obligations

RECORDATION WITH IPOS (Mandatory for certain IP):
73. Patents: Assignment recorded with Intellectual Property Office of Singapore per Section 43, Patents Act (Registry of Patents)
74. Trademarks: Assignment recorded per Section 39, Trade Marks Act (Register of Trade Marks) - assignment void against third parties until recorded
75. Registered Designs: Assignment recorded per Section 20, Registered Designs Act
76. Responsibility: [Assignee] responsible for filing assignment documents and fees
77. Timing: File within [30] days of execution

TAX CONSIDERATIONS (Seek professional advice):
78. GST: [Assignment may be subject to GST if Assignor GST-registered; specify if consideration is GST-inclusive]
79. Income Tax: Assignor responsible for tax on gain; capital vs income treatment affects tax rate
80. Stamp Duty: [Generally no stamp duty on IP assignment unless involves land or shares]
81. Withholding: [For foreign assignors: Consider withholding tax obligations]

GENERAL PROVISIONS:
82. Entire Agreement: Supersedes all prior agreements; amendments in writing only
83. Severability: Invalid provisions severed; remainder enforceable
84. Waiver: No waiver unless written; single waiver not continuing
85. Assignment by Parties: Assignee may assign; Assignor may not assign obligations
86. Notices: Written notice to addresses stated; deemed received [2] days after posting
87. Governing Law: Singapore law (Copyright Act, Patents Act, Trade Marks Act, Registered Designs Act)
88. Jurisdiction: Non-exclusive jurisdiction of Singapore courts
89. Dispute Resolution: [Mediation at SMC, then arbitration at SIAC / Litigation]
90. Counterparts: May execute in counterparts

SPECIAL PROVISIONS:
91. License-Back: [If applicable: Assignee grants Assignor non-exclusive license to use IP for [specified purpose] on terms: [royalty-free / X% royalty]]
92. Earn-Out: [If applicable: Additional payments if IP generates revenue: $X if revenue >$Y]
93. Escrow: [If payment in installments: IP assignment documents held in escrow until full payment]

EXECUTION:
Signed by ASSIGNOR:

________________________
[Name]
[NRIC/UEN]
[Position if company]
Date:

Signed by ASSIGNEE:

________________________
[Name]
[NRIC/UEN]
[Position if company]
Date:

Witnessed by:

________________________
[Name, NRIC]
Date:

SCHEDULES:
Schedule 1: Detailed Description of IP (specifications, registrations, drawings)
Schedule 2: Copies of IP Registrations/Applications
Schedule 3: List of Associated Documentation and Materials
Schedule 4: Form of IPOS Assignment Recordation (Form CM1 for trademarks, etc.)
Schedule 5: License-Back Agreement (if applicable)

STATUTORY COMPLIANCE:
- Copyright Act (Cap. 63): Section 7A governing copyright assignment; must be in writing
- Patents Act (Cap. 221): Section 20 permits assignment; Section 43 requires recordation
- Trade Marks Act (Cap. 332): Section 38 permits assignment WITH goodwill; Section 39 recordation mandatory
- Registered Designs Act (Cap. 266): Section 20 permits assignment; must be recorded
- Common Law: Trade secrets assignable as confidential information
- IPOS Registration: File assignment documents to perfect title and provide public notice

CRITICAL NOTES:
- For trademarks: MUST assign with associated goodwill or assignment is void (Section 38(2))
- Without recordation, assignment may be invalid against third parties or subsequent purchasers
- Ensure all inventors/creators have assigned rights to Assignor (check employment contracts, commissioning agreements)
- Both parties should obtain independent legal and tax advice
- Consider IP due diligence: searches for conflicting rights, validity opinions, freedom-to-operate analysis

Please draft with appropriate schedules, clear scope of assignment, and ensure registration requirements met.`,
  },

  // Quick Clauses
  {
    id: 'confidentiality-clause',
    name: 'Confidentiality Clause',
    category: 'Clauses',
    description: 'Standalone confidentiality provision',
    prompt: `Draft a comprehensive confidentiality clause suitable for inclusion in Singapore commercial contracts, compliant with common law principles of breach of confidence and the Personal Data Protection Act 2012:

CONFIDENTIALITY

1. Definition of Confidential Information
   "Confidential Information" means all information (whether oral, written, electronic, visual, or in any other form) disclosed by one party ("Disclosing Party") to the other party ("Receiving Party") including but not limited to:

   a) Technical Information: Designs, specifications, formulae, know-how, inventions, processes, techniques, research, development data, software, source code, algorithms;

   b) Business Information: Customer lists, supplier details, pricing, marketing strategies, business plans, financial information, sales data, profit margins, forecasts, budgets;

   c) Commercial Information: Contract terms, negotiations, tenders, proposals, trade secrets, proprietary methodologies;

   d) Personal Data: Information subject to Personal Data Protection Act 2012 (if applicable);

   e) Information Marked: Information marked or identified as "Confidential," "Proprietary," or similar designation;

   f) Orally Disclosed Information: Information disclosed orally and identified as confidential at time of disclosure or confirmed in writing as confidential within thirty (30) days.

2. Obligations of Receiving Party
   The Receiving Party shall:

   a) Non-Disclosure: Keep all Confidential Information strictly confidential and not disclose to any third party except as expressly permitted herein;

   b) Non-Use: Use Confidential Information solely for the purposes of [performing this Agreement / the permitted purpose] and not for any other purpose including competitive advantage;

   c) Standard of Care: Protect Confidential Information with the same degree of care used to protect its own confidential information of similar nature (being at minimum a reasonable standard of care);

   d) Limit Access: Restrict access to Confidential Information to employees, contractors, advisors, and agents who:
      (i) Have a legitimate need to know for the permitted purpose;
      (ii) Are bound by written confidentiality obligations no less restrictive than these terms;
      (iii) Have been informed of the confidential nature of the information;

   e) Security Measures: Implement and maintain reasonable physical, electronic, and procedural safeguards to prevent unauthorized access, use, or disclosure;

   f) Breach Notification: Immediately notify Disclosing Party upon discovery of any unauthorized use, disclosure, or breach of confidentiality, and cooperate in remedying the breach;

   g) Return/Destruction: Upon Disclosing Party's written request or upon termination of this Agreement:
      (i) Return all Confidential Information and copies (in any form); OR
      (ii) Destroy all Confidential Information and certify destruction in writing;
      (iii) Except: May retain one copy for legal/compliance purposes in secure, access-restricted files.

3. Exceptions to Confidential Information
   Confidential Information does not include information that:

   a) Public Domain: Is or becomes publicly available through no breach of this Agreement by Receiving Party;

   b) Prior Knowledge: Was in Receiving Party's lawful possession prior to disclosure by Disclosing Party, as evidenced by written records;

   c) Independent Development: Is independently developed by Receiving Party without reference to or use of Disclosing Party's Confidential Information, as evidenced by written records;

   d) Third-Party Disclosure: Is rightfully received from a third party without breach of confidentiality obligations and without restriction on disclosure;

   e) Required by Law: Is required to be disclosed by law, court order, regulatory authority, or government body, provided that Receiving Party:
      (i) Gives Disclosing Party prompt written notice of such requirement (if legally permitted);
      (ii) Cooperates with Disclosing Party's efforts to obtain protective order or confidential treatment;
      (iii) Discloses only the minimum information legally required;
      (iv) Requests confidential treatment of disclosed information where possible.

4. Duration of Confidentiality Obligations
   a) The obligations of confidentiality shall continue for [three (3) / five (5)] years from the date of disclosure of each item of Confidential Information; OR

   b) For Trade Secrets: Obligations continue in perpetuity for information qualifying as trade secrets under common law (per Coco v AN Clark (Engineers) Ltd test: information with necessary quality of confidence, disclosed in circumstances importing obligation, and unauthorized use detrimental);

   c) Survival: Confidentiality obligations survive termination or expiration of this Agreement.

5. Ownership and No License
   a) All Confidential Information remains the sole property of the Disclosing Party;

   b) No license, right, title, or interest in or to Confidential Information or any intellectual property rights is granted except as expressly set forth in this Agreement;

   c) Disclosure does not constitute any representation, warranty, assurance, guarantee, or inducement of any kind.

6. Remedies and Enforcement (Per Aquila Design v Cornhill Insurance principles)
   a) Irreparable Harm: Receiving Party acknowledges that breach would cause irreparable harm to Disclosing Party not adequately compensable by monetary damages;

   b) Equitable Relief: Disclosing Party entitled to seek immediate injunctive relief, specific performance, and other equitable remedies without need to prove damages or post bond (subject to court discretion);

   c) Damages: Disclosing Party entitled to claim all monetary damages including consequential damages resulting from breach;

   d) Cumulative Remedies: Remedies are cumulative and not exclusive; pursuit of one remedy does not preclude others;

   e) Legal Costs: Prevailing party in enforcement action entitled to recover reasonable legal costs [on standard basis / on indemnity basis].

7. Personal Data Protection Act Compliance (If applicable)
   If Confidential Information includes personal data as defined in the Personal Data Protection Act 2012:

   a) Data Protection Obligations: Receiving Party shall comply with all applicable data protection laws including PDPA;

   b) Security: Implement reasonable security arrangements to protect personal data against unauthorized access, collection, use, disclosure, copying, modification, disposal, or similar risks;

   c) Notification: Notify Disclosing Party of any data breaches within [24] hours of discovery;

   d) Data Processing: Process personal data only for authorized purposes and in accordance with Disclosing Party's instructions;

   e) Indemnity: Receiving Party indemnifies Disclosing Party against claims, fines, penalties arising from Receiving Party's breach of data protection obligations.

8. No Obligation to Disclose
   Nothing in this Agreement obligates either party to disclose any Confidential Information; each party may withhold information at its sole discretion.

This clause is governed by the laws of Singapore and enforceable under common law principles of breach of confidence (Coco v AN Clark; Aquila Design v Cornhill Insurance).`,
  },
  {
    id: 'force-majeure',
    name: 'Force Majeure Clause',
    category: 'Clauses',
    description: 'Clause for unforeseeable circumstances',
    prompt: `Draft a comprehensive force majeure clause suitable for Singapore contracts, addressing modern risks including pandemics, supply chain disruptions, and cybersecurity events:

FORCE MAJEURE

1. Force Majeure Event Defined
   "Force Majeure Event" means any event or circumstance beyond the reasonable control of the affected party, which prevents or delays that party from performing its obligations under this Agreement, including but not limited to:

   a) Acts of God: Earthquakes, floods, tsunamis, typhoons, hurricanes, tornadoes, volcanic eruptions, landslides, lightning, severe weather, natural disasters;

   b) Pandemic and Health Emergencies: Pandemics, epidemics, public health emergencies (including COVID-19 and future similar events), quarantine restrictions, government-imposed lockdowns or circuit breakers;

   c) Government Actions: Laws, regulations, orders, directives, embargoes, import/export restrictions, government requisitions, nationalization, expropriation, confiscation, license revocations, curfews, states of emergency;

   d) War and Civil Unrest: War (declared or undeclared), invasion, act of foreign enemy, civil war, rebellion, revolution, insurrection, military coup, terrorism, sabotage, riots, civil commotion;

   e) Labor Disruptions: General strikes, industry-wide labor disputes (excluding strikes specific to the affected party's workforce), lockouts;

   f) Utilities and Infrastructure Failures: Failure of public utilities (power, water, telecommunications, internet), infrastructure collapse, prolonged power outages not caused by affected party;

   g) Cyber Events: Cyberattacks, ransomware, denial-of-service attacks, data breaches, malware infections (provided reasonable cybersecurity measures were in place);

   h) Supply Chain Disruptions: Failure of critical suppliers or subcontractors due to Force Majeure Event (provided reasonable alternative sources explored);

   i) Fire and Explosions: Fire, explosion, chemical contamination (not caused by affected party's negligence);

   j) Transportation Disruptions: Closure of ports, airports, borders; shipping disruptions; vessel or aircraft grounding.

2. Exclusions from Force Majeure
   Force Majeure Event does NOT include:

   a) Economic Hardship: Economic downturn, market changes, financial difficulties, increased costs, inability to make profit, lack of funds, currency fluctuations (unless caused by government actions meeting Force Majeure criteria);

   b) Party's Own Default: Events caused by affected party's negligence, willful misconduct, breach of contract, or failure to perform obligations;

   c) Foreseeable Events: Events that were reasonably foreseeable at the time of contract execution and against which precautions could reasonably have been taken;

   d) Lack of Preparedness: Failure to implement business continuity plans, disaster recovery measures, or reasonable risk mitigation strategies;

   e) Labor Issues: Strikes, disputes, or shortages specific to the affected party's own workforce or resulting from that party's labor practices;

   f) Supplier Default: Default by suppliers or subcontractors (unless due to Force Majeure Event and reasonable alternatives unavailable despite diligent efforts).

3. Notice Requirements
   Upon occurrence of a Force Majeure Event:

   a) Immediate Notice: Affected party shall notify the other party in writing as soon as reasonably practicable (within [3/5/7] days of becoming aware);

   b) Details Required: Notice must include:
      (i) Nature of Force Majeure Event;
      (ii) Date of occurrence and expected duration;
      (iii) Obligations affected and extent of impact;
      (iv) Steps taken to mitigate effects;
      (v) Alternative performance plans (if any);
      (vi) Estimated timeframe for resumption of performance;

   c) Updates: Regular updates (at least every [7/14/30] days) on status, continued impact, and mitigation efforts;

   d) Cessation Notice: Prompt written notice when Force Majeure Event ceases or performance can resume.

4. Effects of Force Majeure
   Upon valid Force Majeure Event properly notified:

   a) Suspension of Obligations: Affected party's performance obligations suspended to the extent prevented by Force Majeure Event, without liability for non-performance or delay;

   b) Time Extension: Performance deadlines extended for period of delay caused by Force Majeure Event plus reasonable period to resume performance;

   c) No Breach: Non-performance or delay due to Force Majeure Event not deemed breach of contract;

   d) Payment Obligations: [Option A: Payment obligations suspended proportionately; OR Option B: Payment obligations continue unless prevented by Force Majeure];

   e) Partial Performance: If only partially prevented, affected party must perform all obligations not prevented by Force Majeure Event.

5. Mitigation Obligations (Critical under Singapore law)
   The affected party shall:

   a) Reasonable Efforts: Use all reasonable endeavors to:
      (i) Mitigate effects of Force Majeure Event;
      (ii) Identify workarounds and alternative means of performance;
      (iii) Resume full performance as soon as reasonably possible;

   b) Alternative Performance: Explore and implement reasonable alternatives including:
      (i) Alternative suppliers, subcontractors, or service providers;
      (ii) Alternative methods of delivery or performance;
      (iii) Allocation of available capacity fairly among customers;

   c) Business Continuity: Implement business continuity and disaster recovery plans;

   d) Cooperation: Cooperate with other party in minimizing impact and achieving alternative solutions.

6. Unaffected Party's Rights
   The party not affected by Force Majeure Event may:

   a) Suspend Performance: Suspend its own corresponding obligations during Force Majeure Event period [where performance depends on affected party's obligations];

   b) Alternative Supply: Obtain substitute goods/services from third parties if commercially reasonable [with/without obligation to return to original party upon resumption];

   c) Monitor Mitigation: Request evidence of mitigation efforts and alternative performance measures.

7. Termination Rights for Prolonged Force Majeure
   If Force Majeure Event continues for more than [90/120/180] consecutive days:

   a) Termination Option: Either party may terminate this Agreement by [30] days' written notice;

   b) Partial Termination: If Force Majeure Event affects only part of obligations, may terminate affected portion only;

   c) Effect of Termination:
      (i) No penalty or damages for termination due to Force Majeure;
      (ii) Each party pays for goods/services delivered to date;
      (iii) Return of materials, property, confidential information;
      (iv) Survival of confidentiality, IP, indemnity, governing law clauses;

   d) Negotiation Option: Before termination, parties may negotiate modified terms to address ongoing Force Majeure impact.

8. Documentation and Evidence
   a) Burden of Proof: Affected party bears burden of proving Force Majeure Event occurrence, impact, and causation;

   b) Supporting Documentation: Must provide reasonable evidence such as:
      (i) Government orders, official declarations, gazette notifications;
      (ii) Industry reports, news articles, expert opinions;
      (iii) Supplier notices, shipping documents;
      (iv) Photographs, inspection reports, damage assessments;

   c) Independent Verification: Other party may reasonably request third-party verification of Force Majeure Event and impact.

9. Pandemic-Specific Provisions (Given COVID-19 experience)
   For pandemic or epidemic events:

   a) Government Measures: Includes lockdowns, circuit breakers, movement restrictions, business closure orders, social distancing mandates;

   b) Health and Safety: Measures taken to comply with health and safety requirements or protect employees deemed reasonable mitigation;

   c) Remote Work: Failure to perform solely because of shift to remote work generally NOT Force Majeure (reasonable adaptation expected);

   d) Supply Chain: Supply chain disruptions due to pandemic qualify if reasonable alternatives unavailable despite diligent efforts.

10. Relationship to Other Provisions
    a) Does not limit or exclude liability for obligations arising before Force Majeure Event;

    b) Does not excuse payment of undisputed amounts due before Force Majeure Event;

    c) Operates without prejudice to any insurance provisions or other risk allocation mechanisms in this Agreement;

    d) [Does / Does not] limit indemnification obligations for third-party claims.

11. Governing Principles
    This clause shall be interpreted in accordance with:

    a) Singapore Contract Law: Common law principles of frustration (discharge for impossibility or radical change in obligations);

    b) Strict Interpretation: Force Majeure clauses strictly construed; claimant must prove event falls within clause (RDC Concrete Pte Ltd v Sato Kogyo);

    c) Foreseeability: Events foreseeable at contracting (e.g., seasonal weather, known political instability) generally excluded unless specifically listed;

    d) Causation: Clear causal link required between Force Majeure Event and inability to perform;

    e) Not Absolute Excuse: Force Majeure does not excuse performance if event merely makes performance more difficult or expensive (Holcim (Singapore) Pte Ltd v Precise Development Pte Ltd).

IMPORTANT NOTES:
- This clause does not operate to frustrate the contract automatically; parties remain bound to perform once Force Majeure Event ceases
- Mitigation obligations are critical; failure to mitigate may invalidate Force Majeure claim
- Early and comprehensive notice essential to preserve Force Majeure rights
- Consider whether force majeure insurance or other risk transfer mechanisms appropriate

This clause is governed by the laws of Singapore.`,
  },
  {
    id: 'dispute-resolution-clause',
    name: 'Dispute Resolution Clause',
    category: 'Clauses',
    description: 'Clause for resolving disputes',
    prompt: `Draft a comprehensive multi-tiered dispute resolution clause for Singapore contracts, incorporating best practices from Singapore International Arbitration Centre (SIAC) and Singapore Mediation Centre (SMC):

DISPUTE RESOLUTION

1. Good Faith Negotiations
   a) Pre-Condition: Before initiating formal dispute resolution, the parties shall attempt in good faith to resolve any dispute, controversy, or claim arising out of or relating to this Agreement, or the breach, termination, or validity thereof ("Dispute") through amicable negotiations;

   b) Escalation Process:
      (i) Working Level: Representatives with knowledge of the matter shall first attempt resolution within [14] days of written notice of Dispute;
      (ii) Senior Management: If unresolved, escalate to senior executives with authority to settle within [14] days;
      (iii) Record: Parties shall prepare written summary of positions and efforts to resolve;

   c) Confidentiality: All negotiations are confidential and conducted on a without prejudice basis per Section 23, Evidence Act (Cap. 97);

   d) Preservation of Rights: Negotiation period does not extend limitation periods; either party may commence formal proceedings if limitation period at risk.

2. Mediation at Singapore Mediation Centre
   a) Mandatory Mediation: If Dispute not resolved through negotiations within [30] days of first written notice, either party may refer to mediation at the Singapore Mediation Centre ("SMC");

   b) SMC Mediation Rules: Mediation conducted under SMC Mediation Procedure in force at time of notice;

   c) Mediator Selection:
      (i) Single mediator agreed by parties within [7] days of referral; OR
      (ii) If no agreement, mediator appointed by SMC Administrator;
      (iii) Preferred qualifications: [Legal background / Industry expertise / Specify if relevant];

   d) Mediation Process:
      (i) Location: Singapore (or virtual if parties agree);
      (ii) Language: English;
      (iii) Duration: Target resolution within [30/60] days of mediator appointment;
      (iv) Good Faith Participation: Parties attend in person with authority to settle;

   e) Costs: Mediation costs (mediator fees, SMC administration fees) shared equally unless otherwise agreed;

   f) Settlement: Any settlement reached in mediation documented in binding written settlement agreement;

   g) Confidentiality: Mediation communications confidential per Section 23, Evidence Act; inadmissible in subsequent proceedings except for enforcement of settlement;

   h) Continuation of Performance: Pending mediation, parties continue performing non-disputed obligations unless otherwise agreed or security/safety concern.

3. Arbitration at Singapore International Arbitration Centre
   a) Exclusive Arbitration: If Dispute not resolved through mediation within [60] days of mediation commencement (or if mediation otherwise terminates), the Dispute shall be finally resolved by arbitration administered by the Singapore International Arbitration Centre ("SIAC");

   b) SIAC Rules: Arbitration conducted under SIAC Arbitration Rules in force at time of notice of arbitration, as modified by this clause;

   c) Arbitral Tribunal:
      (i) Number: [One (1) arbitrator] OR [Three (3) arbitrators];
      (ii) Appointment: [If sole arbitrator: Agreed by parties within 14 days or appointed by President of SIAC] / [If three arbitrators: Each party appoints one arbitrator; two appointed arbitrators select third (presiding) arbitrator; failing agreement, President of SIAC appoints];
      (iii) Qualifications: Arbitrators shall be [legally qualified / have expertise in [industry/field]] and independent of parties;

   d) Seat and Language:
      (i) Seat: Singapore (regardless of where hearings conducted);
      (ii) Language: English (documents in other languages translated at party's expense);

   e) Governing Law of Contract: Singapore law (excluding conflicts of law principles) governs the substance of the Dispute;

   f) Procedural Rules:
      (i) Written Submissions: [Statement of Claim, Statement of Defence, Reply, Rejoinder - specify page limits if desired];
      (ii) Document Production: IBA Rules on the Taking of Evidence in International Arbitration [or specify streamlined production];
      (iii) Hearings: Oral hearings [mandatory / at tribunal's discretion / on party request];
      (iv) Witnesses: Witness statements exchanged; witnesses available for cross-examination;
      (v) Experts: [Party-appointed experts / Tribunal-appointed expert / Both];

   g) Timeline: Target arbitration conclusion within [9/12] months of tribunal constitution (subject to complexity);

   h) Interim Measures:
      (i) Tribunal Powers: Arbitral tribunal may grant interim measures (injunctions, preservation orders, etc.) per Article 26, SIAC Rules;
      (ii) Court Support: Parties may apply to Singapore courts for interim relief per Section 12A, International Arbitration Act (Cap. 143A);

   i) Award:
      (i) Final and Binding: Award final and binding on parties;
      (ii) Reasons: Award shall be reasoned;
      (iii) Currency: Award in Singapore Dollars [or specify currency];
      (iv) Interest: Tribunal may award pre-award and post-award interest;
      (v) Costs: Tribunal shall allocate costs (arbitrators' fees, SIAC fees, legal costs) [per SIAC Rules / costs follow the event / specify allocation];
      (vi) Legal Costs Basis: [Standard basis / Indemnity basis for prevailing party];

   j) Enforcement: Award enforceable as judgment of Singapore courts per Section 19, International Arbitration Act; or internationally per New York Convention (Singapore signatory);

   k) Confidentiality: Arbitration proceedings, submissions, evidence, and awards strictly confidential except:
      (i) Disclosure to legal/financial advisors under confidentiality obligations;
      (ii) Disclosure required by law, regulatory authority, stock exchange;
      (iii) Disclosure for enforcement purposes;
      (iv) Disclosure necessary to protect party's legal rights in other proceedings;

   l) Consolidation and Joinder:
      (i) Related Disputes: Parties may agree to consolidate related arbitrations;
      (ii) Third Parties: Tribunal may join third parties if agreement permits and all parties (including third party) consent;
      (iii) Absent specific joinder provisions, each arbitration proceeds separately.

4. Interim and Conservatory Relief from Singapore Courts
   a) Court Jurisdiction: Notwithstanding arbitration agreement, parties may apply to Singapore courts for:
      (i) Urgent interim or conservatory relief (injunctions, asset freezes, preservation orders, inspection orders) per Section 12A, International Arbitration Act;
      (ii) Security for costs;
      (iii) Enforcement of mediation settlement agreements or arbitral awards;

   b) Not Waiver: Application to court for interim relief not waiver of arbitration agreement and does not affect tribunal's authority;

   c) Supporting Arbitration: Court relief intended to support, not supplant, arbitration process.

5. Exclusive Jurisdiction for Non-Arbitrable Matters
   For matters not subject to arbitration (if any, e.g., injunctive relief, IP registration disputes):

   a) Courts: Parties submit to the exclusive jurisdiction of the courts of Singapore;

   b) Service of Process: Parties irrevocably consent to service of process at addresses in this Agreement;

   c) Waiver: Parties waive any objection to venue or inconvenient forum.

6. Multi-Contract and Third-Party Disputes
   a) Related Contracts: If Dispute relates to multiple contracts with substantially similar dispute resolution clauses, parties may consolidate into single mediation or arbitration;

   b) Third-Party Claims: [For contracts contemplating third-party involvement (e.g., construction contracts with multiple parties):
      (i) Joined Proceedings: Claims involving third parties [may / may not] be joined to arbitration with consent of all parties and tribunal;
      (ii) Alternative: Third-party disputes resolved under same procedure in parallel proceedings coordinated by agreement.]

7. Exceptions to Dispute Resolution Procedure
   The following matters exempt from negotiation and mediation (may proceed directly to arbitration or court):

   a) Urgent Relief: Applications for urgent interim relief where delay would cause irreparable harm;

   b) IP Enforcement: Intellectual property infringement claims requiring immediate injunctive relief;

   c) Payment Disputes: [If specified: Undisputed payment obligations may be enforced directly];

   d) Insolvency: Claims in bankruptcy, insolvency, winding up, or receivership proceedings.

8. Limitation Periods
   a) Preservation: Timelines for negotiation and mediation do not extend statutory limitation periods;

   b) Tolling: Limitation periods tolled during mediation from date of mediation notice to termination of mediation;

   c) Protective Filings: Parties may file protective arbitration notice to preserve rights if limitation period at risk.

9. Continuing Obligations During Dispute
   Pending resolution of Dispute:

   a) Performance Continues: Parties continue performing non-disputed obligations (unless performance enjoined or subject matter of Dispute);

   b) Payments: Continue making undisputed payments when due;

   c) Confidentiality: Maintain confidentiality and other ongoing obligations;

   d) Good Faith: Deal with each other in good faith; no repudiation of contract solely due to Dispute.

10. Costs and Expenses
    a) Each Party Bears Own: Each party bears its own costs of negotiations and mediation (unless settlement provides otherwise);

    b) Shared Mediation Costs: SMC fees and mediator fees shared equally unless parties agree otherwise;

    c) Arbitration Costs: Per arbitral award allocation (typically costs follow the event);

    d) Security for Costs: Tribunal may order security for costs if appropriate.

11. Governing Law and Interpretation
    a) This dispute resolution clause governed by Singapore law;

    b) Arbitration governed by International Arbitration Act (Cap. 143A) [for international arbitration] OR Arbitration Act (Cap. 10) [for domestic arbitration];

    c) Mediation settlement agreements enforceable as contracts; if parties opt in, also enforceable under Singapore Convention on Mediation (United Nations Convention on International Settlement Agreements Resulting from Mediation);

    d) Severability: If any part of this clause invalid or unenforceable, remainder continues in effect;

    e) Survival: This clause survives termination or expiration of the Agreement.

IMPORTANT NOTES:
- Multi-tiered dispute resolution demonstrates good faith and may reduce costs and preserve relationships
- Compliance with negotiation/mediation tiers may be condition precedent to arbitration; failure to comply may result in arbitration being stayed
- Early assessment critical: evaluate prospects and costs at each tier
- Consider whether emergency arbitrator provisions needed (SIAC Rules allow emergency arbitrator for urgent relief)
- SIAC arbitration awards recognized and enforceable in 160+ countries per New York Convention

This clause reflects Singapore's status as leading seat for international arbitration and mediation, with pro-arbitration judiciary, modern legislation, and world-class institutions.`,
  },
];

export const templateCategories = [
  'All',
  'Contracts',
  'Employment',
  'Corporate',
  'Property',
  'Finance',
  'Dispute Resolution',
  'Intellectual Property',
  'Clauses',
] as const;

export type TemplateCategory = typeof templateCategories[number];

export function getTemplatesByCategory(category: TemplateCategory): LegalTemplate[] {
  if (category === 'All') {
    return legalTemplates;
  }
  return legalTemplates.filter(template => template.category === category);
}

export function getTemplateById(id: string): LegalTemplate | undefined {
  return legalTemplates.find(template => template.id === id);
}
