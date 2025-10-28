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
    prompt: `Draft a comprehensive Non-Disclosure Agreement (NDA) under Singapore law with the following requirements:

1. Parties: [Specify disclosing party and receiving party]
2. Purpose: [Define the purpose of disclosure]
3. Confidential Information: [Describe what constitutes confidential information]
4. Obligations: Include non-disclosure, non-use, and security obligations
5. Duration: [Specify confidentiality period]
6. Exceptions: Standard exceptions (public knowledge, independent development, etc.)
7. Remedies: Injunctive relief and damages
8. Governing Law: Singapore law
9. Jurisdiction: Singapore courts

Please include all standard clauses for a Singapore NDA and explain each section.`,
  },
  {
    id: 'employment',
    name: 'Employment Contract',
    category: 'Employment',
    description: 'Standard employment agreement for Singapore employees',
    prompt: `Draft an Employment Contract compliant with Singapore's Employment Act including:

1. Parties: Employer and Employee details
2. Position and Duties: Job title, responsibilities, reporting structure
3. Commencement Date and Probation Period
4. Compensation: Salary, CPF contributions, bonuses, allowances
5. Working Hours: Standard hours, overtime provisions
6. Leave Entitlements: Annual leave, sick leave, maternity/paternity leave
7. Termination: Notice periods, grounds for termination
8. Confidentiality and Non-Compete: Post-employment restrictions
9. IP Assignment: Work-related intellectual property
10. Governing Law: Singapore law

Ensure compliance with the Employment Act and MOM regulations.`,
  },
  {
    id: 'service-agreement',
    name: 'Service Agreement',
    category: 'Contracts',
    description: 'Agreement for provision of services',
    prompt: `Draft a Service Agreement for Singapore businesses covering:

1. Parties: Service provider and client
2. Services: Detailed description of services to be provided
3. Term: Duration of agreement and renewal terms
4. Fees and Payment: Service fees, payment terms, late payment
5. Performance Standards: Quality metrics and KPIs
6. Responsibilities: Each party's obligations
7. IP Rights: Ownership of work product and deliverables
8. Confidentiality: Protection of business information
9. Liability: Limitation of liability and indemnities
10. Termination: Grounds and procedures
11. Dispute Resolution: Mediation and arbitration clauses
12. Governing Law: Singapore law

Include standard commercial terms and protections.`,
  },

  // Corporate Documents
  {
    id: 'shareholders-agreement',
    name: 'Shareholders Agreement',
    category: 'Corporate',
    description: 'Agreement governing shareholder rights and obligations',
    prompt: `Draft a Shareholders Agreement for a Singapore private limited company including:

1. Parties: All shareholders
2. Share Structure: Initial shareholdings and classes
3. Board Composition: Director appointments and removal
4. Voting Rights: Ordinary and special resolutions
5. Transfer Restrictions: Right of first refusal, drag-along, tag-along
6. Pre-emption Rights: New share issuances
7. Reserved Matters: Decisions requiring unanimous/supermajority approval
8. Dividend Policy: Distribution procedures
9. Dead lock Resolution: Mechanisms for resolving disputes
10. Exit Provisions: Put and call options
11. Non-Compete: Restrictions on competing businesses
12. Confidentiality: Protection of company information
13. Governing Law: Singapore law and Companies Act compliance`,
  },
  {
    id: 'resolution',
    name: 'Board Resolution',
    category: 'Corporate',
    description: 'Template for board resolutions',
    prompt: `Draft a Board Resolution template for a Singapore company for:

Subject: [Specify the matter to be resolved]

Include:
1. Company name and registration number
2. Date and location of meeting (or written resolution)
3. Directors present (or consenting)
4. Quorum confirmation
5. Resolution details with clear wording
6. Authorization of specific actions
7. Signing authority delegation if applicable
8. Effective date
9. Signature blocks for directors

Ensure compliance with Companies Act requirements for board resolutions.`,
  },

  // Property & Leases
  {
    id: 'tenancy-agreement',
    name: 'Tenancy Agreement',
    category: 'Property',
    description: 'Residential or commercial lease agreement',
    prompt: `Draft a Tenancy Agreement for [residential/commercial] property in Singapore covering:

1. Parties: Landlord and Tenant
2. Property: Full address and description
3. Term: Lease period and renewal options
4. Rent: Monthly rent, deposit, payment terms
5. Permitted Use: Residential/commercial use restrictions
6. Maintenance: Repair and maintenance obligations
7. Utilities: Responsibility for utility payments
8. Insurance: Requirements for contents and public liability
9. Alterations: Consent requirements for modifications
10. Assignment and Subletting: Transfer restrictions
11. Termination: Early termination clauses and penalties
12. Default Remedies: Rights upon breach
13. Stamp Duty: Responsibility for stamp duty payment
14. Governing Law: Singapore law

Include standard HDB/URA guidelines if applicable.`,
  },

  // Commercial Agreements
  {
    id: 'loan-agreement',
    name: 'Loan Agreement',
    category: 'Finance',
    description: 'Agreement for lending money',
    prompt: `Draft a Loan Agreement under Singapore law including:

1. Parties: Lender and Borrower
2. Loan Amount: Principal sum
3. Purpose: Use of loan proceeds
4. Interest Rate: Rate and calculation method
5. Repayment: Schedule and method of repayment
6. Security: Collateral or personal guarantees
7. Representations and Warranties
8. Covenants: Affirmative and negative covenants
9. Events of Default: Triggers for acceleration
10. Remedies: Rights upon default
11. Fees: Arrangement fees, late payment charges
12. Prepayment: Early repayment terms
13. Governing Law: Singapore law
14. Stamp Duty: Consideration

Ensure compliance with Moneylenders Act if applicable.`,
  },
  {
    id: 'partnership',
    name: 'Partnership Agreement',
    category: 'Corporate',
    description: 'Agreement for business partnership',
    prompt: `Draft a Partnership Agreement for a Singapore partnership including:

1. Parties: All partners
2. Partnership Name and Business
3. Commencement Date and Duration
4. Capital Contributions: Initial and additional capital
5. Profit Sharing: Distribution of profits and losses
6. Management: Decision-making authority and voting
7. Duties and Restrictions: Partner obligations and restrictions
8. Banking and Accounts: Financial management
9. Admission of New Partners: Procedures and requirements
10. Withdrawal and Expulsion: Exit procedures
11. Dissolution: Grounds and wind-up procedures
12. Dispute Resolution: Mediation and arbitration
13. Non-Compete: Restrictions during and after partnership
14. Governing Law: Singapore Partnership Act

Include provisions for different types of partners if applicable.`,
  },

  // Dispute Resolution
  {
    id: 'settlement-agreement',
    name: 'Settlement Agreement',
    category: 'Dispute Resolution',
    description: 'Agreement to settle disputes',
    prompt: `Draft a Settlement Agreement for resolving a dispute in Singapore:

Background: [Describe the dispute]

Include:
1. Parties: All parties to the dispute
2. Recitals: Background of dispute
3. Settlement Terms: Specific terms of settlement
4. Payment: Amount, timing, and method (if applicable)
5. Release: Mutual release of claims
6. Confidentiality: Non-disclosure of settlement terms
7. No Admission: Clause that settlement is not admission of liability
8. Full and Final Settlement: Comprehensive discharge
9. Governing Law: Singapore law
10. Enforcement: Consent judgment provisions if needed

Ensure the agreement is legally binding and enforceable.`,
  },

  // IP & Technology
  {
    id: 'ip-assignment',
    name: 'IP Assignment Agreement',
    category: 'Intellectual Property',
    description: 'Agreement for transferring intellectual property rights',
    prompt: `Draft an Intellectual Property Assignment Agreement under Singapore law:

1. Parties: Assignor and Assignee
2. IP Description: Detailed description of IP being assigned
3. Assignment: Complete transfer of all rights, title, and interest
4. Consideration: Payment or other consideration
5. Warranties: Assignor's warranties about ownership and rights
6. Further Assurance: Cooperation for registration and enforcement
7. Moral Rights: Waiver of moral rights where applicable
8. Confidentiality: Protection of proprietary information
9. Indemnities: Protection against IP infringement claims
10. Governing Law: Singapore law and IP Acts

Include specific provisions for patents, trademarks, copyrights, or trade secrets as applicable.`,
  },

  // Quick Clauses
  {
    id: 'confidentiality-clause',
    name: 'Confidentiality Clause',
    category: 'Clauses',
    description: 'Standalone confidentiality provision',
    prompt: 'Draft a comprehensive confidentiality clause suitable for inclusion in Singapore commercial contracts, covering definition of confidential information, obligations, exceptions, duration, and remedies.',
  },
  {
    id: 'force-majeure',
    name: 'Force Majeure Clause',
    category: 'Clauses',
    description: 'Clause for unforeseeable circumstances',
    prompt: 'Draft a force majeure clause suitable for Singapore contracts, covering COVID-19, natural disasters, government actions, strikes, and other unforeseeable events, including notice requirements and consequences.',
  },
  {
    id: 'dispute-resolution-clause',
    name: 'Dispute Resolution Clause',
    category: 'Clauses',
    description: 'Clause for resolving disputes',
    prompt: 'Draft a multi-tiered dispute resolution clause for Singapore contracts, including negotiation, mediation at Singapore Mediation Centre, and arbitration at SIAC under Singapore law.',
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
