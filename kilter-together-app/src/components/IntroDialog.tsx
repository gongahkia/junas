import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface IntroDialogFeature {
  icon: ReactNode;
  title: string;
  description: string;
}

interface IntroDialogProps {
  open: boolean;
  title: string;
  description: string;
  features: IntroDialogFeature[];
  onDismiss: () => void;
  dismissLabel?: string;
}

export default function IntroDialog({
  open,
  title,
  description,
  features,
  onDismiss,
  dismissLabel = "Continue",
}: IntroDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onDismiss()}>
      <DialogContent className="max-w-[calc(100vw-1.5rem)] border-0 bg-white/95 p-0 shadow-2xl shadow-teal-950/20 backdrop-blur sm:max-w-5xl sm:rounded-[2rem] lg:max-w-6xl">
        <div className="grid gap-8 p-6 sm:p-10">
          <DialogHeader className="gap-5 text-left">
            <div className="inline-flex w-fit items-center gap-2 rounded-full bg-teal-100 px-4 py-1.5 text-xs font-medium uppercase tracking-[0.28em] text-teal-800">
              <Sparkles className="h-3.5 w-3.5" />
              Welcome
            </div>
            <div className="space-y-3">
              <DialogTitle className="text-4xl font-semibold tracking-tight sm:text-6xl">
                {title}
              </DialogTitle>
              <DialogDescription className="max-w-3xl text-base leading-8 text-slate-600 sm:text-xl">
                {description}
              </DialogDescription>
            </div>
          </DialogHeader>

          <div className="grid gap-4 lg:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-6 shadow-lg shadow-slate-900/8"
              >
                <div className="mb-5 inline-flex rounded-full bg-teal-100 p-4 text-teal-700">
                  {feature.icon}
                </div>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                  {feature.title}
                </h2>
                <p className="mt-4 text-base leading-8 text-slate-600">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>

          <div className="flex justify-end">
            <Button type="button" size="lg" className="min-w-40" onClick={onDismiss}>
              {dismissLabel}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
