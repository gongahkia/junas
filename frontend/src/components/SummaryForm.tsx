"use client";

import type {
  SearchResult,
  SourceOption,
  SpoilerLevel,
  TargetsPayload,
} from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { Loader2, Search, Sparkles } from "lucide-react";

interface SummaryFormProps {
  sourceOptions: SourceOption[];
  source: SourceOption["id"];
  query: string;
  selectedMedia: SearchResult | null;
  targetsPayload: TargetsPayload | null;
  selectedTargetId: string;
  spoilerLevel: SpoilerLevel;
  searchResults: SearchResult[];
  searchLoading: boolean;
  targetsLoading: boolean;
  summarizing: boolean;
  onSourceChange: (source: SourceOption["id"]) => void;
  onQueryChange: (value: string) => void;
  onSelectMedia: (media: SearchResult) => void;
  onTargetChange: (targetId: string) => void;
  onSpoilerLevelChange: (spoilerLevel: SpoilerLevel) => void;
  onSummarize: () => void;
}

const spoilerStyles: Record<SpoilerLevel, string> = {
  light: "border-white/10 bg-white/5 text-stone-100",
  standard: "border-cyan-400/30 bg-cyan-400/10 text-cyan-100",
  full: "border-orange-400/30 bg-orange-400/10 text-orange-100",
};

export default function SummaryForm({
  sourceOptions,
  source,
  query,
  selectedMedia,
  targetsPayload,
  selectedTargetId,
  spoilerLevel,
  searchResults,
  searchLoading,
  targetsLoading,
  summarizing,
  onSourceChange,
  onQueryChange,
  onSelectMedia,
  onTargetChange,
  onSpoilerLevelChange,
  onSummarize,
}: SummaryFormProps) {
  const activeSource =
    sourceOptions.find((option) => option.id === source) ?? sourceOptions[0];
  const selectedTarget =
    targetsPayload?.targets.find((target) => target.id === selectedTargetId) ??
    null;
  const canSummarize = Boolean(selectedMedia && selectedTargetId);

  return (
    <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-black/30 shadow-[0_40px_120px_-40px_rgba(0,0,0,0.85)] backdrop-blur">
      <div className="grid gap-8 p-6 lg:grid-cols-[1.1fr_0.9fr] lg:p-8">
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.32em] text-stone-300">
              <Sparkles className="h-3.5 w-3.5" />
              Guided summary workflow
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold text-white lg:text-3xl">
                Search first, then decide exactly what to skip.
              </h2>
              <p className="max-w-2xl text-sm leading-6 text-stone-300 lg:text-base">
                Anime and TV can go episode by episode. The remaining sources stay
                title-level, but the spoiler control and structured output stay
                consistent across the product.
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {sourceOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => onSourceChange(option.id)}
                className={cn(
                  "group rounded-[1.4rem] border p-4 text-left transition duration-200",
                  option.id === source
                    ? "border-white/40 bg-white/10"
                    : "border-white/10 bg-white/5 hover:border-white/25 hover:bg-white/8",
                )}
              >
                <div
                  className={cn(
                    "mb-4 h-1.5 rounded-full bg-gradient-to-r opacity-90",
                    option.accent,
                  )}
                />
                <p className="text-[0.62rem] uppercase tracking-[0.28em] text-stone-400">
                  {option.eyebrow}
                </p>
                <h3 className="mt-2 text-lg font-semibold text-white">
                  {option.label}
                </h3>
                <p className="mt-2 text-sm leading-6 text-stone-300">
                  {option.description}
                </p>
              </button>
            ))}
          </div>

          <div className="rounded-[1.6rem] border border-white/10 bg-stone-950/80 p-4">
            <label
              htmlFor="media-search"
              className="mb-3 block text-xs uppercase tracking-[0.28em] text-stone-400"
            >
              Search {activeSource.label}
            </label>
            <div className="flex items-center gap-3 rounded-[1.3rem] border border-white/10 bg-white/5 px-4 py-3">
              <Search className="h-4 w-4 text-stone-400" />
              <input
                id="media-search"
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder={`Search ${activeSource.label.toLowerCase()} titles`}
                className="w-full bg-transparent text-base text-white outline-none placeholder:text-stone-500"
              />
              {searchLoading ? (
                <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
              ) : null}
            </div>
            <p className="mt-3 text-sm text-stone-400">
              Results update as you type once the query is long enough to be
              meaningful.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs uppercase tracking-[0.28em] text-stone-400">
                Matching titles
              </h3>
              <span className="text-xs text-stone-500">
                {searchResults.length} found
              </span>
            </div>
            <div className="grid max-h-[26rem] gap-3 overflow-y-auto pr-1">
              {query.trim().length < 2 ? (
                <EmptyHint text="Choose a source and type at least two characters to start searching." />
              ) : null}

              {query.trim().length >= 2 &&
              !searchLoading &&
              searchResults.length === 0 ? (
                <EmptyHint text="No matches yet. Try a broader title or a different source." />
              ) : null}

              {searchResults.map((result) => {
                const isSelected = selectedMedia?.id === result.id;

                return (
                  <button
                    key={`${result.source}-${result.id}`}
                    type="button"
                    onClick={() => onSelectMedia(result)}
                    className={cn(
                      "grid gap-4 rounded-[1.4rem] border p-4 text-left transition md:grid-cols-[88px_1fr]",
                      isSelected
                        ? "border-cyan-300/50 bg-cyan-300/10"
                        : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/8",
                    )}
                  >
                    <Poster imageUrl={result.image_url} title={result.title} />
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-white/10 bg-black/30 px-2 py-1 text-[0.68rem] uppercase tracking-[0.2em] text-stone-300">
                          {result.source_label}
                        </span>
                        <span className="rounded-full border border-white/10 bg-black/30 px-2 py-1 text-[0.68rem] uppercase tracking-[0.2em] text-stone-400">
                          {result.supports_segments ? "Segment-ready" : "Title-only"}
                        </span>
                      </div>
                      <div>
                        <h4 className="text-lg font-semibold text-white">
                          {result.title}
                        </h4>
                        {result.subtitle ? (
                          <p className="mt-1 text-sm text-stone-300">
                            {result.subtitle}
                          </p>
                        ) : null}
                      </div>
                      <p className="text-sm text-stone-400">
                        {isSelected
                          ? "Selected. Pick a target and spoiler level on the right."
                          : "Select this title to load available summary targets."}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="space-y-5 rounded-[1.8rem] border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.18),_transparent_36%),linear-gradient(180deg,rgba(17,24,39,0.96),rgba(7,10,16,0.98))] p-5">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/70">
              Target selection
            </p>
            <h3 className="text-2xl font-semibold text-white">
              {selectedMedia ? selectedMedia.title : "Pick a title to continue"}
            </h3>
            <p className="text-sm leading-6 text-stone-300">
              {selectedMedia
                ? "Choose the exact slice you want summarized and how much spoiler detail you can tolerate."
                : "This panel becomes active after you select a result from the left-hand column."}
            </p>
          </div>

          <div className="rounded-[1.4rem] border border-white/10 bg-black/20 p-4">
            <p className="mb-3 text-xs uppercase tracking-[0.24em] text-stone-400">
              Summary target
            </p>
            <select
              value={selectedTargetId}
              onChange={(event) => onTargetChange(event.target.value)}
              disabled={!targetsPayload || targetsLoading}
              className="w-full rounded-[1rem] border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="" className="bg-stone-950 text-stone-200">
                {targetsLoading
                  ? "Loading targets..."
                  : targetsPayload?.target_mode === "segment"
                    ? "Select an episode"
                    : "Select the title summary"}
              </option>
              {(targetsPayload?.targets ?? []).map((target) => (
                <option
                  key={target.id}
                  value={target.id}
                  className="bg-stone-950 text-stone-200"
                >
                  {target.label}
                </option>
              ))}
            </select>
            <p className="mt-3 min-h-10 text-sm leading-6 text-stone-400">
              {selectedTarget?.description ??
                (targetsPayload?.target_mode === "segment"
                  ? "Episode-level targets are loaded from the selected source."
                  : "This source currently supports title-level summaries only.")}
            </p>
          </div>

          <div className="space-y-3 rounded-[1.4rem] border border-white/10 bg-black/20 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-stone-400">
              Spoiler level
            </p>
            <div className="grid gap-2">
              {(["light", "standard", "full"] as SpoilerLevel[]).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => onSpoilerLevelChange(level)}
                  className={cn(
                    "rounded-[1rem] border px-4 py-3 text-left transition",
                    spoilerLevel === level
                      ? spoilerStyles[level]
                      : "border-white/10 bg-white/5 text-stone-300 hover:border-white/20 hover:bg-white/8",
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium capitalize">{level}</span>
                    <span className="text-xs uppercase tracking-[0.22em] text-stone-400">
                      {level === "light"
                        ? "Safe-ish"
                        : level === "standard"
                          ? "Balanced"
                          : "No restraint"}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={onSummarize}
            disabled={!canSummarize || summarizing}
            className="flex w-full items-center justify-center gap-2 rounded-[1.2rem] bg-gradient-to-r from-cyan-400 via-sky-500 to-blue-600 px-5 py-4 text-sm font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {summarizing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating summary
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate structured summary
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}

function Poster({
  imageUrl,
  title,
}: {
  imageUrl?: string | null;
  title: string;
}) {
  if (!imageUrl) {
    return (
      <div className="flex h-[124px] items-center justify-center rounded-[1.1rem] border border-dashed border-white/10 bg-white/5 text-center text-xs uppercase tracking-[0.22em] text-stone-500">
        No art
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[1.1rem] border border-white/10 bg-black/20">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageUrl}
        alt={title}
        className="h-[124px] w-full object-cover"
      />
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="rounded-[1.3rem] border border-dashed border-white/10 bg-white/[0.03] p-5 text-sm leading-6 text-stone-400">
      {text}
    </div>
  );
}
