import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import { getApiErrorDetails } from "@/lib/api-errors";
import {
  dismissOnboarding,
  loadUserPrefs,
  markGuestJoinedRoom,
  rememberDisplayName,
  rememberRoomVisit,
  resetOnboardingPrefs,
} from "@/lib/user-prefs";
import OnboardingCallout from "@/components/OnboardingCallout";
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

export default function RoomJoinPage() {
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const [searchParams] = useSearchParams();
  const showErrorToast = useErrorToast();
  const [showOnboarding, setShowOnboarding] = useState(
    () => {
      const prefs = loadUserPrefs();
      return prefs.settings.autoGuidesEnabled && !prefs.onboarding.dismissed;
    }
  );
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setInlineError("");
    reportEvent("room.join", "guest join submitted", { slug });

    try {
      const room = await api.joinRoom(slug, displayName);
      rememberDisplayName(displayName);
      rememberRoomVisit(room);
      markGuestJoinedRoom();
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
      showErrorToast(details.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(247,254,231,0.75),_rgba(255,255,255,1))] px-6 py-10">
      <div className="mx-auto max-w-xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
          <Button asChild variant="ghost">
            <Link to="/join">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div className="flex items-center gap-2">
            <HeaderNavButton
              type="button"
              onClick={() => {
                resetOnboardingPrefs();
                setShowOnboarding(true);
              }}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
          </div>
        </div>

        {showOnboarding ? (
          <OnboardingCallout
            title="Guest flow: join fast, then vote"
            description="Guests do not need provider credentials. Once you join the room, your vote and queue actions update the shared session immediately."
            steps={[
              "Keep the host-provided slug or invite URL open on this device.",
              "Enter the display name everyone in the room should see.",
              "After joining, vote for climbs you want to do or add a climb to the queue.",
            ]}
            onDismiss={() => {
              dismissOnboarding();
              setShowOnboarding(false);
            }}
          />
        ) : null}

        <Card className="shadow-lg shadow-lime-950/10">
          <CardHeader>
            <CardTitle className="text-3xl">Join room</CardTitle>
            <CardDescription className="text-base">
              Enter a display name for this device. You will join room{" "}
              <span className="font-medium text-foreground">{slug}</span>.
            </CardDescription>
          </CardHeader>
          <CardContent>
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
                <label htmlFor="join-display-name" className="text-sm font-medium">
                  Display name
                </label>
                <Input
                  id="join-display-name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Kai, Mei, Spotter"
                />
              </div>

              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Joining room..." : "Join room"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
