import { useEffect, useState } from "react";
import { api } from "@/api";
import type { ProviderCapability } from "@/types";
import { fallbackProviderCapabilities } from "@/lib/provider-capabilities";

export function useProviderCapabilities() {
  const [capabilities, setCapabilities] = useState<ProviderCapability[]>(
    () => fallbackProviderCapabilities()
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const nextCapabilities = await api.getProviderCapabilities();
        if (!cancelled && nextCapabilities.length > 0) {
          setCapabilities(nextCapabilities);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    capabilities,
    loading,
  };
}
