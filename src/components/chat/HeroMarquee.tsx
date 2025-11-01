'use client';

export function HeroMarquee() {

const row1Items = [
    'Contract analysis',
    'Case law and research',
    'Statutory analysis',
    'Document drafting',
    'Citation & research',
    'Legal compliance review',
    'Due diligence',
    'Regulatory analysis',
    'Litigation support',
    'IP law research',
    'Contract intelligence platform',
    'Legal document automation',
    'Full-text search repository',
    'Automated clause extraction',
    'Legal precedent matching',
    'Risk flag identification',
    'Cross-reference analysis',
    'Obligation tracking system',
    'Regulation mapping tools',
    'Legal AI summarization',
    'Document version control',
    'Metadata extraction',
    'Clause library management',
    'Redline comparison',
    'Legal language standardization',
    'Intellectual property management',
    'Patent prior art search',
    'Trademark monitoring',
    'Copyright compliance',
    'Trade secret protection',
    'Litigation document assembly',
    'Evidence chain management',
    'Discovery workflow automation',
    'Legal hold management',
    'Privileged information filtering',
    'Deposition transcript analysis',
    'Motion template library',
    'Legal research database integration',
    'Multi-jurisdiction analysis',
    'Regulatory deadline tracking',
  ];

  const row2Items = [
    'Employment law',
    'Corporate governance',
    'Mergers & acquisitions',
    'Dispute resolution',
    'Legal opinions',
    'Risk assessment',
    'Policy drafting',
    'Contractual obligations',
    'Legal memoranda',
    'Precedent analysis',
    'Board resolutions management',
    'Shareholder agreement tracking',
    'Stock option administration',
    'Employment contract templates',
    'Separation agreement drafting',
    'Non-disclosure agreement management',
    'Transaction closing checklist',
    'Due diligence questionnaire',
    'Acquisition integration planning',
    'Vendor contract management',
    'Commercial negotiation tools',
    'Terms and conditions builder',
    'Service level agreement tracking',
    'Insurance policy management',
    'Claims management system',
    'Compliance certification database',
    'Internal audit scheduling',
    'Policy repository management',
    'Training requirement tracking',
    'Incident reporting system',
    'Whistleblower complaint management',
    'Conflict of interest disclosure',
    'Anti-corruption compliance',
    'Data privacy impact assessment',
    'Third-party vendor assessment',
    'Budget and billing tracking',
    'Matter management system',
    'Time and expense tracking',
    'Invoice reconciliation',
    'Legal workflow automation',
  ];

  const row3Items = [
    'Singapore law',
    'Statutory interpretation',
    'Legislative review',
    'Legal research',
    'Case summaries',
    'Legal citations',
    'Judicial decisions',
    'Legal frameworks',
    'Compliance audits',
    'Legal documentation',
    'Singapore statute library',
    'Supreme Court decision database',
    'High Court precedent compiler',
    'District Court case tracker',
    'Tribunal judgments repository',
    'Singapore Court of Appeal records',
    'PDPA enforcement case law',
    'Companies Act interpretation guide',
    'Constitution Article reference',
    'Subsidiary legislation tracker',
    'Parliamentary debate records',
    'Singapore law journal access',
    'Legal profession regulation guide',
    'Singapore Bar association resources',
    'Law Society Singapore directory',
    'Court filing deadline calculator',
    'Singapore Rules of Court navigator',
    'Evidence Act case digest',
    'Penal Code commentary',
    'Insolvency law tracker',
    'Environmental Protection Act guide',
    'Consumer Protection Act resources',
    'Workplace Safety Act provisions',
    'Foreign investment regulation',
    'Singapore tax law compiler',
    'Real estate transaction guide',
    'Conveyancing checklist',
    'Land Titles Act reference',
    'Probate and succession planning',
    'Wills Act provisions database',
  ];

  return (
    <div className="flex flex-col items-center justify-center h-[30vh] md:h-[40vh] select-none overflow-hidden gap-3 md:gap-6">
      {/* Row 1 - Fast */}
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-16 md:w-32 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-16 md:w-32 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        <div className="whitespace-nowrap animate-[marquee_25s_linear_infinite] text-lg md:text-2xl lg:text-3xl font-semibold text-muted-foreground">
          {row1Items.concat(row1Items).map((text, idx) => (
            <span key={idx} className="mx-4 md:mx-8 opacity-80 hover:opacity-100 transition-opacity">{text}</span>
          ))}
        </div>
      </div>

      {/* Row 2 - Medium (reverse direction) */}
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-16 md:w-32 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-16 md:w-32 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        <div className="whitespace-nowrap animate-[marquee-reverse_35s_linear_infinite] text-lg md:text-2xl lg:text-3xl font-semibold text-muted-foreground">
          {row2Items.concat(row2Items).map((text, idx) => (
            <span key={idx} className="mx-4 md:mx-8 opacity-70 hover:opacity-100 transition-opacity">{text}</span>
          ))}
        </div>
      </div>

      {/* Row 3 - Slow */}
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-16 md:w-32 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-16 md:w-32 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        <div className="whitespace-nowrap animate-[marquee_45s_linear_infinite] text-lg md:text-2xl lg:text-3xl font-semibold text-muted-foreground">
          {row3Items.concat(row3Items).map((text, idx) => (
            <span key={idx} className="mx-4 md:mx-8 opacity-60 hover:opacity-100 transition-opacity">{text}</span>
          ))}
        </div>
      </div>

      <style jsx>{`
        @keyframes marquee {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        @keyframes marquee-reverse {
          from { transform: translateX(-50%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}


