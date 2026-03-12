import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Share2 } from "lucide-react";
import { api } from "@/api";
import BrandWordmark from "@/components/BrandWordmark";
import FeedbackPrompt from "@/components/FeedbackPrompt";
import LoadingSlideshow from "@/components/LoadingSlideshow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useErrorToast } from "@/hooks/use-toast";
import { copyTextToClipboard, isShareAbortError } from "@/lib/clipboard";
import { trackProductEvent } from "@/lib/product-analytics";
import {
  beginRoomSeed,
  markFeedbackPromptSeen,
  shouldShowFeedbackPrompt,
} from "@/lib/user-prefs";
import type { RoomRecap } from "@/types";

export default function RoomRecapPage() {
  const { shareId = "" } = useParams();
  const navigate = useNavigate();
  const showErrorToast = useErrorToast();
  const [recap, setRecap] = useState<RoomRecap | null>(null);
  const [loading, setLoading] = useState(true);
  const [slideIndex, setSlideIndex] = useState(0);
  const [showFeedback, setShowFeedback] = useState(false);

  useEffect(() => {
    let active = true;
    trackProductEvent("recap.view", {
      properties: { share_id: shareId },
    });

    void (async () => {
      try {
        const nextRecap = await api.getRoomRecap(shareId);
        if (active) {
          setRecap(nextRecap);
        }
      } catch (error) {
        if (active) {
          showErrorToast("Unable to load that session recap right now.");
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

  useEffect(() => {
    if (!recap) {
      return;
    }
    const lastSlideIndex = recap.slides.length - 1;
    if (slideIndex === lastSlideIndex && shouldShowFeedbackPrompt("recap_final_slide")) {
      setShowFeedback(true);
    }
  }, [recap, slideIndex]);

  if (loading) {
    return (
      <LoadingSlideshow
        title="Loading session recap"
        description="Pulling the immutable session deck from the server snapshot."
        detail="This recap is rendered from stored session data, not live provider calls."
      />
    );
  }

  if (!recap) {
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
              <CardTitle>Recap unavailable</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                The recap link may be invalid or the server no longer has this snapshot.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const currentSlide = recap.slides[slideIndex];
  const isLastSlide = slideIndex === recap.slides.length - 1;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))] px-4 py-6 sm:px-6">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-5">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link to="/" aria-label="Back to home page" className="inline-flex">
            <BrandWordmark />
          </Link>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                trackProductEvent("recap.share", {
                  properties: { share_id: recap.share_id },
                });
                const url = typeof window !== "undefined" ? window.location.href : "";
                try {
                  if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
                    await navigator.share({
                      title: recap.room_name || `Room ${recap.room_slug}`,
                      url,
                    });
                    return;
                  }
                  await copyTextToClipboard(url);
                } catch (caughtError) {
                  if (isShareAbortError(caughtError)) {
                    return;
                  }
                  showErrorToast("Unable to share or copy this recap link.");
                }
              }}
            >
              <Share2 className="mr-2 h-4 w-4" />
              Share
            </Button>
          </div>
        </header>

        <Card className="flex-1 border-0 bg-white/90 shadow-2xl shadow-teal-950/10 backdrop-blur">
          <CardHeader className="space-y-3">
            <p className="text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
              {currentSlide.eyebrow}
            </p>
            <div className="space-y-2">
              <CardTitle className="text-3xl sm:text-4xl">{currentSlide.title}</CardTitle>
              <p className="max-w-3xl text-base leading-7 text-muted-foreground">
                {currentSlide.description}
              </p>
            </div>
          </CardHeader>
          <CardContent className="grid gap-6">
            {currentSlide.featured_climb ? (
              <div className="rounded-3xl border bg-teal-50/70 p-5">
                <p className="text-xs uppercase tracking-[0.2em] text-teal-700">
                  Featured climb
                </p>
                <h2 className="mt-2 text-2xl font-semibold">
                  {currentSlide.featured_climb.name}
                </h2>
                <p className="mt-2 text-sm text-teal-900/80">
                  {currentSlide.featured_climb.setter_name || "Unknown setter"}
                </p>
              </div>
            ) : null}

            {currentSlide.stats?.length ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {currentSlide.stats.map((stat) => (
                  <div key={`${currentSlide.id}:${stat.label}`} className="rounded-2xl border bg-white/70 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                      {stat.label}
                    </p>
                    <p className="mt-2 text-xl font-semibold">{stat.value}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {currentSlide.climbs?.length ? (
              <div className="grid gap-3">
                {currentSlide.climbs.map((item) => (
                  <div key={`${currentSlide.id}:${item.climb.id}`} className="rounded-2xl border bg-white/70 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{item.climb.name}</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {item.climb.setter_name || "Unknown setter"}
                        </p>
                      </div>
                      {item.vote_count ? (
                        <span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-medium text-teal-800">
                          {item.vote_count} votes
                        </span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            {currentSlide.participants?.length ? (
              <div className="flex flex-wrap gap-2">
                {currentSlide.participants.map((participant) => (
                  <span
                    key={`${currentSlide.id}:${participant}`}
                    className="rounded-full border bg-white/70 px-3 py-1 text-sm"
                  >
                    {participant}
                  </span>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={slideIndex === 0}
            onClick={() => setSlideIndex((current) => Math.max(0, current - 1))}
          >
            Back
          </Button>
          <div className="text-sm text-muted-foreground">
            Slide {slideIndex + 1} of {recap.slides.length}
          </div>
          <div className="flex items-center gap-2">
            {recap.rematch_seed ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  beginRoomSeed({
                    providerId: recap.rematch_seed!.provider_id,
                    title: recap.room_name,
                    surface: recap.rematch_seed!.surface,
                    climbs: recap.rematch_seed!.climbs,
                  });
                  trackProductEvent("recap.rematch", {
                    properties: { share_id: recap.share_id },
                  });
                  navigate("/rooms/new");
                }}
              >
                Start rematch
              </Button>
            ) : null}
            <Button
              type="button"
              onClick={() =>
                setSlideIndex((current) =>
                  Math.min(recap.slides.length - 1, current + 1)
                )
              }
            >
              {isLastSlide ? "Stay here" : "Next"}
              {!isLastSlide ? <ArrowRight className="ml-2 h-4 w-4" /> : null}
            </Button>
          </div>
        </div>
      </div>

      <FeedbackPrompt
        open={showFeedback}
        title="How did this recap feel?"
        description="A quick signal helps tune the next recap deck."
        onClose={() => {
          markFeedbackPromptSeen("recap_final_slide");
          setShowFeedback(false);
        }}
        onSubmit={async ({ sentiment, message }) => {
          await api.submitFeedback({
            shareId: recap.share_id,
            promptFamily: "recap_final_slide",
            sentiment,
            message,
            route: `/recaps/${recap.share_id}`,
          });
          markFeedbackPromptSeen("recap_final_slide");
        }}
      />
    </div>
  );
}
