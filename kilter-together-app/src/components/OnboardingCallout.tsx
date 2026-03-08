import { Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
    <Card className="border-teal-200 bg-teal-50/80 shadow-sm">
      <CardHeader className="gap-3">
        <div className="inline-flex w-fit items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-teal-700">
          <Lightbulb className="h-3.5 w-3.5" />
          First-time guide
        </div>
        <div>
          <CardTitle className="text-xl">{title}</CardTitle>
          <CardDescription className="mt-2 text-sm leading-6 text-teal-950/70">
            {description}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3">
        <ol className="grid gap-2 text-sm text-teal-950/80">
          {steps.map((step, index) => (
            <li key={step} className="rounded-2xl border border-teal-200/70 bg-white/80 px-4 py-3">
              <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-teal-100 text-xs font-semibold text-teal-700">
                {index + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap gap-2">
          {actionLabel && onAction ? (
            <Button type="button" size="sm" onClick={onAction}>
              {actionLabel}
            </Button>
          ) : null}
          <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>
            Dismiss
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
