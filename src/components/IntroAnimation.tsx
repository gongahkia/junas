'use client';

import { useEffect, useState } from 'react';
import { JUNAS_ASCII_LOGO } from '@/lib/constants';


const IntroAnimation = () => {
  const lines = JUNAS_ASCII_LOGO.split('\n');
  const [lineCharCounts, setLineCharCounts] = useState(Array(lines.length).fill(0));
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    let fadeOutTimer: NodeJS.Timeout | null = null;
    let lineTimers: NodeJS.Timeout[] = [];
    let charIntervals: NodeJS.Timeout[] = [];

    // For each line, schedule its character animation at the right time
    lines.forEach((line, i) => {
      const lineTimer = setTimeout(() => {
        // Animate this line's characters one by one
        let charIdx = 0;
        const charInterval = setInterval(() => {
          charIdx++;
          setLineCharCounts(prev => {
            const next = [...prev];
            next[i] = Math.min(charIdx, line.length);
            return next;
          });
          if (charIdx >= line.length) {
            clearInterval(charInterval);
            // If this is the last line, start fade out after a pause
            if (i === lines.length - 1) {
              fadeOutTimer = setTimeout(() => {
                setFadeOut(true);
              }, 700);
            }
          }
        }, 20); // Character-by-character speed
        charIntervals.push(charInterval);
      }, i * 300); // Line-by-line timing
      lineTimers.push(lineTimer);
    });

    return () => {
      lineTimers.forEach(clearTimeout);
      charIntervals.forEach(clearInterval);
      if (fadeOutTimer) clearTimeout(fadeOutTimer);
    };
  }, [lines.length]);

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-white text-black transition-opacity ${fadeOut ? 'duration-200' : 'duration-500'} ${fadeOut ? 'fade-out' : 'fade-in'}`}>
      <pre className="text-xs font-mono whitespace-pre-wrap">
        {lines.map((line, i) => line.substring(0, lineCharCounts[i])).join('\n')}
      </pre>
    </div>
  );
};

export default IntroAnimation;
