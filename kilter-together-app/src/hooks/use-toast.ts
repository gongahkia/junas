import { useCallback, useContext } from "react";
import { ToastContext } from "@/lib/toast";

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider.");
  }

  return context;
}

export function useErrorToast() {
  const { toast } = useToast();

  return useCallback(
    (description: string, title = "Something went wrong") => {
      toast({
        title,
        description,
        variant: "destructive",
      });
    },
    [toast]
  );
}
