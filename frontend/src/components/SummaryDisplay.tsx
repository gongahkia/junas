import type { ReactNode } from "react";
import type { SummaryPayload } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { ArrowUpRight, Clock3, Layers3, Sparkles, UsersRound } from "lucide-react";

interface SummaryDisplayProps {
  result: SummaryPayload;
}

export default function SummaryDisplay({ result }: SummaryDisplayProps) {
  return (
    <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-black/35 shadow-[0_40px_120px_-40px_rgba(0,0,0,0.8)] backdrop-blur">
      <div className="grid gap-8 p-6 lg:grid-cols-[0.92fr_1.08fr] lg:p-8">
        <div className="space-y-6">
          <div className="overflow-hidden rounded-[1.7rem] border border-white/10 bg-white/[0.04]">
            {result.media.image_url ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={result.media.image_url}
                  alt={result.media.title}
                  className="h-[280px] w-full object-cover"
                />
              </>
            ) : (
              <div className="flex h-[280px] items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.18),_transparent_50%),linear-gradient(180deg,rgba(17,24,39,0.96),rgba(10,10,10,0.98))]">
                <p className="text-sm uppercase tracking-[0.32em] text-stone-400">
                  No artwork available
                </p>
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{result.media.source_label}</Badge>
              <Badge tone="cyan">{result.target.type}</Badge>
              <Badge tone="orange">{result.meta.spoiler_level} spoilers</Badge>
            </div>

            <div className="space-y-2">
              <h2 className="text-3xl font-semibold text-white lg:text-4xl">
                {result.media.title}
              </h2>
              {result.media.subtitle ? (
                <p className="text-sm text-stone-300 lg:text-base">
                  {result.media.subtitle}
                </p>
              ) : null}
            </div>

            <div className="grid gap-3 rounded-[1.4rem] border border-white/10 bg-white/[0.04] p-4">
              <InfoRow icon={<Layers3 className="h-4 w-4" />} label="Target">
                {result.target.label}
              </InfoRow>
              <InfoRow icon={<Clock3 className="h-4 w-4" />} label="Generated">
                {new Date(result.meta.generated_at).toLocaleString()}
              </InfoRow>
              <InfoRow icon={<Sparkles className="h-4 w-4" />} label="Carry forward">
                {result.summary.skip_context}
              </InfoRow>
            </div>

            {result.meta.attribution.url ? (
              <a
                href={result.meta.attribution.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 text-sm text-cyan-300 transition hover:text-cyan-200"
              >
                View source reference
                <ArrowUpRight className="h-4 w-4" />
              </a>
            ) : null}
          </div>
        </div>

        <div className="grid gap-5">
          <Panel
            icon={<UsersRound className="h-4 w-4" />}
            title="Characters"
            description="The names and groups that matter most for what you skipped."
          >
            <ul className="grid gap-2">
              {result.summary.characters.map((character) => (
                <li
                  key={character}
                  className="rounded-[1rem] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-stone-200"
                >
                  {character}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel
            icon={<Sparkles className="h-4 w-4" />}
            title="Key Events"
            description="High-signal beats in the order they matter."
          >
            <ol className="grid gap-3">
              {result.summary.key_events.map((event, index) => (
                <li
                  key={`${index}-${event}`}
                  className="grid grid-cols-[2.2rem_1fr] gap-3 rounded-[1rem] border border-cyan-400/15 bg-cyan-400/5 px-4 py-3 text-sm leading-6 text-stone-100"
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/10 text-xs font-semibold text-cyan-100">
                    {index + 1}
                  </span>
                  <span>{event}</span>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel
            icon={<Layers3 className="h-4 w-4" />}
            title="Plot Points"
            description="A more detailed rundown of what the skip changes downstream."
          >
            <div className="grid gap-3">
              {result.summary.plot_points.map((point, index) => (
                <div
                  key={`${index}-${point}`}
                  className="rounded-[1rem] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-6 text-stone-200"
                >
                  {point}
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </section>
  );
}

function Panel({
  icon,
  title,
  description,
  children,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[1.6rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="rounded-full border border-white/10 bg-white/5 p-2 text-cyan-100">
          {icon}
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-stone-400">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "cyan" | "orange";
}) {
  return (
    <span
      className={cn(
        "rounded-full border px-3 py-1 text-[0.68rem] uppercase tracking-[0.24em]",
        tone === "neutral" && "border-white/10 bg-white/[0.04] text-stone-300",
        tone === "cyan" && "border-cyan-300/20 bg-cyan-300/10 text-cyan-100",
        tone === "orange" &&
          "border-orange-300/20 bg-orange-300/10 text-orange-100",
      )}
    >
      {children}
    </span>
  );
}

function InfoRow({
  icon,
  label,
  children,
}: {
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-2 border-b border-white/8 pb-3 last:border-b-0 last:pb-0">
      <div className="flex items-center gap-2 text-[0.68rem] uppercase tracking-[0.24em] text-stone-400">
        {icon}
        {label}
      </div>
      <div className="text-sm leading-6 text-stone-200">{children}</div>
    </div>
  );
}
