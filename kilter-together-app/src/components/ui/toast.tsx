import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertCircle, Info, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ToastContext,
  type ToastInput,
  type ToastRecord,
} from "@/lib/toast";
import { cn } from "@/lib/utils";

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const toastsRef = useRef<ToastRecord[]>([]);
  const dismissTimeoutsRef = useRef<Record<string, number>>({});

  useEffect(() => {
    toastsRef.current = toasts;
  }, [toasts]);

  const dismissToast = useCallback((id: string) => {
    const timeoutId = dismissTimeoutsRef.current[id];
    if (timeoutId) {
      window.clearTimeout(timeoutId);
      delete dismissTimeoutsRef.current[id];
    }
    setToasts((currentToasts) => currentToasts.filter((toast) => toast.id !== id));
  }, []);

  const toast = useCallback(
    ({
      title,
      description,
      variant = "default",
      duration = 6000,
    }: ToastInput) => {
      const existingToast = toastsRef.current.find(
        (currentToast) =>
          currentToast.title === title &&
          currentToast.description === description &&
          currentToast.variant === variant
      );
      if (existingToast) {
        return existingToast.id;
      }

      const id = `toast-${toastCounter + 1}`;
      toastCounter += 1;
      const nextToast: ToastRecord = {
        id,
        title,
        description,
        variant,
        duration,
      };

      setToasts((currentToasts) => [...currentToasts, nextToast]);

      if (typeof window !== "undefined" && duration > 0) {
        dismissTimeoutsRef.current[id] = window.setTimeout(() => dismissToast(id), duration);
      }

      return id;
    },
    [dismissToast]
  );

  useEffect(
    () => () => {
      Object.values(dismissTimeoutsRef.current).forEach((timeoutId) => {
        window.clearTimeout(timeoutId);
      });
    },
    []
  );

  return (
    <ToastContext.Provider value={{ toast, dismissToast }}>
      {children}
      <div
        aria-live="assertive"
        className="pointer-events-none fixed inset-x-4 top-4 z-[220] flex flex-col gap-3 sm:left-auto sm:right-4 sm:w-[24rem]"
      >
        {toasts.map((toastItem) => (
          <ToastCard
            key={toastItem.id}
            toast={toastItem}
            onDismiss={() => dismissToast(toastItem.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastRecord;
  onDismiss: () => void;
}) {
  const Icon = toast.variant === "destructive" ? AlertCircle : Info;

  return (
    <div
      role={toast.variant === "destructive" ? "alert" : "status"}
      className={cn(
        "pointer-events-auto rounded-2xl border px-4 py-3 shadow-xl backdrop-blur transition-all animate-in fade-in-0 slide-in-from-top-2",
        toast.variant === "destructive"
          ? "border-destructive/35 bg-white/96 text-foreground shadow-red-950/10"
          : "border-border/70 bg-white/96 text-foreground shadow-slate-950/10"
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "mt-0.5 rounded-full p-1",
            toast.variant === "destructive" ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          {toast.title ? <p className="text-sm font-semibold">{toast.title}</p> : null}
          <p className={cn("text-sm leading-6", toast.title ? "mt-1" : "")}>
            {toast.description}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7 rounded-full text-muted-foreground hover:text-foreground"
          onClick={onDismiss}
          aria-label="Dismiss notification"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
