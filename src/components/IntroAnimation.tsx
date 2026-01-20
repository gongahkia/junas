'use client';

import { useEffect, useState } from 'react';
import { JUNAS_ASCII_LOGO } from '@/lib/constants';

const IntroAnimation = () => {
  const [visibleLines, setVisibleLines] = useState(0);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    const lines = JUNAS_ASCII_LOGO.split('\n');
    let fadeOutTimer: NodeJS.Timeout | null = null;
    const artInterval = setInterval(() => {
      setVisibleLines(prev => {
        const next = prev + 1;
        if (next >= lines.length) {
          clearInterval(artInterval);
          // Start fade out only after all lines are visible
          fadeOutTimer = setTimeout(() => {
            setFadeOut(true);
          }, 700); // Fast fade out after short pause
          return lines.length;
        }
        return next;
      });
    }, 300); // Reveal one line every 300ms

    return () => {
      clearInterval(artInterval);
      if (fadeOutTimer) clearTimeout(fadeOutTimer);
    };
  }, []);

  const lines = JUNAS_ASCII_LOGO.split('\n');
  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-white text-black transition-opacity ${fadeOut ? 'duration-200' : 'duration-500'} ${fadeOut ? 'fade-out' : 'fade-in'}`}>
      <pre className="text-xs font-mono whitespace-pre-wrap">
        {lines.slice(0, visibleLines).join('\n')}
      </pre>
    </div>
  );
};

export default IntroAnimation;
