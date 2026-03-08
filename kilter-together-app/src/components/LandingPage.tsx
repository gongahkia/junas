import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Camera,
  CircleHelp,
  History,
  Link2,
  Mountain,
  Pin,
  Trash2,
  Users,
} from "lucide-react";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import {
  dismissLandingIntro,
  dismissOnboarding,
  loadUserPrefs,
  removeRecentRoom,
  resetOnboardingPrefs,
  togglePinnedRecentRoom,
} from "@/lib/user-prefs";
import { cn } from "@/lib/utils";
import IntroDialog from "@/components/IntroDialog";
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

export default function LandingPage() {
  const navigate = useNavigate();
  const [inviteCode, setInviteCode] = useState("");
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const showOnboarding = !prefs.onboarding.dismissed;
  const showIntro = !showOnboarding && !prefs.intro.landingDismissed;

  const handleJoinRedirect = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const roomSlug = extractRoomSlugFromValue(inviteCode);
    if (!roomSlug) {
      return;
    }

    navigate(`/join/${encodeURIComponent(roomSlug)}`);
  };

  const handleTogglePinnedRoom = (slug: string) => {
    setPrefs(togglePinnedRecentRoom(slug));
  };

  const handleRemoveRecentRoom = (slug: string) => {
    setPrefs(removeRecentRoom(slug));
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
      <IntroDialog
        open={showIntro}
        title="One host. Shared decisions."
        description="Create a room, connect one Kilter or Crux account on the server, and let everyone join from their phones to vote and queue climbs."
        features={[
          {
            icon: <Users className="h-6 w-6" />,
            title: "Invite friends",
            description: "Share a room URL or QR code. Guests do not need board credentials.",
          },
          {
            icon: <Mountain className="h-6 w-6" />,
            title: "Choose climbs together",
            description: "Vote on climbs, build a queue, and let the host control the running order.",
          },
          {
            icon: <Link2 className="h-6 w-6" />,
            title: "Support multiple providers",
            description: "Start with Kilter and Crux now, while keeping the provider model extensible.",
          },
        ]}
        dismissLabel="Start exploring"
        onDismiss={() => setPrefs(dismissLandingIntro())}
      />

      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="flex items-center justify-between py-4">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Collaborative Board Sessions
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-6xl">
              kilter-together
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setPrefs(resetOnboardingPrefs())}
            >
              <CircleHelp className="mr-2 h-4 w-4" />
              Help
            </Button>
            <Button asChild variant="ghost">
              <Link to="/solo">Solo browse</Link>
            </Button>
          </div>
        </header>

        {showOnboarding ? (
          <div className="pb-4">
            <OnboardingCallout
              title="Start in whichever role you have right now"
              description="Hosts create the room and connect one provider account. Guests scan or paste the invite, join with a display name, then vote or add climbs to the queue."
              steps={[
                "Create a room if you are hosting. Pick Kilter or Crux, then connect the account inside the room.",
                "Join a room if someone else is hosting. Scanning the QR code is the fastest path on a phone.",
                "Use solo browse when you just want to inspect Kilter climbs without the shared room layer.",
              ]}
              actionLabel="Create room"
              onAction={() => navigate("/rooms/new")}
              onDismiss={() => setPrefs(dismissOnboarding())}
            />
          </div>
        ) : null}

        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center gap-6 py-8">
          <div
            className="mx-auto grid w-full max-w-5xl gap-6 md:grid-cols-2"
          >
            <Card className="bg-card/90">
              <CardHeader>
                <CardTitle>Create a room</CardTitle>
                <CardDescription>
                  Start a new collaborative session and authenticate the host account before the room opens.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button asChild className="w-full justify-between">
                  <Link to="/rooms/new">
                    Create room
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <p className="text-sm text-muted-foreground">
                  Supported providers today: Kilter and Crux.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card/90">
              <CardHeader>
                <CardTitle>Join a room</CardTitle>
                <CardDescription>
                  Paste a room slug from an invite link to join from this device.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-3" onSubmit={handleJoinRedirect}>
                  <Input
                    value={inviteCode}
                    onChange={(event) => setInviteCode(event.target.value)}
                    placeholder="Room slug or invite URL"
                  />
                  <Button type="submit" variant="outline" className="w-full">
                    Join room
                  </Button>
                  <Button asChild type="button" variant="ghost" className="w-full">
                    <Link to="/join">
                      <Camera className="mr-2 h-4 w-4" />
                      Scan or paste in full screen
                    </Link>
                  </Button>
                </form>
              </CardContent>
            </Card>

          </div>

        </main>

        {prefs.recentRooms.length > 0 ? (
          <section className="mx-auto w-full max-w-5xl pb-8">
            <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
              <CardHeader className="min-w-0">
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <History className="h-5 w-5" />
                  Recent rooms
                </CardTitle>
                <CardDescription className="max-w-full break-words">
                  Reopen a room directly. If the room cookie expired, the app will fall back to the join flow.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {prefs.recentRooms.map((room) => {
                  const roomLabel = room.roomName || `Room ${room.slug}`;

                  return (
                    <div
                      key={room.slug}
                      className="min-w-0 overflow-hidden rounded-2xl border bg-white/75 p-4 transition-colors hover:bg-white"
                    >
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <p
                              className={cn(
                                "min-w-0 font-medium",
                                room.roomName ? "break-words" : "break-all"
                              )}
                            >
                              {roomLabel}
                            </p>
                            {room.pinned ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-teal-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-teal-700">
                                <Pin className="h-3 w-3" />
                                Pinned
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1 break-all text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            {room.providerId} · {room.slug}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className={cn(
                              "h-8 w-8 rounded-full text-muted-foreground",
                              room.pinned ? "bg-teal-50 text-teal-700 hover:bg-teal-100 hover:text-teal-800" : null
                            )}
                            aria-label={`${room.pinned ? "Unpin" : "Pin"} ${roomLabel}`}
                            onClick={() => handleTogglePinnedRoom(room.slug)}
                          >
                            <Pin className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 rounded-full text-muted-foreground hover:text-destructive"
                            aria-label={`Remove ${roomLabel} from recent rooms`}
                            onClick={() => handleRemoveRecentRoom(room.slug)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <p className="mt-3 break-words text-sm text-muted-foreground">
                        {room.surfaceName || "Surface not chosen yet"}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        Last seen {new Date(room.lastVisitedAt).toLocaleString()}
                      </p>
                      <Button asChild variant="outline" className="mt-4 w-full justify-between">
                        <Link
                          to={`/rooms/${room.slug}`}
                          aria-label={`Open ${roomLabel}`}
                        >
                          Open room
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </section>
        ) : null}
      </div>
    </div>
  );
}
