'use client';

import { useEffect, useState } from 'react';
import { JUNAS_ASCII_LOGO } from '@/lib/constants';

const IntroAnimation = () => {
  const [visibleChars, setVisibleChars] = useState(0);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    const artInterval = setInterval(() => {
      setVisibleChars(prev => {
        const next = prev + 20;
        if (next >= JUNAS_ASCII_LOGO.length) {
          clearInterval(artInterval);
          return JUNAS_ASCII_LOGO.length;
        }
        return next;
      });
    }, 10);

    const fadeOutTimer = setTimeout(() => {
      setFadeOut(true);
    }, 2000); // Start fade out after 2 seconds

    return () => {
      clearInterval(artInterval);
      clearTimeout(fadeOutTimer);
    };
  }, []);

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-white text-black transition-opacity duration-500 ${fadeOut ? 'fade-out' : 'fade-in'}`}>
      <pre className="text-xs font-mono whitespace-pre-wrap">
        {JUNAS_ASCII_LOGO.substring(0, visibleChars)}
      </pre>
    </div>
  );
};

export default IntroAnimation;
