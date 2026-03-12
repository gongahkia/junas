import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Camera, ScanSearch } from "lucide-react";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import CoachMarkOverlay, { type CoachMarkStep } from "@/components/CoachMarkOverlay";
import { loadUserPrefs, resetGuides } from "@/lib/user-prefs";
import { HeaderNavButton, HeaderNavLink } from "@/components/HeaderNavAction";
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
import { useErrorToast } from "@/hooks/use-toast";
import { useIsMobile } from "@/hooks/use-mobile";

const GUEST_DISCOVERY_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="guest-paste"]',
    title: "Paste the invite or slug",
    description: "If the host sent you a link, this is the quickest way into the room.",
  },
  {
    target: '[data-guide="guest-scan"]',
    title: "Scan from the wall",
    description: "If you are already standing near the board, the QR scanner is the fastest phone-first join path.",
  },
];

export default function RoomDiscoveryPage() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const showErrorToast = useErrorToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [prefs] = useState(() => loadUserPrefs());
  const [showGuide, setShowGuide] = useState(false);
  const [joinValue, setJoinValue] = useState("");
  const scannerMode = searchParams.get("mode") === "scan";

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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const roomSlug = extractRoomSlugFromValue(joinValue);
    if (!roomSlug) {
      showErrorToast("Paste a room slug or invite URL to continue.");
      return;
    }

    navigate(`/join/${encodeURIComponent(roomSlug)}`);
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(239,246,255,0.92),_rgba(255,255,255,1))] px-6 py-10">
      <CoachMarkOverlay
        open={showGuide}
        steps={GUEST_DISCOVERY_STEPS}
        onClose={() => setShowGuide(false)}
      />
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
          <Button asChild variant="ghost">
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div className="flex items-center gap-2">
            <HeaderNavButton
              type="button"
              onClick={() => {
                resetGuides();
                setShowGuide(true);
              }}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="shadow-lg shadow-sky-950/10" data-guide="guest-paste">
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
                <Button type="submit" className="w-full">
                  Continue to join
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="border-dashed bg-card/80" data-guide="guest-scan">
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
