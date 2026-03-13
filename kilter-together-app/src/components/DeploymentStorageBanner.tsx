import { AlertTriangle, HardDrive } from "lucide-react";
import type { RuntimeStatus } from "@/types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const units = ["KB", "MB", "GB", "TB", "PB"];
  let value = bytes;
  let unitIndex = -1;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

export default function DeploymentStorageBanner({
  status,
}: {
  status: RuntimeStatus | null;
}) {
  if (!status || (status.storage.severity !== "warning" && status.storage.severity !== "critical")) {
    return null;
  }

  const critical = status.storage.severity === "critical";
  const containerClass = critical
    ? "border-rose-200 bg-rose-50/95 text-rose-900"
    : "border-amber-200 bg-amber-50/95 text-amber-900";
  const iconClass = critical ? "text-rose-600" : "text-amber-600";

  return (
    <div className={`rounded-3xl border px-4 py-4 shadow-lg shadow-slate-900/5 ${containerClass}`}>
      <div className="flex items-start gap-3">
        {critical ? (
          <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${iconClass}`} />
        ) : (
          <HardDrive className={`mt-0.5 h-5 w-5 shrink-0 ${iconClass}`} />
        )}
        <div className="min-w-0 space-y-1.5">
          <p className="text-sm font-semibold uppercase tracking-[0.22em]">
            {critical ? "Hosted storage critically low" : "Hosted storage nearing full"}
          </p>
          <p className="text-sm leading-6">{status.storage.message}</p>
          <p className="text-xs leading-5 text-current/75">
            Used {status.storage.usage_percent.toFixed(1)}% • {formatBytes(status.storage.available_bytes)} free on{" "}
            {status.storage.mount_path}
          </p>
        </div>
      </div>
    </div>
  );
}
