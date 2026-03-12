import { Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface OnboardingCalloutProps {
  title: string;
  description: string;
  steps: string[];
  onDismiss: () => void;
  actionLabel?: string;
  onAction?: () => void;
}

export default function OnboardingCallout({
  title,
  description,
  steps,
  onDismiss,
  actionLabel,
  onAction,
}: OnboardingCalloutProps) {
  return (
    <Dialog open onOpenChange={(nextOpen) => !nextOpen && onDismiss()}>
      <DialogContent className="max-h-[min(92vh,48rem)] max-w-[calc(100vw-1rem)] overflow-hidden border-0 bg-white/95 p-0 shadow-2xl shadow-teal-950/20 backdrop-blur sm:max-w-4xl sm:rounded-[2rem]">
        <div className="grid max-h-[min(92vh,48rem)] gap-5 overflow-y-auto p-5 sm:gap-6 sm:p-8">
          <DialogHeader className="gap-4 text-left">
            <div className="inline-flex w-fit items-center gap-2 rounded-full bg-teal-100 px-4 py-1.5 text-xs font-medium uppercase tracking-[0.28em] text-teal-800">
              <Lightbulb className="h-3.5 w-3.5" />
              First-time guide
            </div>
            <div className="space-y-3">
              <DialogTitle className="text-2xl font-semibold tracking-tight sm:text-4xl">
                {title}
              </DialogTitle>
              <DialogDescription className="text-sm leading-6 text-slate-600 sm:text-lg sm:leading-7">
                {description}
              </DialogDescription>
            </div>
          </DialogHeader>

          <ol className="grid gap-3 text-sm text-slate-700 sm:text-base">
            {steps.map((step, index) => (
              <li
                key={step}
                className="flex items-start gap-3 rounded-2xl border border-teal-200/70 bg-teal-50/70 px-4 py-4"
              >
                <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-100 text-sm font-semibold text-teal-700">
                  {index + 1}
                </span>
                <span className="leading-7">{step}</span>
              </li>
            ))}
          </ol>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            {actionLabel && onAction ? (
              <Button type="button" className="w-full sm:w-auto" onClick={onAction}>
                {actionLabel}
              </Button>
            ) : null}
            <Button type="button" variant="ghost" className="w-full sm:w-auto" onClick={onDismiss}>
              Dismiss
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
