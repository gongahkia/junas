import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface DetailGridItem {
  label: string;
  value: ReactNode;
  valueClassName?: string;
}

interface DetailGridProps {
  items: DetailGridItem[];
  className?: string;
  itemClassName?: string;
}

export default function DetailGrid({
  items,
  className,
  itemClassName,
}: DetailGridProps) {
  if (!items.length) {
    return null;
  }

  return (
    <dl className={cn("grid gap-3 sm:grid-cols-2", className)}>
      {items.map((item) => (
        <div
          key={item.label}
          className={cn("rounded-2xl border bg-muted/30 px-4 py-3", itemClassName)}
        >
          <dt className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
            {item.label}
          </dt>
          <dd className={cn("mt-2 text-sm font-medium text-foreground", item.valueClassName)}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
