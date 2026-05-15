"use client";

import type { RecentSummary } from "@/lib/contracts";
import { History, Layers3 } from "lucide-react";

interface RecentSummariesProps {
  items: RecentSummary[];
  onSelect: (item: RecentSummary) => void;
}

export default function RecentSummaries({
  items,
  onSelect,
}: RecentSummariesProps) {
  return (
    <section className="rounded-[1.8rem] border border-white/10 bg-black/25 p-5 backdrop-blur">
      <div className="mb-4 flex items-center gap-3">
        <div className="rounded-full border border-white/10 bg-white/[0.04] p-2 text-stone-200">
          <History className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">Recent summaries</h2>
          <p className="text-sm text-stone-400">
            Saved in this browser only for faster demo navigation.
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="rounded-[1.3rem] border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm leading-6 text-stone-400">
          Your recent activity appears here after the first successful summary.
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1">
          {items.map((item) => (
            <button
              key={`${item.payload.media.source}-${item.payload.media.id}-${item.stored_at}`}
              type="button"
              onClick={() => onSelect(item)}
              className="rounded-[1.3rem] border border-white/10 bg-white/[0.04] p-4 text-left transition hover:border-white/20 hover:bg-white/[0.06]"
            >
              <div className="flex flex-wrap items-center gap-2 text-[0.68rem] uppercase tracking-[0.24em] text-stone-400">
                <span>{item.payload.media.source_label}</span>
                <span className="rounded-full border border-white/10 px-2 py-1 text-stone-300">
                  {item.payload.meta.spoiler_level}
                </span>
              </div>

              <div className="mt-3">
                <h3 className="text-base font-semibold text-white">
                  {item.payload.media.title}
                </h3>
                <p className="mt-1 text-sm text-stone-300">
                  {item.payload.target.label}
                </p>
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 text-sm text-stone-400">
                <span>{new Date(item.stored_at).toLocaleString()}</span>
                <span className="inline-flex items-center gap-2 text-stone-300">
                  <Layers3 className="h-4 w-4" />
                  Reopen
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
