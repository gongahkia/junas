import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Heart, Layers3, ListChecks, Mountain, Trash2 } from "lucide-react";
import { api } from "@/api";
import AngleSelector from "./AngleSelector";
import BrandWordmark from "./BrandWordmark";
import CoachMarkOverlay, { type CoachMarkStep } from "./CoachMarkOverlay";
import LoadingSlideshow from "./LoadingSlideshow";
import type { Board, SoloFilterPreset, SoloSavedClimb } from "../types";
import { DEFAULT_ANGLE } from "@/lib/climbs";
import { useProviderCapabilities } from "@/hooks/useProviderCapabilities";
import {
  buildSoloFilterPresetPath,
  buildSoloResumePath,
  buildSoloSavedClimbPath,
  completeGuideBranch,
  loadUserPrefs,
  removeSoloFilterPreset,
  removeSoloFavorite,
  removeSoloShortlist,
  rememberLastKilterSurface,
  soloSavedClimbKey,
} from "@/lib/user-prefs";
import { trackProductEvent } from "@/lib/product-analytics";
import { HeaderNavButton, HeaderNavLink } from "@/components/HeaderNavAction";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface BoardSelectorProps {
  boards: Board[];
  loading: boolean;
  boardPathPrefix?: string;
}

const SOLO_GUIDE_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="solo-angle"]',
    title: "Pick the default angle",
    description: "This becomes the starting view whenever you open a board from here.",
  },
  {
    target: '[data-guide="solo-collections"]',
    title: "Saved solo state",
    description: "Favorites, shortlist, and filter presets stay local to this browser.",
  },
  {
    target: '[data-guide="solo-providers"]',
    title: "Provider solo browse",
    description: "Use provider-backed solo pages when you want live gym context instead of the local Kilter dataset.",
    placement: "top",
  },
];

export default function BoardSelector({
  boards,
  loading,
  boardPathPrefix = "/boards",
}: BoardSelectorProps) {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const { capabilities } = useProviderCapabilities();
  const [showGuide, setShowGuide] = useState(false);
  const [angle, setAngle] = useState(() => prefs.lastKilter.angle || DEFAULT_ANGLE);
  const soloResumePath = buildSoloResumePath(prefs.soloResume);
  const alternateSoloProviders = capabilities.filter(
    (capability) => capability.solo_supported && capability.id !== "kilter"
  );

  if (loading) {
    return (
      <LoadingSlideshow
        title="Loading solo browse"
        description="Fetching the available Kilter boards for this local session."
        detail="This page stays read-only and uses the same local catalog as the collaborative rooms."
      />
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
      <CoachMarkOverlay
        open={showGuide}
        steps={SOLO_GUIDE_STEPS}
        onClose={() => setShowGuide(false)}
        onComplete={() => {
          setPrefs(completeGuideBranch("solo"));
          trackProductEvent("onboarding.completed", {
            properties: { branch: "solo" },
          });
        }}
      />

      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="flex items-center justify-between py-4">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Solo Kilter Browse
            </p>
            <h1 className="mt-3 leading-none">
              <Link to="/" aria-label="Back to home page" className="inline-flex">
                <BrandWordmark />
              </Link>
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <HeaderNavButton
              type="button"
              onClick={() => {
                setShowGuide(true);
              }}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
            <HeaderNavLink to="/">Community mode</HeaderNavLink>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center gap-6 py-8">
          <div className="mx-auto grid w-full max-w-5xl gap-6">
            <div className="grid gap-6 md:grid-cols-4">
              <Card
                className={soloResumePath ? "bg-card/90 md:col-span-3" : "bg-card/90 md:col-span-4"}
                data-guide="solo-angle"
              >
                <CardHeader>
                  <CardTitle>Choose the default angle</CardTitle>
                  <CardDescription>
                    This angle becomes the starting view whenever you open a board from this page.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <AngleSelector angle={angle} onAngleChange={setAngle} />
                  <p className="text-sm text-muted-foreground">
                    The browser remembers your last solo angle locally for the next visit.
                  </p>
                </CardContent>
              </Card>

              {soloResumePath ? (
                <Card className="bg-card/90 md:col-span-1">
                  <CardHeader>
                    <CardTitle>Resume solo browse</CardTitle>
                    <CardDescription>
                      Jump back into your last Kilter board filters on this browser.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex h-full items-end">
                    <Button asChild variant="outline" className="w-full justify-between">
                      <Link to={soloResumePath}>
                        Resume solo browse
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  </CardContent>
                </Card>
              ) : null}
            </div>

            {prefs.savedSoloFilters.length > 0 ||
            prefs.soloFavorites.length > 0 ||
            prefs.soloShortlist.length > 0 ? (
              <div className="grid gap-6 md:grid-cols-2" data-guide="solo-collections">
                {prefs.savedSoloFilters.length > 0 ? (
                  <SavedSoloFilterCard
                    presets={prefs.savedSoloFilters}
                    onRemove={(presetID) => setPrefs(removeSoloFilterPreset(presetID))}
                  />
                ) : null}
                {prefs.soloFavorites.length > 0 ? (
                  <SavedSoloCollectionCard
                    icon={<Heart className="h-5 w-5" />}
                    title="Favorites"
                    description="Pinned climbs you want to come back to from this browser."
                    climbs={prefs.soloFavorites}
                    onRemove={(climbKey) => setPrefs(removeSoloFavorite(climbKey))}
                  />
                ) : null}
                {prefs.soloShortlist.length > 0 ? (
                  <SavedSoloCollectionCard
                    icon={<ListChecks className="h-5 w-5" />}
                    title="Shortlist"
                    description="Candidate climbs worth turning into a room queue later."
                    climbs={prefs.soloShortlist}
                    onRemove={(climbKey) => setPrefs(removeSoloShortlist(climbKey))}
                  />
                ) : null}
              </div>
            ) : null}

            {alternateSoloProviders.length > 0 ? (
              <Card
                className="border-0 bg-white/88 shadow-xl shadow-slate-900/10 backdrop-blur"
                data-guide="solo-providers"
              >
                <CardHeader>
                  <CardTitle className="text-2xl">Other solo providers</CardTitle>
                  <CardDescription>
                    Use provider-specific solo browse when you want gym-backed catalog context
                    instead of the local Kilter dataset.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  {alternateSoloProviders.map((capability) => (
                    <div
                      key={capability.id}
                      className="rounded-2xl border bg-white/70 p-5 shadow-sm"
                    >
                      <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                        Provider solo browse
                      </p>
                      <h2 className="mt-3 text-xl font-medium">{capability.label}</h2>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Authenticate on demand, pick a gym context, then inspect climbs without
                        opening a collaborative room first.
                      </p>
                      <Button asChild variant="outline" className="mt-4 justify-between">
                        <Link to={`/solo/providers/${encodeURIComponent(capability.id)}`}>
                          Open {capability.label}
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="text-2xl">Choose a board</CardTitle>
                <CardDescription>
                  Open a board to browse climbs at {angle}° by default.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {boards.length === 0 ? (
                  <div className="rounded-2xl border border-dashed bg-muted/20 p-8 text-center text-muted-foreground">
                    No Kilter boards were returned by the API.
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    {boards.map((board) => (
                      <button
                        key={board.id}
                        type="button"
                        className="rounded-2xl border bg-white/75 p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:bg-white hover:shadow-lg"
                        onClick={() => {
                          rememberLastKilterSurface(String(board.id), angle);
                          navigate(
                            `${boardPathPrefix}/${board.id}?angle=${angle}&sort=${prefs.settings.soloDefaultSort}`
                          );
                        }}
                      >
                        <div className="rounded-[1.25rem] border border-slate-200/80 bg-[linear-gradient(180deg,_rgba(240,253,250,0.9),_rgba(255,255,255,0.96))] p-3 shadow-inner shadow-slate-900/5">
                          <div className="flex aspect-[16/9] items-center justify-center overflow-hidden rounded-[1rem] bg-[radial-gradient(circle_at_top,_rgba(20,184,166,0.16),_transparent_45%),linear-gradient(180deg,_rgba(248,250,252,0.98),_rgba(226,232,240,0.72))]">
                            {board.preview_image_filename ? (
                              <img
                                src={api.getImageUrl(board.preview_image_filename)}
                                alt={`${board.kilter_name} ${board.name} board preview`}
                                className="h-full w-full object-contain"
                                loading="lazy"
                              />
                            ) : (
                              <Mountain className="h-12 w-12 text-slate-300" />
                            )}
                          </div>
                        </div>
                        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                          Board {board.id}
                        </p>
                        <h2 className="mt-3 text-xl font-medium">{board.kilter_name}</h2>
                        <p className="mt-2 text-sm text-muted-foreground">{board.name}</p>
                        <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                          <span className="rounded-full bg-slate-100 px-3 py-1">
                            Size {board.name}
                          </span>
                          <span className="rounded-full bg-teal-50 px-3 py-1 text-teal-700">
                            {(board.climb_count ?? 0).toLocaleString()} climbs
                          </span>
                        </div>
                        <p className="mt-4 text-sm font-medium text-teal-700">
                          Open at {angle}°
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

        </main>
      </div>
    </div>
  );
}

function SavedSoloFilterCard({
  onRemove,
  presets,
}: {
  onRemove: (presetID: string) => void;
  presets: SoloFilterPreset[];
}) {
  return (
    <Card className="border-0 bg-white/88 shadow-xl shadow-teal-950/10 backdrop-blur">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-2xl">
          <Layers3 className="h-5 w-5" />
          Saved filters
        </CardTitle>
        <CardDescription>
          Reopen the board and filter combinations you keep using in solo browse.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {presets.slice(0, 4).map((preset) => (
          <div
            key={preset.id}
            className="flex items-start justify-between gap-3 rounded-2xl border bg-white/70 px-4 py-4"
          >
            <div className="min-w-0">
              <Link
                to={buildSoloFilterPresetPath(preset)}
                className="line-clamp-1 text-sm font-medium text-foreground hover:text-teal-700"
              >
                {preset.label}
              </Link>
              <p className="mt-2 text-sm text-muted-foreground">
                Sort: {preset.sort}
                {preset.q ? ` · Query: ${preset.q}` : ""}
                {preset.setter ? ` · Setter: ${preset.setter}` : ""}
                {preset.grade ? ` · Grade: ${preset.grade}` : ""}
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0"
              onClick={() => onRemove(preset.id)}
              aria-label={`Remove ${preset.label}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SavedSoloCollectionCard({
  climbs,
  description,
  icon,
  onRemove,
  title,
}: {
  climbs: SoloSavedClimb[];
  description: string;
  icon: ReactNode;
  onRemove: (climbKey: string) => void;
  title: string;
}) {
  return (
    <Card className="border-0 bg-white/88 shadow-xl shadow-teal-950/10 backdrop-blur">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-2xl">
          {icon}
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {climbs.slice(0, 4).map((climb) => {
          const climbKey = soloSavedClimbKey(climb);
          return (
            <div
              key={climbKey}
              className="flex items-start justify-between gap-3 rounded-2xl border bg-white/70 px-4 py-4"
            >
              <div className="min-w-0">
                <Link
                  to={buildSoloSavedClimbPath(climb)}
                  className="line-clamp-1 text-sm font-medium text-foreground hover:text-teal-700"
                >
                  {climb.climb_name}
                </Link>
                <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                  {climb.board_name} · {climb.angle}\u00b0
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {climb.grade || "Grade unavailable"} · {climb.setter_name}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="shrink-0"
                onClick={() => onRemove(climbKey)}
                aria-label={`Remove ${climb.climb_name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
