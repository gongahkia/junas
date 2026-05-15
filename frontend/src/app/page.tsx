"use client";

import type { ReactNode } from "react";
import { useDeferredValue, useEffect, useState, startTransition } from "react";
import RecentSummaries from "@/components/RecentSummaries";
import SummaryDisplay from "@/components/SummaryDisplay";
import SummaryForm from "@/components/SummaryForm";
import {
  createSummary,
  fetchTargets,
  getApiErrorMessage,
  searchTitles,
} from "@/lib/api";
import {
  SOURCE_OPTIONS,
  type RecentSummary,
  type SearchResult,
  type SourceId,
  type SpoilerLevel,
  type SummaryPayload,
  type TargetsPayload,
} from "@/lib/contracts";
import { ArrowRight, Radar, ShieldCheck, Telescope } from "lucide-react";

const RECENTS_STORAGE_KEY = "sayless.recent-summaries";

export default function HomePage() {
  const [source, setSource] = useState<SourceId>("myanimelistanime");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState<SearchResult | null>(null);
  const [targetsPayload, setTargetsPayload] = useState<TargetsPayload | null>(
    null,
  );
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [selectedTargetId, setSelectedTargetId] = useState("");
  const [spoilerLevel, setSpoilerLevel] = useState<SpoilerLevel>("standard");
  const [result, setResult] = useState<SummaryPayload | null>(null);
  const [recents, setRecents] = useState<RecentSummary[]>([]);
  const [summarizing, setSummarizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query.trim());

  useEffect(() => {
    try {
      const storedValue = window.localStorage.getItem(RECENTS_STORAGE_KEY);

      if (!storedValue) {
        return;
      }

      const parsedValue = JSON.parse(storedValue) as RecentSummary[];
      setRecents(parsedValue);
    } catch {
      window.localStorage.removeItem(RECENTS_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (deferredQuery.length < 2) {
      startTransition(() => setSearchResults([]));
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);

    const timeoutId = window.setTimeout(async () => {
      try {
        const results = await searchTitles(source, deferredQuery);

        if (cancelled) {
          return;
        }

        setError(null);
        startTransition(() => setSearchResults(results));
      } catch (searchError) {
        if (cancelled) {
          return;
        }

        startTransition(() => setSearchResults([]));
        setError(getApiErrorMessage(searchError));
      } finally {
        if (!cancelled) {
          setSearchLoading(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [deferredQuery, source]);

  async function handleSelectMedia(media: SearchResult) {
    setSelectedMedia(media);
    setTargetsPayload(null);
    setSelectedTargetId("");
    setResult(null);
    setError(null);
    setTargetsLoading(true);

    try {
      const payload = await fetchTargets(media.source, media.id);
      const defaultTargetId = payload.targets[0]?.id ?? "";

      startTransition(() => {
        setTargetsPayload(payload);
        setSelectedTargetId(defaultTargetId);
      });
    } catch (targetsError) {
      setError(getApiErrorMessage(targetsError));
    } finally {
      setTargetsLoading(false);
    }
  }

  async function handleSummarize() {
    if (!selectedMedia || !targetsPayload || !selectedTargetId) {
      return;
    }

    const selectedTarget = targetsPayload.targets.find(
      (target) => target.id === selectedTargetId,
    );

    if (!selectedTarget) {
      return;
    }

    setSummarizing(true);
    setError(null);

    try {
      const payload = await createSummary({
        source: selectedMedia.source,
        mediaId: selectedMedia.id,
        targetType: selectedTarget.type,
        targetId: selectedTarget.id,
        spoilerLevel,
      });

      startTransition(() => setResult(payload));
      saveRecent(payload);
    } catch (summaryError) {
      setError(getApiErrorMessage(summaryError));
    } finally {
      setSummarizing(false);
    }
  }

  function handleSourceChange(nextSource: SourceId) {
    setSource(nextSource);
    setQuery("");
    setError(null);
    setSelectedMedia(null);
    setTargetsPayload(null);
    setSelectedTargetId("");
    setResult(null);
    startTransition(() => setSearchResults([]));
  }

  function handleQueryChange(nextQuery: string) {
    setQuery(nextQuery);
    setError(null);
    setSelectedMedia(null);
    setTargetsPayload(null);
    setSelectedTargetId("");
    setResult(null);
  }

  function handleRecentSelect(item: RecentSummary) {
    const reopenedResult = item.payload;

    setSource(reopenedResult.media.source);
    setQuery(reopenedResult.media.title);
    setError(null);
    setSpoilerLevel(reopenedResult.meta.spoiler_level);
    setSelectedMedia({
      ...reopenedResult.media,
      supports_segments: reopenedResult.target.type !== "title",
    });
    setTargetsPayload({
      media: reopenedResult.media,
      target_mode: reopenedResult.target.type === "episode" ? "segment" : "title",
      targets: [reopenedResult.target],
    });
    setSelectedTargetId(reopenedResult.target.id);
    startTransition(() => setResult(reopenedResult));
  }

  function saveRecent(payload: SummaryPayload) {
    const nextEntry: RecentSummary = {
      stored_at: new Date().toISOString(),
      payload,
    };

    setRecents((current) => {
      const deduped = current.filter(
        (item) =>
          !(
            item.payload.media.source === payload.media.source &&
            item.payload.media.id === payload.media.id &&
            item.payload.target.id === payload.target.id
          ),
      );

      const nextValue = [nextEntry, ...deduped].slice(0, 6);
      window.localStorage.setItem(RECENTS_STORAGE_KEY, JSON.stringify(nextValue));
      return nextValue;
    });
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.15),_transparent_30%),radial-gradient(circle_at_right,_rgba(249,115,22,0.16),_transparent_28%),linear-gradient(180deg,#0a0b10_0%,#10131a_48%,#0b0c11_100%)] text-white">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:72px_72px] opacity-[0.08]" />

      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
        <header className="grid gap-6 rounded-[2rem] border border-white/10 bg-black/25 p-6 backdrop-blur lg:grid-cols-[1.12fr_0.88fr] lg:p-8">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.32em] text-cyan-100">
              <Telescope className="h-3.5 w-3.5" />
              Consumer demo build
            </div>
            <div className="space-y-4">
              <h1 className="max-w-4xl text-4xl font-semibold leading-tight text-white sm:text-5xl lg:text-6xl">
                Skip smarter, not blindly.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-stone-300 lg:text-lg">
                SayLess turns public media metadata into spoiler-controlled
                summaries. Search a title, pick a target, choose your spoiler
                tolerance, and carry the important context forward.
              </p>
            </div>
            <div className="inline-flex items-center gap-2 text-sm text-stone-300">
              Search
              <ArrowRight className="h-4 w-4 text-cyan-300" />
              Choose target
              <ArrowRight className="h-4 w-4 text-cyan-300" />
              Generate recap
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <FeatureCard
              icon={<Radar className="h-4 w-4" />}
              title="Depth where it matters"
              body="Anime and TV are episode-aware, while books, movies, and manga stay honest about title-level scope."
            />
            <FeatureCard
              icon={<ShieldCheck className="h-4 w-4" />}
              title="Spoiler control"
              body="Choose light, standard, or full spoilers before you ask the model to summarize."
            />
            <FeatureCard
              icon={<Telescope className="h-4 w-4" />}
              title="Portfolio-grade contract"
              body="Search, target discovery, and summarization all run through the same typed backend workflow."
            />
          </div>
        </header>

        {error ? (
          <div className="rounded-[1.4rem] border border-rose-400/25 bg-rose-400/10 px-5 py-4 text-sm leading-6 text-rose-100">
            {error}
          </div>
        ) : null}

        <div className="grid gap-8 xl:grid-cols-[1.18fr_0.82fr]">
          <div className="space-y-8">
            <SummaryForm
              sourceOptions={SOURCE_OPTIONS}
              source={source}
              query={query}
              selectedMedia={selectedMedia}
              targetsPayload={targetsPayload}
              selectedTargetId={selectedTargetId}
              spoilerLevel={spoilerLevel}
              searchResults={searchResults}
              searchLoading={searchLoading}
              targetsLoading={targetsLoading}
              summarizing={summarizing}
              onSourceChange={handleSourceChange}
              onQueryChange={handleQueryChange}
              onSelectMedia={handleSelectMedia}
              onTargetChange={setSelectedTargetId}
              onSpoilerLevelChange={setSpoilerLevel}
              onSummarize={handleSummarize}
            />

            {result ? (
              <SummaryDisplay result={result} />
            ) : (
              <EmptyResultState />
            )}
          </div>

          <div className="space-y-6">
            <RecentSummaries items={recents} onSelect={handleRecentSelect} />
            <aside className="rounded-[1.8rem] border border-white/10 bg-black/25 p-5 backdrop-blur">
              <div className="space-y-3">
                <p className="text-xs uppercase tracking-[0.28em] text-stone-400">
                  Product notes
                </p>
                <h2 className="text-2xl font-semibold text-white">
                  What this build is optimized for
                </h2>
                <div className="grid gap-3 text-sm leading-6 text-stone-300">
                  <p>
                    Search replaces raw ID entry, so the demo behaves like a
                    product instead of an internal API tester.
                  </p>
                  <p>
                    The backend stays honest about source depth. If the upstream
                    service only supports title-level context, the interface says so.
                  </p>
                  <p>
                    Recent summaries are local-only by design, which keeps the repo
                    lightweight while still making repeated demos smoother.
                  </p>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  body,
}: {
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.04] p-4">
      <div className="mb-3 inline-flex rounded-full border border-white/10 bg-black/20 p-2 text-cyan-100">
        {icon}
      </div>
      <h2 className="text-base font-semibold text-white">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-stone-300">{body}</p>
    </div>
  );
}

function EmptyResultState() {
  return (
    <section className="rounded-[2rem] border border-dashed border-white/10 bg-black/20 p-8 backdrop-blur">
      <div className="max-w-2xl space-y-4">
        <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
          Waiting on a summary
        </p>
        <h2 className="text-3xl font-semibold text-white">
          Structured recaps land here once you run the flow.
        </h2>
        <p className="text-base leading-7 text-stone-300">
          The result view includes title metadata, target details, key events,
          plot points, and the carry-forward context users need after skipping.
        </p>
      </div>
    </section>
  );
}
