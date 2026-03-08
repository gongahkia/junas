import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Camera, CircleHelp, History, Link2, Mountain, Users } from "lucide-react";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import {
  buildSoloResumePath,
  dismissLandingIntro,
  dismissOnboarding,
  loadUserPrefs,
  resetOnboardingPrefs,
} from "@/lib/user-prefs";
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
  const soloResumePath = buildSoloResumePath(prefs.soloResume);
  const showIntro = !prefs.intro.landingDismissed;
  const showOnboarding = !showIntro && !prefs.onboarding.dismissed;

  const handleJoinRedirect = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const roomSlug = extractRoomSlugFromValue(inviteCode);
    if (!roomSlug) {
      return;
    }

    navigate(`/join/${encodeURIComponent(roomSlug)}`);
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
          <div className="mx-auto grid w-full max-w-4xl gap-6 md:grid-cols-2 xl:grid-cols-3">
            <Card className="bg-card/90">
              <CardHeader>
                <CardTitle>Create a room</CardTitle>
                <CardDescription>
                  Start a new collaborative session and connect the host account inside the room.
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

            {soloResumePath ? (
              <Card className="bg-card/90 md:col-span-2 xl:col-span-1">
                <CardHeader>
                  <CardTitle>Resume solo browse</CardTitle>
                  <CardDescription>
                    Jump back into your last Kilter board filters on this browser.
                  </CardDescription>
                </CardHeader>
                <CardContent>
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

          <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-center text-3xl sm:text-4xl">
                One host. Shared decisions.
              </CardTitle>
              <CardDescription className="mx-auto max-w-3xl text-center text-base leading-7">
                Create a room, connect one Kilter or Crux account on the server,
                and let everyone join from their phones to vote and queue climbs.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border bg-white/70 p-5 text-center text-sm leading-7 text-muted-foreground">
                Hosts connect the provider once, guests join from their own devices, and the room stays focused on live votes, queueing, and quick consensus at the wall.
              </div>
              <div className="flex flex-wrap justify-center gap-2 text-sm text-muted-foreground">
                <span className="rounded-full bg-teal-100 px-3 py-1 font-medium text-teal-800">
                  Host-linked auth
                </span>
                <span className="rounded-full bg-teal-100 px-3 py-1 font-medium text-teal-800">
                  Invite URL + QR
                </span>
                <span className="rounded-full bg-teal-100 px-3 py-1 font-medium text-teal-800">
                  Live voting + queue
                </span>
              </div>
            </CardContent>
          </Card>
        </main>

        {prefs.recentRooms.length > 0 ? (
          <section className="mx-auto w-full max-w-5xl pb-8">
            <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <History className="h-5 w-5" />
                  Recent rooms
                </CardTitle>
                <CardDescription>
                  Reopen a room directly. If the room cookie expired, the app will fall back to the join flow.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {prefs.recentRooms.map((room) => (
                  <Link
                    key={room.slug}
                    to={`/rooms/${room.slug}`}
                    className="rounded-2xl border bg-white/75 p-4 transition-colors hover:bg-white"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">Room {room.slug}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                          {room.providerId}
                        </p>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">
                      {room.surfaceName || "Surface not chosen yet"}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Last seen {new Date(room.lastVisitedAt).toLocaleString()}
                    </p>
                  </Link>
                ))}
              </CardContent>
            </Card>
          </section>
        ) : null}
      </div>
    </div>
  );
}
