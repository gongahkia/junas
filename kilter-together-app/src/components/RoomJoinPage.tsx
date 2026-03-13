import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import CoachMarkOverlay, { type CoachMarkStep } from "@/components/CoachMarkOverlay";
import DeploymentStorageBanner from "@/components/DeploymentStorageBanner";
import FeedbackPrompt from "@/components/FeedbackPrompt";
import MobilePageHeader from "@/components/MobilePageHeader";
import { getApiErrorDetails } from "@/lib/api-errors";
import {
  loadUserPrefs,
  markFeedbackPromptSeen,
  rememberDisplayName,
  rememberRoomVisit,
  shouldShowFeedbackPrompt,
} from "@/lib/user-prefs";
import { HeaderNavButton, HeaderNavLink } from "@/components/HeaderNavAction";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useErrorToast } from "@/hooks/use-toast";
import { reportError, reportEvent } from "@/lib/observability";
import { useIsMobile } from "@/hooks/use-mobile";
import { useRuntimeStatus } from "@/hooks/useRuntimeStatus";

const GUEST_JOIN_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="guest-display-name"]',
    title: "Pick the name the room sees",
    description: "This display name is how the host and the other guests will recognize you in the session.",
  },
  {
    target: '[data-guide="guest-join-submit"]',
    title: "Join this device into the room",
    description: "After this step, your phone becomes a live participant in the room state.",
  },
];

export default function RoomJoinPage() {
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const isMobile = useIsMobile();
  const [searchParams] = useSearchParams();
  const showErrorToast = useErrorToast();
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const { status: runtimeStatus } = useRuntimeStatus();
  const [showGuide, setShowGuide] = useState(false);
  const [showFailureFeedback, setShowFailureFeedback] = useState(false);
  const [displayName, setDisplayName] = useState(
    () => loadUserPrefs().savedDisplayName
  );
  const [submitting, setSubmitting] = useState(false);
  const [inlineError, setInlineError] = useState("");
  const joinReason = searchParams.get("reason") ?? "";
  const joinReasonMessage =
    joinReason === "session_expired"
      ? "Your last room session on this browser expired. Rejoin the room to continue."
      : joinReason === "session_invalid"
        ? "This browser does not have a valid session for the room. Join again to continue."
        : joinReason === "session_required"
          ? "Join the room on this browser before opening the invite."
          : "";

  useEffect(() => {
    if (
      isMobile &&
      prefs.settings.autoGuidesEnabled &&
      prefs.guidedTour.activeBranch === "guest" &&
      !prefs.guidedTour.guestCompleted
    ) {
      setShowGuide(true);
    }
  }, [isMobile, prefs.guidedTour.activeBranch, prefs.guidedTour.guestCompleted, prefs.settings.autoGuidesEnabled]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setInlineError("");
    reportEvent("room.join", "guest join submitted", { slug });

    try {
      const room = await api.joinRoom(slug, displayName);
      rememberDisplayName(displayName);
      rememberRoomVisit(room);
      reportEvent("room.join", "guest join succeeded", {
        providerId: room.provider_id,
        slug: room.slug,
      });
      navigate(`/rooms/${slug}`);
    } catch (caughtError) {
      console.error("Join room failed", caughtError);
      const details = getApiErrorDetails(
        caughtError,
        "Unable to join this room. It may be closed, expired, or require a different invite slug."
      );
      if (details.code === "display_name_taken") {
        setInlineError("That display name is already in use in this room. Try a different one.");
      } else {
        setInlineError(details.message);
      }
      reportError(caughtError, {
        extra: { slug },
        tags: {
          code: typeof details.code === "string" ? details.code : "unknown",
          flow: "room_join",
        },
      });
      if (shouldShowFeedbackPrompt("room-join-failure")) {
        setShowFailureFeedback(true);
      }
      showErrorToast(details.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(247,254,231,0.75),_rgba(255,255,255,1))] px-4 py-4 sm:px-6 sm:py-8">
      <CoachMarkOverlay open={showGuide} steps={GUEST_JOIN_STEPS} onClose={() => setShowGuide(false)} />
      <FeedbackPrompt
        open={showFailureFeedback}
        title="Was the join failure message useful?"
        description="A quick signal helps tighten invite validation and rename prompts."
        onClose={() => {
          setPrefs(markFeedbackPromptSeen("room-join-failure"));
          setShowFailureFeedback(false);
        }}
        onSubmit={async ({ sentiment, message }) => {
          await api.submitFeedback({
            roomSlug: slug,
            promptFamily: "room-join-failure",
            sentiment,
            message,
          });
          setPrefs(markFeedbackPromptSeen("room-join-failure"));
          setShowFailureFeedback(false);
        }}
      />
      <div className="mx-auto max-w-xl">
        <MobilePageHeader
          title="Join room"
          backTo="/join"
          backLabel="Back to invite"
          onHelp={() => setShowGuide(true)}
        />
        <div className="mb-6 hidden flex-wrap items-center justify-between gap-2 md:flex">
          <Button asChild variant="ghost">
            <Link to="/join">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div className="flex items-center gap-2">
            <HeaderNavButton
              type="button"
              onClick={() => setShowGuide(true)}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
          </div>
        </div>

        <Card className="shadow-lg shadow-lime-950/10">
          <CardHeader>
            <CardTitle className="text-2xl sm:text-3xl">Join room</CardTitle>
            <CardDescription className="text-base">
              Enter a display name for this device. You will join room{" "}
              <span className="font-medium text-foreground">{slug}</span>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DeploymentStorageBanner status={runtimeStatus} />
            {runtimeStatus &&
            (runtimeStatus.storage.severity === "warning" ||
              runtimeStatus.storage.severity === "critical") ? (
              <div className="h-5" />
            ) : null}
            <form onSubmit={handleSubmit} className="space-y-5">
              {joinReasonMessage ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {joinReasonMessage}
                </div>
              ) : null}
              {inlineError ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
                  {inlineError}
                </div>
              ) : null}
              <div className="space-y-2">
                <label
                  htmlFor="join-display-name"
                  className="text-sm font-medium"
                  data-guide="guest-display-name"
                >
                  Display name
                </label>
                <Input
                  id="join-display-name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Kai, Mei, Spotter"
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={submitting}
                data-guide="guest-join-submit"
              >
                {submitting ? "Joining room..." : "Join room"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
