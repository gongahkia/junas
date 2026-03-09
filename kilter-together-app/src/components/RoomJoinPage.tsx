import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import {
  dismissOnboarding,
  loadUserPrefs,
  markGuestJoinedRoom,
  rememberDisplayName,
  rememberRoomVisit,
  resetOnboardingPrefs,
} from "@/lib/user-prefs";
import OnboardingCallout from "@/components/OnboardingCallout";
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

export default function RoomJoinPage() {
  const navigate = useNavigate();
  const { slug = "" } = useParams();
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);

    try {
      const room = await api.joinRoom(slug, displayName);
      rememberDisplayName(displayName);
      rememberRoomVisit(room);
      markGuestJoinedRoom();
      navigate(`/rooms/${slug}`);
    } catch (caughtError) {
      console.error("Join room failed", caughtError);
      showErrorToast(
        "Unable to join this room. It may be closed, expired, or require a different invite slug."
      );
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
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                resetOnboardingPrefs();
                setShowOnboarding(true);
              }}
            >
              Help
            </Button>
            <Button asChild variant="ghost">
              <Link to="/about">About</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/settings">Settings</Link>
            </Button>
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
