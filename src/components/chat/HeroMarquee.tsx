'use client';

export function HeroMarquee() {
  const items = [
    'Contract analysis',
    'Case law and research',
    'Statutory analysis',
    'Document drafting',
    'Citation & research',
  ];

  return (
    <div className="flex items-center justify-center h-[40vh] select-none overflow-hidden">
      <div className="relative w-full">
        <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-background to-transparent pointer-events-none" />
        <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-background to-transparent pointer-events-none" />
        <div className="whitespace-nowrap animate-[marquee_18s_linear_infinite] text-4xl font-semibold text-muted-foreground">
          {items.concat(items).map((text, idx) => (
            <span key={idx} className="mx-8 opacity-80 hover:opacity-100 transition-opacity">{text}</span>
          ))}
        </div>
      </div>
      <style jsx>{`
        @keyframes marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
      `}</style>
    </div>
  );
}


