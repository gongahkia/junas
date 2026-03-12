import { ArrowRight, Compass, MapPinned, Mountain } from "lucide-react";
import { Link } from "react-router-dom";
import BrandWordmark from "./BrandWordmark";
import MobilePageHeader from "./MobilePageHeader";
import LoadingSlideshow from "./LoadingSlideshow";
import { HeaderNavLink } from "@/components/HeaderNavAction";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useProviderCapabilities } from "@/hooks/useProviderCapabilities";
import { getProviderCapability } from "@/lib/provider-capabilities";
import { buildSoloResumePath, loadUserPrefs } from "@/lib/user-prefs";
import { trackProductEvent } from "@/lib/product-analytics";

export default function SoloEntryPage() {
  const prefs = loadUserPrefs();
  const { capabilities, loading } = useProviderCapabilities();
  const soloResumePath = buildSoloResumePath(prefs.soloResume);
  const kilterCapability = getProviderCapability("kilter", capabilities);
  const cruxCapability = getProviderCapability("crux", capabilities);
  const cruxAvailable =
    Boolean(cruxCapability?.solo_supported) && cruxCapability?.surface_hierarchy !== "board";

  if (loading && !kilterCapability && !cruxCapability) {
    return (
      <LoadingSlideshow
        title="Loading solo browse"
        description="Checking which solo providers are available in this browser session."
        detail="Kilter uses the local board dataset, while Crux opens a live provider-backed catalog."
      />
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-4 sm:px-6 sm:py-6">
        <MobilePageHeader title="Solo Browse" backTo="/" backLabel="Community mode" />
        <header className="hidden flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between md:flex">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Solo Browse
            </p>
            <h1 className="mt-3 leading-none">
              <Link to="/" aria-label="Back to home page" className="inline-flex">
                <BrandWordmark />
              </Link>
            </h1>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
            <HeaderNavLink to="/">Community mode</HeaderNavLink>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center gap-5 py-4 sm:gap-6 sm:py-8">
          <Card className="border-0 bg-white/90 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader className="max-w-3xl">
              <p className="text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
                Start solo mode
              </p>
              <CardTitle className="text-3xl sm:text-4xl">Choose your provider first</CardTitle>
              <CardDescription className="text-base leading-7">
                Pick Kilter when you want the built-in board dataset on this browser, or Crux
                when you want live gym and wall context from the provider catalog.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-5 lg:grid-cols-2">
              <section className="rounded-[1.75rem] border bg-[linear-gradient(180deg,_rgba(240,253,250,0.92),_rgba(255,255,255,0.98))] p-6 shadow-lg shadow-slate-900/8">
                <div className="flex items-start justify-between gap-4">
                  <div className="inline-flex rounded-full bg-teal-100 p-3 text-teal-700">
                    <Mountain className="h-5 w-5" />
                  </div>
                  <Badge variant="secondary">Local board dataset</Badge>
                </div>
                <div className="mt-6 space-y-3">
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                    Kilter
                  </p>
                  <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                    Browse Kilter boards
                  </h2>
                  <p className="text-base leading-7 text-slate-600">
                    Use saved board presets, favorites, and shortlist data from this browser, then
                    open the Kilter board view directly.
                  </p>
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                  <Badge variant="outline">{prefs.soloFavorites.length} favorites</Badge>
                  <Badge variant="outline">{prefs.soloShortlist.length} shortlisted</Badge>
                  <Badge variant="outline">{prefs.savedSoloFilters.length} saved filters</Badge>
                </div>
                <div className="mt-8 flex flex-wrap gap-3">
                  <Button asChild className="justify-between">
                    <Link
                      to="/solo/kilter"
                      onClick={() => {
                        trackProductEvent("solo.provider_selected", {
                          properties: { provider_id: "kilter" },
                        });
                      }}
                    >
                      Open Kilter
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                  {soloResumePath ? (
                    <Button asChild variant="outline" className="justify-between">
                      <Link
                        to={soloResumePath}
                        onClick={() => {
                          trackProductEvent("solo.resume_clicked", {
                            properties: { provider_id: "kilter" },
                          });
                        }}
                      >
                        Resume solo browse
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  ) : null}
                </div>
              </section>

              {cruxAvailable ? (
                <section className="rounded-[1.75rem] border bg-[linear-gradient(180deg,_rgba(248,250,252,0.96),_rgba(255,255,255,0.98))] p-6 shadow-lg shadow-slate-900/8">
                  <div className="flex items-start justify-between gap-4">
                    <div className="inline-flex rounded-full bg-sky-100 p-3 text-sky-700">
                      <Compass className="h-5 w-5" />
                    </div>
                    <Badge variant="outline">Live provider catalog</Badge>
                  </div>
                  <div className="mt-6 space-y-3">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      {cruxCapability?.label ?? "Crux"}
                    </p>
                    <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                      Browse gym-backed climbs
                    </h2>
                    <p className="text-base leading-7 text-slate-600">
                      Authenticate on demand, choose a gym and wall, then inspect the provider
                      catalog without opening a shared room first.
                    </p>
                  </div>
                  <div className="mt-6 flex flex-wrap gap-2">
                    <Badge variant="outline">
                      <MapPinned className="mr-1 h-3.5 w-3.5" />
                      Gym context
                    </Badge>
                    <Badge variant="outline">Tab-scoped auth</Badge>
                  </div>
                  <div className="mt-8">
                    <Button asChild variant="outline" className="justify-between">
                      <Link
                        to="/solo/providers/crux"
                        onClick={() => {
                          trackProductEvent("solo.provider_selected", {
                            properties: { provider_id: "crux" },
                          });
                        }}
                      >
                        Open Crux
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </section>
              ) : null}
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}
