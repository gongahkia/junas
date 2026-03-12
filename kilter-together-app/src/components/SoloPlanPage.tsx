import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Share2 } from "lucide-react";
import { api } from "@/api";
import BrandWordmark from "@/components/BrandWordmark";
import LoadingSlideshow from "@/components/LoadingSlideshow";
import MobilePageHeader from "@/components/MobilePageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useErrorToast } from "@/hooks/use-toast";
import { copyTextToClipboard, isShareAbortError } from "@/lib/clipboard";
import { trackProductEvent } from "@/lib/product-analytics";
import { beginRoomSeed } from "@/lib/user-prefs";
import type { SoloPlanSnapshot } from "@/types";

export default function SoloPlanPage() {
  const { shareId = "" } = useParams();
  const navigate = useNavigate();
  const showErrorToast = useErrorToast();
  const [plan, setPlan] = useState<SoloPlanSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    trackProductEvent("solo_plan.view", {
      properties: { share_id: shareId },
    });

    void (async () => {
      try {
        const nextPlan = await api.getSoloPlan(shareId);
        if (active) {
          setPlan(nextPlan);
        }
      } catch {
        if (active) {
          showErrorToast("Unable to load that shared solo plan.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [shareId, showErrorToast]);

  if (loading) {
    return (
      <LoadingSlideshow
        title="Loading shared plan"
        description="Pulling the immutable solo planning snapshot from the server."
        detail="This page stays read-only so the shared plan does not drift after it is created."
      />
    );
  }

  if (!plan) {
    return (
      <div className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-xl">
          <Button asChild variant="ghost" className="mb-6">
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <Card>
            <CardHeader>
              <CardTitle>Plan unavailable</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                The shared plan link may be invalid or the snapshot is no longer available.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const sharePlan = async () => {
    trackProductEvent("solo_plan.share", {
      properties: { share_id: plan.share_id },
    });
    const url = typeof window !== "undefined" ? window.location.href : "";
    try {
      if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
        try {
          await navigator.share({
            title: plan.title,
            url,
          });
          return;
        } catch (caughtError) {
          if (isShareAbortError(caughtError)) {
            return;
          }
        }
      }
      await copyTextToClipboard(url);
    } catch {
      showErrorToast("Unable to share or copy this solo plan link.");
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.16),_transparent_34%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))] px-4 py-6 sm:px-6">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-5">
        <MobilePageHeader
          title={plan.title}
          backTo="/"
          backLabel="Community mode"
          primaryAction={{
            label: "Share",
            icon: <Share2 className="h-4 w-4" />,
            onSelect: () => {
              void sharePlan();
            },
          }}
        />
        <header className="hidden flex-wrap items-center justify-between gap-3 md:flex">
          <Link to="/" aria-label="Back to home page" className="inline-flex">
            <BrandWordmark />
          </Link>
          <Button
            type="button"
            variant="outline"
            onClick={() => void sharePlan()}
          >
            <Share2 className="mr-2 h-4 w-4" />
            Share
          </Button>
        </header>

        <Card className="border-0 bg-white/90 shadow-2xl shadow-teal-950/10 backdrop-blur">
          <CardHeader className="space-y-3">
            <p className="text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
              Shared solo plan
            </p>
            <CardTitle className="text-3xl sm:text-4xl">{plan.title}</CardTitle>
            <CardDescription className="max-w-3xl text-base leading-7">
              {plan.notes || "No planning note was added to this snapshot."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-2xl border bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Provider
                </p>
                <p className="mt-2 text-lg font-semibold">{plan.provider_id}</p>
              </div>
              <div className="rounded-2xl border bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Surface
                </p>
                <p className="mt-2 text-lg font-semibold">{plan.surface.name}</p>
              </div>
              <div className="rounded-2xl border bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Climbs
                </p>
                <p className="mt-2 text-lg font-semibold">{plan.climbs.length}</p>
              </div>
              <div className="rounded-2xl border bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Created
                </p>
                <p className="mt-2 text-lg font-semibold">
                  {new Date(plan.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            {Object.keys(plan.filters ?? {}).length > 0 ? (
              <div className="rounded-2xl border bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Filters
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(plan.filters ?? {}).map(([key, value]) => (
                    <span
                      key={`${key}:${value}`}
                      className="rounded-full border bg-white px-3 py-1 text-sm"
                    >
                      {key}: {value}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="grid gap-3">
              {plan.climbs.map((climb) => (
                <div key={climb.id} className="rounded-2xl border bg-white/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{climb.name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {climb.setter_name || "Unknown setter"}
                      </p>
                    </div>
                    {climb.primary_grade ? (
                      <span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-medium text-teal-800">
                        {climb.primary_grade}
                      </span>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button asChild variant="ghost">
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back home
            </Link>
          </Button>
          <div className="flex items-center gap-2">
            {plan.open_path ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  trackProductEvent("solo_plan.open_in_solo", {
                    properties: { share_id: plan.share_id },
                  });
                  navigate(plan.open_path!);
                }}
              >
                Open in solo
              </Button>
            ) : null}
            <Button
              type="button"
              onClick={() => {
                beginRoomSeed({
                  providerId: plan.provider_id,
                  title: plan.title,
                  surface: plan.surface,
                  climbs: plan.climbs,
                  openPath: plan.open_path,
                });
                trackProductEvent("solo_plan.room_start", {
                  properties: { share_id: plan.share_id },
                });
                navigate("/rooms/new");
              }}
            >
              Start room from plan
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
