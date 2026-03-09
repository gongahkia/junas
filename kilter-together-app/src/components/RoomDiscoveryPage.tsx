import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Camera, CircleHelp, ScanSearch } from "lucide-react";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import { dismissOnboarding, loadUserPrefs, resetOnboardingPrefs } from "@/lib/user-prefs";
import OnboardingCallout from "@/components/OnboardingCallout";
import RoomScanner from "@/components/RoomScanner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function RoomDiscoveryPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [showOnboarding, setShowOnboarding] = useState(
    () => !loadUserPrefs().onboarding.dismissed
  );
  const [joinValue, setJoinValue] = useState("");
  const [error, setError] = useState("");
  const scannerMode = searchParams.get("mode") === "scan";

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const roomSlug = extractRoomSlugFromValue(joinValue);
    if (!roomSlug) {
      setError("Paste a room slug or invite URL to continue.");
      return;
    }

    setError("");
    navigate(`/join/${encodeURIComponent(roomSlug)}`);
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(239,246,255,0.92),_rgba(255,255,255,1))] px-6 py-10">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
          <Button asChild variant="ghost">
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              resetOnboardingPrefs();
              setShowOnboarding(true);
            }}
          >
            <CircleHelp className="mr-2 h-4 w-4" />
            Replay onboarding
          </Button>
        </div>

        {showOnboarding ? (
          <OnboardingCallout
            title="Phone-first join works best from this page"
            description="Use the camera when the host is showing a QR code. If you already have the link, paste it here and continue into the join form."
            steps={[
              "Scan the host QR code if you are standing near the wall.",
              "If scanning is not convenient, paste the invite URL or just the room slug.",
              "You will still pick a display name on the next screen before joining the room.",
            ]}
            onDismiss={() => {
              dismissOnboarding();
              setShowOnboarding(false);
            }}
          />
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="shadow-lg shadow-sky-950/10">
            <CardHeader>
              <CardTitle className="text-3xl">Join a room</CardTitle>
              <CardDescription className="text-base">
                Paste an invite link or room slug, or use the camera-first workflow to scan the host QR code.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <Input
                  value={joinValue}
                  onChange={(event) => setJoinValue(event.target.value)}
                  placeholder="https://.../join/room-slug or room-slug"
                />
                {error ? (
                  <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                    {error}
                  </div>
                ) : null}
                <Button type="submit" className="w-full">
                  Continue to join
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="border-dashed bg-card/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Camera className="h-4 w-4" />
                Camera workflow
              </CardTitle>
              <CardDescription>
                Open the scanner to point your phone at the host QR code.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!scannerMode ? (
                <>
                  <div className="rounded-2xl border bg-muted/30 p-4 text-sm text-muted-foreground">
                    The scanner opens your rear camera, reads a room invite QR code, and takes you directly into the join flow.
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => setSearchParams({ mode: "scan" })}
                  >
                    <ScanSearch className="mr-2 h-4 w-4" />
                    Open scanner
                  </Button>
                </>
              ) : (
                <>
                  <RoomScanner
                    autoStart={true}
                    onDetected={(roomSlug) =>
                      navigate(`/join/${encodeURIComponent(roomSlug)}`)
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    className="w-full"
                    onClick={() => setSearchParams({})}
                  >
                    Hide scanner
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
