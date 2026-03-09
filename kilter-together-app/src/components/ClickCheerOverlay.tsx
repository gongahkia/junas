import { useEffect, useRef, useState, type CSSProperties } from "react";
import { loadUserPrefs } from "@/lib/user-prefs";

interface CheerInstance {
  id: number;
  x: number;
  y: number;
  text: string;
  drift: number;
  tilt: number;
}

const cheerPhrases = [
  "allez!",
  "がんばって!",
  "加油!",
  "¡vamos!",
  "forza!",
  "hup!",
  "давай!",
  "화이팅!",
  "yalla!",
  "bora!",
  "πάμε!",
  "kom igen!",
  "haydi!",
];

const CHEER_LIFETIME_MS = 1400;

export default function ClickCheerOverlay() {
  const [cheers, setCheers] = useState<CheerInstance[]>([]);
  const nextIDRef = useRef(0);
  const phraseIndexRef = useRef(0);
  const timeoutIDsRef = useRef<number[]>([]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || event.button !== 0) {
        return;
      }

      if (!loadUserPrefs().settings.clickCheersEnabled) {
        return;
      }

      const id = nextIDRef.current++;
      const text = cheerPhrases[phraseIndexRef.current % cheerPhrases.length];
      phraseIndexRef.current += 1;

      const nextCheer: CheerInstance = {
        id,
        x: event.clientX,
        y: event.clientY,
        text,
        drift: Math.round((Math.random() - 0.5) * 28),
        tilt: Number(((Math.random() - 0.5) * 14).toFixed(2)),
      };

      setCheers((currentCheers) => [...currentCheers, nextCheer]);

      const timeoutID = window.setTimeout(() => {
        setCheers((currentCheers) =>
          currentCheers.filter((cheerInstance) => cheerInstance.id !== id)
        );
        timeoutIDsRef.current = timeoutIDsRef.current.filter(
          (storedTimeoutID) => storedTimeoutID !== timeoutID
        );
      }, CHEER_LIFETIME_MS);

      timeoutIDsRef.current.push(timeoutID);
    };

    window.addEventListener("pointerdown", handlePointerDown);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      timeoutIDsRef.current.forEach((timeoutID) => window.clearTimeout(timeoutID));
      timeoutIDsRef.current = [];
    };
  }, []);

  if (cheers.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed inset-0 z-[120] overflow-hidden">
      {cheers.map((cheer) => (
        <span
          key={cheer.id}
          className="click-cheer"
          style={
            {
              left: `${cheer.x}px`,
              top: `${cheer.y}px`,
              "--click-cheer-drift": `${cheer.drift}px`,
              "--click-cheer-tilt": `${cheer.tilt}deg`,
            } as CSSProperties
          }
        >
          {cheer.text}
        </span>
      ))}
    </div>
  );
}
