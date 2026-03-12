import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface CoachMarkStep {
  target: string;
  title: string;
  description: string;
  placement?: "top" | "bottom";
}

interface CoachMarkOverlayProps {
  open: boolean;
  steps: CoachMarkStep[];
  onClose: () => void;
  onComplete?: () => void;
}

const CARD_WIDTH = 288;
const GAP = 18;

export default function CoachMarkOverlay({
  open,
  steps,
  onClose,
  onComplete,
}: CoachMarkOverlayProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  const step = steps[stepIndex];

  useEffect(() => {
    if (!open) {
      setStepIndex(0);
    }
  }, [open]);

  useLayoutEffect(() => {
    if (!open || !step) {
      setTargetRect(null);
      return;
    }

    const syncTarget = () => {
      const nextTarget = document.querySelector(step.target);
      if (!(nextTarget instanceof HTMLElement)) {
        setTargetRect(null);
        return;
      }

      nextTarget.scrollIntoView({
        block: "center",
        inline: "center",
        behavior: "smooth",
      });
      setTargetRect(nextTarget.getBoundingClientRect());
    };

    syncTarget();
    window.addEventListener("resize", syncTarget);
    window.addEventListener("scroll", syncTarget, true);
    return () => {
      window.removeEventListener("resize", syncTarget);
      window.removeEventListener("scroll", syncTarget, true);
    };
  }, [open, step]);

  const cardStyle = useMemo(() => {
    if (!targetRect) {
      return {
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    const placement = step?.placement ?? "bottom";
    const targetCenterX = targetRect.left + targetRect.width / 2;
    const left = Math.min(
      Math.max(16, targetCenterX - CARD_WIDTH / 2),
      window.innerWidth - CARD_WIDTH - 16
    );
    const top =
      placement === "top"
        ? Math.max(16, targetRect.top - GAP - 180)
        : Math.min(window.innerHeight - 220, targetRect.bottom + GAP);

    return {
      left,
      top,
    };
  }, [step?.placement, targetRect]);

  if (!open || !step || typeof document === "undefined") {
    return null;
  }

  const canGoBack = stepIndex > 0;
  const isLastStep = stepIndex === steps.length - 1;

  return createPortal(
    <div className="fixed inset-0 z-[120]">
      <div className="absolute inset-0 bg-slate-950/55 backdrop-blur-[1px]" />
      {targetRect ? (
        <div
          className="absolute rounded-3xl border-2 border-white shadow-[0_0_0_9999px_rgba(15,23,42,0.42)] transition-all"
          style={{
            left: Math.max(targetRect.left - 10, 8),
            top: Math.max(targetRect.top - 10, 8),
            width: targetRect.width + 20,
            height: targetRect.height + 20,
          }}
        />
      ) : null}

      <div
        className="absolute w-[18rem] rounded-[1.75rem] border border-white/70 bg-white/96 p-4 shadow-2xl shadow-slate-950/25"
        style={cardStyle}
      >
        <div
          className={cn(
            "absolute left-1/2 h-4 w-4 -translate-x-1/2 rotate-45 border border-white/70 bg-white/96",
            (step.placement ?? "bottom") === "top" ? "-bottom-2" : "-top-2"
          )}
        />
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-[0.28em] text-teal-700">
            First-time guide
          </p>
          <p className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
            Step {stepIndex + 1} of {steps.length}
          </p>
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{step.title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {step.description}
            </p>
          </div>
          <div className="flex items-center justify-between gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Dismiss
            </Button>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={!canGoBack}
                onClick={() => setStepIndex((current) => Math.max(0, current - 1))}
              >
                Back
              </Button>
              <Button
                type="button"
                onClick={() => {
                  if (isLastStep) {
                    onComplete?.();
                    onClose();
                    return;
                  }
                  setStepIndex((current) => current + 1);
                }}
              >
                {isLastStep ? "Finish" : "Next"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
