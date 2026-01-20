'use client';

import { useEffect, useState } from 'react';
import { JUNAS_ASCII_LOGO } from '@/lib/constants';


const IntroAnimation = () => {
  const lines = JUNAS_ASCII_LOGO.split('\n');
  const [lineCharCounts, setLineCharCounts] = useState(Array(lines.length).fill(0));
  const [fadeOut, setFadeOut] = useState(false);
  const [readyToFade, setReadyToFade] = useState(false);


  useEffect(() => {
    let lineTimers: NodeJS.Timeout[] = [];
    let charIntervals: NodeJS.Timeout[] = [];

    lines.forEach((line, i) => {
      const lineTimer = setTimeout(() => {
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
            // If this is the last line, allow fade out trigger
            if (i === lines.length - 1) {
              setTimeout(() => setReadyToFade(true), 200); // Small pause for polish
            }
          }
        }, 20);
        charIntervals.push(charInterval);
      }, i * 300);
      lineTimers.push(lineTimer);
    });

    return () => {
      lineTimers.forEach(clearTimeout);
      charIntervals.forEach(clearInterval);
    };
  }, [lines.length]);

  // Handler for user interaction to trigger fade out
  useEffect(() => {
    if (!readyToFade) return;
    const handle = (e: KeyboardEvent | MouseEvent) => {
      if (fadeOut) return;
      if (e instanceof KeyboardEvent && e.code !== 'Space') return;
      setFadeOut(true);
    };
    window.addEventListener('mousedown', handle);
    window.addEventListener('keydown', handle);
    return () => {
      window.removeEventListener('mousedown', handle);
      window.removeEventListener('keydown', handle);
    };
  }, [readyToFade, fadeOut]);

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-white text-black transition-opacity ${fadeOut ? 'duration-200' : 'duration-500'} ${fadeOut ? 'fade-out' : 'fade-in'}`}>
      <div className="flex flex-col items-center">
        <pre className="text-xs font-mono whitespace-pre-wrap">
          {lines.map((line, i) => line.substring(0, lineCharCounts[i])).join('\n')}
        </pre>
        {readyToFade && !fadeOut && (
          <div className="mt-2 text-xs font-mono text-muted-foreground">v0.1.0</div>
        )}
      </div>
      {readyToFade && !fadeOut && (
        <div className="absolute bottom-8 left-0 right-0 text-center text-xs text-muted-foreground select-none pointer-events-none">
          Click or press <b>Space</b> to continue
        </div>
      )}
    </div>
  );
};

export default IntroAnimation;
