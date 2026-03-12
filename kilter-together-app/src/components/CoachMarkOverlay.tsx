import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
const DEFAULT_CARD_HEIGHT = 248;
const EDGE_PADDING = 16;
const GAP = 18;

function areStepIndexListsEqual(left: number[], right: number[]) {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export default function CoachMarkOverlay({
  open,
  steps,
  onClose,
  onComplete,
}: CoachMarkOverlayProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [availableStepIndices, setAvailableStepIndices] = useState<number[]>([]);
  const [cardHeight, setCardHeight] = useState(DEFAULT_CARD_HEIGHT);
  const cardRef = useRef<HTMLDivElement | null>(null);

  const step = steps[stepIndex];
  const activeStepPosition = availableStepIndices.indexOf(stepIndex);
  const visibleStepCount = availableStepIndices.length;

  useEffect(() => {
    if (!open) {
      setStepIndex(0);
      setTargetRect(null);
      setAvailableStepIndices([]);
      setCardHeight(DEFAULT_CARD_HEIGHT);
    }
  }, [open]);

  useLayoutEffect(() => {
    if (!open || !step) {
      setTargetRect(null);
      return;
    }

    const syncTarget = (scrollBehavior?: ScrollBehavior) => {
      const nextAvailableStepIndices = steps.reduce<number[]>((indices, candidate, index) => {
        const candidateTarget = document.querySelector(candidate.target);
        if (candidateTarget instanceof HTMLElement) {
          indices.push(index);
        }
        return indices;
      }, []);

      setAvailableStepIndices((current) =>
        areStepIndexListsEqual(current, nextAvailableStepIndices)
          ? current
          : nextAvailableStepIndices
      );

      const resolvedStepIndex =
        nextAvailableStepIndices.includes(stepIndex)
          ? stepIndex
          : nextAvailableStepIndices.find((index) => index > stepIndex) ??
            nextAvailableStepIndices[0];

      if (resolvedStepIndex === undefined) {
        setTargetRect(null);
        return;
      }

      if (resolvedStepIndex !== stepIndex) {
        setStepIndex(resolvedStepIndex);
        return;
      }

      const nextTarget = document.querySelector(steps[resolvedStepIndex].target);
      if (!(nextTarget instanceof HTMLElement)) {
        setTargetRect(null);
        return;
      }

      if (scrollBehavior) {
        nextTarget.scrollIntoView({
          block: "center",
          inline: "center",
          behavior: scrollBehavior,
        });
      }
      setTargetRect(nextTarget.getBoundingClientRect());
    };

    syncTarget("smooth");

    const handleViewportChange = () => syncTarget();

    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [open, step, stepIndex, steps]);

  useLayoutEffect(() => {
    if (!open || !cardRef.current) {
      return;
    }

    const nextCardHeight = Math.ceil(cardRef.current.getBoundingClientRect().height);
    if (nextCardHeight > 0 && nextCardHeight !== cardHeight) {
      setCardHeight(nextCardHeight);
    }
  }, [cardHeight, open, step?.description, step?.title, visibleStepCount]);

  const resolvedPlacement = useMemo(() => {
    if (!targetRect) {
      return step?.placement ?? "bottom";
    }

    const preferredPlacement = step?.placement ?? "bottom";
    const canFitAbove = targetRect.top >= cardHeight + GAP + EDGE_PADDING;
    const canFitBelow =
      window.innerHeight - targetRect.bottom >= cardHeight + GAP + EDGE_PADDING;

    if (preferredPlacement === "top" && !canFitAbove && canFitBelow) {
      return "bottom";
    }

    if (preferredPlacement === "bottom" && !canFitBelow && canFitAbove) {
      return "top";
    }

    return preferredPlacement;
  }, [cardHeight, step?.placement, targetRect]);

  const cardStyle = useMemo(() => {
    if (!targetRect) {
      return {
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    const targetCenterX = targetRect.left + targetRect.width / 2;
    const maxLeft = Math.max(EDGE_PADDING, window.innerWidth - CARD_WIDTH - EDGE_PADDING);
    const maxTop = Math.max(EDGE_PADDING, window.innerHeight - cardHeight - EDGE_PADDING);
    const left = clamp(
      targetCenterX - CARD_WIDTH / 2,
      EDGE_PADDING,
      maxLeft
    );
    const top =
      resolvedPlacement === "top"
        ? clamp(targetRect.top - GAP - cardHeight, EDGE_PADDING, maxTop)
        : clamp(targetRect.bottom + GAP, EDGE_PADDING, maxTop);

    return {
      left,
      top,
    };
  }, [cardHeight, resolvedPlacement, targetRect]);

  if (
    !open ||
    !step ||
    typeof document === "undefined" ||
    (availableStepIndices.length > 0 && activeStepPosition === -1) ||
    visibleStepCount === 0
  ) {
    return null;
  }

  const canGoBack = activeStepPosition > 0;
  const isLastStep = activeStepPosition === visibleStepCount - 1;

  return createPortal(
    <div className="fixed inset-0 z-[120]">
      <div className="absolute inset-0 bg-slate-950/55 backdrop-blur-[1px]" />
      {targetRect ? (
        <div
          data-slot="coachmark-highlight"
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
        ref={cardRef}
        data-slot="coachmark-card"
        className="absolute w-[18rem] rounded-[1.75rem] border border-white/70 bg-white/96 p-4 shadow-2xl shadow-slate-950/25"
        style={cardStyle}
      >
        <div
          data-slot="coachmark-pointer"
          className={cn(
            "absolute left-1/2 h-4 w-4 -translate-x-1/2 rotate-45 border border-white/70 bg-white/96",
            resolvedPlacement === "top" ? "-bottom-2" : "-top-2"
          )}
        />
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-[0.28em] text-teal-700">
            First-time guide
          </p>
          <p className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
            Step {activeStepPosition + 1} of {visibleStepCount}
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
                onClick={() => {
                  const previousStepIndex = availableStepIndices[activeStepPosition - 1];
                  if (previousStepIndex !== undefined) {
                    setStepIndex(previousStepIndex);
                  }
                }}
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

                  const nextStepIndex = availableStepIndices[activeStepPosition + 1];
                  if (nextStepIndex !== undefined) {
                    setStepIndex(nextStepIndex);
                  }
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
