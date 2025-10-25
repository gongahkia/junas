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
  ];

  return (
    <div className="flex flex-col items-center justify-center h-[40vh] select-none overflow-hidden gap-6">
      {/* Row 1 - Fast */}
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        <div className="whitespace-nowrap animate-[marquee_25s_linear_infinite] text-3xl font-semibold text-muted-foreground">
          {row1Items.concat(row1Items).map((text, idx) => (
            <span key={idx} className="mx-8 opacity-80 hover:opacity-100 transition-opacity">{text}</span>
          ))}
        </div>
      </div>

      {/* Row 2 - Medium (reverse direction) */}
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        <div className="whitespace-nowrap animate-[marquee-reverse_35s_linear_infinite] text-3xl font-semibold text-muted-foreground">
          {row2Items.concat(row2Items).map((text, idx) => (
            <span key={idx} className="mx-8 opacity-70 hover:opacity-100 transition-opacity">{text}</span>
          ))}
        </div>
      </div>

      {/* Row 3 - Slow */}
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        <div className="whitespace-nowrap animate-[marquee_45s_linear_infinite] text-3xl font-semibold text-muted-foreground">
          {row3Items.concat(row3Items).map((text, idx) => (
            <span key={idx} className="mx-8 opacity-60 hover:opacity-100 transition-opacity">{text}</span>
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


