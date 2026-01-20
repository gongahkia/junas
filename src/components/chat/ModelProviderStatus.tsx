import { useEffect, useState } from 'react';
import { getModelsWithStatus } from '@/lib/ml/model-manager';

export function ModelProviderStatus() {
  const [modelCount, setModelCount] = useState(0);
  const [providerCount, setProviderCount] = useState(0);
  const [providerNames, setProviderNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStatus() {
      // Local models
      const models = getModelsWithStatus();
      setModelCount(models.filter(m => m.isDownloaded).length);

      // Providers
      try {
        const res = await fetch('/api/auth/keys');
        if (res.ok) {
          const { configured } = await res.json();
          const names = Object.entries(configured)
            .filter(([_, v]) => v)
            .map(([k]) => k.charAt(0).toUpperCase() + k.slice(1));
          setProviderCount(names.length);
          setProviderNames(names);
        } else {
          setProviderCount(0);
          setProviderNames([]);
        }
      } catch {
        setProviderCount(0);
        setProviderNames([]);
      }
      setLoading(false);
    }
    fetchStatus();
  }, []);

  if (loading) return <span className="text-xs text-muted-foreground">[ ... ]</span>;
  if (modelCount === 0 && providerCount === 0) return <span className="text-xs text-muted-foreground">[ No models ✗ ]</span>;

  const parts = [];
  if (modelCount > 0) parts.push(`${modelCount} local model${modelCount > 1 ? 's' : ''}`);
  if (providerCount > 0) parts.push(`${providerNames.join(', ')} API`);

  return <span className="text-xs text-muted-foreground">[ {parts.join(' • ')} ]</span>;
}
