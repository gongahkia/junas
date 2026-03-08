import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Camera, History, Link2, Mountain, Users } from "lucide-react";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import { buildSoloResumePath, loadUserPrefs } from "@/lib/user-prefs";
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
  const prefs = useMemo(() => loadUserPrefs(), []);
  const soloResumePath = buildSoloResumePath(prefs.soloResume);

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
          <Button asChild variant="ghost">
            <Link to="/solo">Solo browse</Link>
          </Button>
        </header>

        <main className="grid flex-1 gap-6 py-8 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-3xl">One host. Shared decisions.</CardTitle>
              <CardDescription className="max-w-2xl text-base leading-7">
                Create a room, connect one Kilter or Crux account on the server,
                and let everyone join from their phones to vote and queue climbs.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <FeatureCard
                icon={<Users className="h-5 w-5" />}
                title="Invite friends"
                description="Share a room URL or QR code. Guests do not need board credentials."
              />
              <FeatureCard
                icon={<Mountain className="h-5 w-5" />}
                title="Choose climbs together"
                description="Vote on climbs, build a queue, and let the host control the running order."
              />
              <FeatureCard
                icon={<Link2 className="h-5 w-5" />}
                title="Support multiple providers"
                description="Start with Kilter and Crux now, while keeping the provider model extensible."
              />
            </CardContent>
          </Card>

          <div className="grid gap-6">
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
              <Card className="bg-card/90">
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
        </main>

        {prefs.recentRooms.length > 0 ? (
          <section className="pb-8">
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

interface FeatureCardProps {
  icon: ReactNode;
  title: string;
  description: string;
}

function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <div className="rounded-2xl border bg-white/75 p-5 shadow-sm">
      <div className="mb-4 inline-flex rounded-full bg-teal-100 p-2 text-teal-700">
        {icon}
      </div>
      <h2 className="text-lg font-medium">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}
