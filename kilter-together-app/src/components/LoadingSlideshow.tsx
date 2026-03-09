import { useEffect, useState } from "react";
import BrandWordmark from "@/components/BrandWordmark";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface LoadingSlideshowProps {
  title: string;
  description: string;
  detail?: string;
  eyebrow?: string;
}

const loadingFrames = ["/loading/1.png", "/loading/2.png", "/loading/3.png", "/loading/4.png"];
const endingFrames = ["/loading/5-1.png", "/loading/5-2.png"];
const FRAMES_PER_LOOP = loadingFrames.length + 1;
const FRAME_INTERVAL_MS = 900;

export default function LoadingSlideshow({
  title,
  description,
  detail,
  eyebrow = "Preparing Kilter Together",
}: LoadingSlideshowProps) {
  const [tick, setTick] = useState(0);
  const frameIndex = tick % FRAMES_PER_LOOP;
  const endingVariant = Math.floor(tick / FRAMES_PER_LOOP) % endingFrames.length;
  const currentFrame =
    frameIndex === loadingFrames.length
      ? endingFrames[endingVariant]
      : loadingFrames[frameIndex];

  useEffect(() => {
    const intervalID = window.setInterval(() => {
      setTick((currentTick) => currentTick + 1);
    }, FRAME_INTERVAL_MS);

    return () => window.clearInterval(intervalID);
  }, []);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))] px-6 py-10">
      <div className="mx-auto flex min-h-[70vh] max-w-6xl items-center justify-center">
        <div className="grid w-full max-w-5xl gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:items-center">
          <div className="rounded-[2rem] border border-white/70 bg-white/75 p-4 shadow-xl shadow-teal-950/10 backdrop-blur">
            <div className="relative overflow-hidden rounded-[1.5rem] bg-[radial-gradient(circle_at_top,_rgba(20,184,166,0.14),_transparent_45%),linear-gradient(180deg,_rgba(248,250,252,0.98),_rgba(241,245,249,0.9))] p-4">
              <div className="aspect-[450/574] overflow-hidden rounded-[1.25rem]">
                <img
                  key={currentFrame}
                  src={currentFrame}
                  alt=""
                  aria-hidden="true"
                  className="h-full w-full object-contain"
                />
              </div>
            </div>
          </div>

          <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader className="gap-4">
              <p className="text-xs font-medium uppercase tracking-[0.32em] text-teal-700">
                {eyebrow}
              </p>
              <div className="leading-none">
                <BrandWordmark />
              </div>
              <div>
                <CardTitle className="text-3xl">{title}</CardTitle>
                <CardDescription className="mt-3 text-base leading-7">
                  {description}
                </CardDescription>
              </div>
            </CardHeader>
            {detail ? (
              <CardContent className="text-sm leading-7 text-muted-foreground">
                {detail}
              </CardContent>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}
