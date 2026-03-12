import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Camera,
  Clock3,
  History,
  Link2,
  Mountain,
  Pin,
  Trophy,
  Trash2,
  Users,
} from "lucide-react";
import { api } from "@/api";
import CoachMarkOverlay, { type CoachMarkStep } from "@/components/CoachMarkOverlay";
import {
  fallbackProviderCapabilities,
  getProviderLabel,
} from "@/lib/provider-capabilities";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import {
  completeLandingGuide,
  loadUserPrefs,
  queueGuideBranch,
  type RecentRoom,
  removeRecentRoom,
  resetGuides,
  togglePinnedRecentRoom,
} from "@/lib/user-prefs";
import { getApiErrorDetails } from "@/lib/api-errors";
import { reportError } from "@/lib/observability";
import { trackProductEvent } from "@/lib/product-analytics";
import { cn } from "@/lib/utils";
import BrandWordmark from "@/components/BrandWordmark";
import { HeaderNavButton, HeaderNavLink } from "@/components/HeaderNavAction";
import { useIsMobile } from "@/hooks/use-mobile";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { ProviderId, SessionSummary } from "@/types";

const INLINE_RECENT_ROOM_LIMIT = 3;
const RECENT_ROOM_MODAL_LIMIT = 9;
const PROVIDER_CAPABILITIES = fallbackProviderCapabilities();
const LANDING_GUIDE_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="landing-brand"]',
    title: "Start here",
    description: "This home screen splits the product into hosting, joining, and solo planning.",
  },
  {
    target: '[data-guide="landing-create-room"]',
    title: "Host a session",
    description: "Create the room, connect the provider account once, then share the invite.",
  },
  {
    target: '[data-guide="landing-join-room"]',
    title: "Join from a phone",
    description: "Guests paste or scan the invite, choose a display name, then vote and queue.",
  },
  {
    target: '[data-guide="landing-solo-browse"]',
    title: "Scout first",
    description: "Solo browse is where you research climbs, shortlist them, and later spin up a room.",
    placement: "top",
  },
  {
    target: '[data-guide="landing-help"]',
    title: "Replay the guide",
    description: "Help reopens this walkthrough any time you need a quick refresher.",
    placement: "top",
  },
];

function resolveProviderLabel(providerId: ProviderId): string {
  return getProviderLabel(providerId, PROVIDER_CAPABILITIES);
}

export default function LandingPage() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [inviteCode, setInviteCode] = useState("");
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [showGuide, setShowGuide] = useState(false);
  const [isRecentRoomsDialogOpen, setIsRecentRoomsDialogOpen] = useState(false);
  const recentRooms = prefs.settings.recentRoomsEnabled
    ? prefs.recentRooms.slice(0, RECENT_ROOM_MODAL_LIMIT)
    : [];
  const previewRecentRooms = recentRooms.slice(0, INLINE_RECENT_ROOM_LIMIT);
  const hasMoreRecentRooms = recentRooms.length > INLINE_RECENT_ROOM_LIMIT;

  useEffect(() => {
    let active = true;

    const fetchRecentSessions = async () => {
      try {
        const sessions = await api.getRecentSessions(4);
        if (active) {
          setRecentSessions(sessions);
        }
      } catch (error) {
        reportError(error, {
          tags: { flow: "landing_recent_sessions" },
          extra: {
            ...getApiErrorDetails(error, "Unable to load recent sessions"),
          },
        });
        if (active) {
          setRecentSessions([]);
        }
      }
    };

    void fetchRecentSessions();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (
      isMobile &&
      prefs.settings.autoGuidesEnabled &&
      !prefs.guidedTour.landingCompleted
    ) {
      setShowGuide(true);
      trackProductEvent("onboarding.started", {
        properties: { branch: "landing" },
      });
    }
  }, [isMobile, prefs.guidedTour.landingCompleted, prefs.settings.autoGuidesEnabled]);

  const handleJoinRedirect = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const roomSlug = extractRoomSlugFromValue(inviteCode);
    if (!roomSlug) {
      return;
    }

    setPrefs(queueGuideBranch("guest"));
    trackProductEvent("landing.join_clicked", {
      properties: { branch: "guest", slug: roomSlug },
    });
    navigate(`/join/${encodeURIComponent(roomSlug)}`);
  };

  const handleTogglePinnedRoom = (slug: string) => {
    setPrefs(togglePinnedRecentRoom(slug));
  };

  const handleRemoveRecentRoom = (slug: string) => {
    setPrefs(removeRecentRoom(slug));
  };

  return (
    <div className="min-h-full overflow-x-hidden bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
      <CoachMarkOverlay
        open={showGuide}
        steps={LANDING_GUIDE_STEPS}
        onClose={() => {
          setPrefs(completeLandingGuide());
          setShowGuide(false);
          trackProductEvent("onboarding.skipped", {
            properties: { branch: "landing" },
          });
        }}
        onComplete={() => {
          setPrefs(completeLandingGuide());
          trackProductEvent("onboarding.completed", {
            properties: { branch: "landing" },
          });
        }}
      />
      <Dialog open={isRecentRoomsDialogOpen} onOpenChange={setIsRecentRoomsDialogOpen}>
        <DialogContent className="h-[min(84vh,56rem)] max-w-[min(92vw,68rem)] overflow-hidden border-0 bg-white/95 p-0 shadow-2xl">
          <DialogHeader className="border-b border-slate-200/70 px-6 py-5">
            <DialogTitle className="flex items-center gap-2 text-2xl">
              <History className="h-5 w-5" />
              Recent rooms
            </DialogTitle>
            <DialogDescription>
              Showing up to the latest 9 saved rooms from this browser.
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-y-auto px-6 pb-6 pt-4">
            <div className="grid gap-3">
              {recentRooms.map((room) => (
                <RecentRoomModalCard
                  key={room.slug}
                  room={room}
                  onTogglePinned={handleTogglePinnedRoom}
                  onRemove={handleRemoveRecentRoom}
                />
              ))}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <div className="mx-auto flex min-h-full max-w-6xl flex-col px-4 pb-24 pt-4 sm:px-6 sm:pt-6">
        <header className="flex shrink-0 flex-col gap-4 py-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0" data-guide="landing-brand">
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Collaborative Board Sessions
            </p>
            <h1 className="mt-3 leading-none">
              <BrandWordmark imageClassName="h-[38px] sm:h-[50px]" />
            </h1>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
            <HeaderNavButton
              type="button"
              data-guide="landing-help"
              className="justify-start sm:justify-center"
              onClick={() => {
                setPrefs(resetGuides());
                setShowGuide(true);
              }}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about" className="justify-start sm:justify-center">
              About
            </HeaderNavLink>
            <HeaderNavLink to="/settings" className="justify-start sm:justify-center">
              Settings
            </HeaderNavLink>
            <HeaderNavLink to="/solo" className="justify-start sm:justify-center">
              Solo browse
            </HeaderNavLink>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-4xl flex-1 items-stretch justify-start pb-6 pt-2 lg:justify-center">
          <div className="mx-auto grid w-full max-w-4xl gap-5 lg:grid-cols-2">
            <Card className="bg-card/90">
              <CardHeader>
                <CardTitle>Create a room</CardTitle>
                <CardDescription>
                  Start a new collaborative session and authenticate the host account before the room opens.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button asChild className="w-full justify-between" data-guide="landing-create-room">
                  <Link
                    to="/rooms/new"
                    onClick={() => {
                      setPrefs(queueGuideBranch("host"));
                      trackProductEvent("landing.create_clicked", {
                        properties: { branch: "host" },
                      });
                    }}
                  >
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
                  <Button
                    type="submit"
                    variant="outline"
                    className="w-full"
                    data-guide="landing-join-room"
                  >
                    Join room
                  </Button>
                  <Button asChild type="button" variant="ghost" className="w-full">
                    <Link
                      to="/join"
                      onClick={() => {
                        setPrefs(queueGuideBranch("guest"));
                        trackProductEvent("landing.join_clicked", {
                          properties: { branch: "guest" },
                        });
                      }}
                    >
                      <Camera className="mr-2 h-4 w-4" />
                      Scan or paste in full screen
                    </Link>
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="bg-card/90 lg:col-span-2">
              <CardHeader>
                <CardTitle>Plan solo, then share</CardTitle>
                <CardDescription>
                  Use solo browse to shortlist climbs, create shareable plans, and seed the next room with context already attached.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  asChild
                  variant="outline"
                  className="w-full justify-between sm:w-auto"
                  data-guide="landing-solo-browse"
                >
                  <Link
                    to="/solo"
                    onClick={() => {
                      trackProductEvent("landing.solo_clicked");
                    }}
                  >
                    Open solo browse
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>

          </div>

        </main>

        {recentRooms.length > 0 ? (
          <section className="mx-auto w-full max-w-4xl shrink-0">
            <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
              <CardHeader className="min-w-0 gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <History className="h-5 w-5" />
                    Recent rooms
                  </CardTitle>
                  <CardDescription className="max-w-full break-words">
                    {hasMoreRecentRooms
                      ? `Showing ${previewRecentRooms.length} of ${recentRooms.length} saved rooms.`
                      : "Reopen a room directly. If the room cookie expired, the app will fall back to the join flow."}
                  </CardDescription>
                </div>
                {hasMoreRecentRooms ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={() => setIsRecentRoomsDialogOpen(true)}
                  >
                    See more
                  </Button>
                ) : null}
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 lg:grid-cols-3">
                  {previewRecentRooms.map((room) => (
                    <RecentRoomPreviewCard
                      key={room.slug}
                      room={room}
                      onTogglePinned={handleTogglePinnedRoom}
                      onRemove={handleRemoveRecentRoom}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>
        ) : null}

        {recentSessions.length > 0 ? (
          <section className="mx-auto mt-5 w-full max-w-4xl shrink-0">
            <Card className="border-0 bg-slate-950 text-slate-50 shadow-xl shadow-slate-950/20">
              <CardHeader className="min-w-0 gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <CardTitle className="flex items-center gap-2 text-xl text-white">
                    <Clock3 className="h-5 w-5" />
                    Recent sessions
                  </CardTitle>
                  <CardDescription className="max-w-full break-words text-slate-300">
                    Closed sessions from the shared server. Use them as a read on what surfaces
                    and climbs people are clustering around lately.
                  </CardDescription>
                </div>
                <Button asChild variant="secondary" className="w-full sm:w-auto">
                  <Link to="/rooms/new">Start a room</Link>
                </Button>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 lg:grid-cols-2">
                  {recentSessions.map((session) => (
                    <RecentSessionCard key={`${session.room_slug}:${session.closed_at}`} session={session} />
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>
        ) : null}
      </div>
    </div>
  );
}

interface RecentRoomItemProps {
  room: RecentRoom;
  onTogglePinned: (slug: string) => void;
  onRemove: (slug: string) => void;
}

function RecentRoomPreviewCard({
  room,
  onTogglePinned,
  onRemove,
}: RecentRoomItemProps) {
  const roomLabel = room.roomName || `Room ${room.slug}`;
  const providerLabel = resolveProviderLabel(room.providerId);

  return (
    <div className="min-w-0 rounded-2xl border bg-white/75 p-4">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p
              className={cn(
                "min-w-0 truncate font-medium",
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
          <p className="mt-1 break-all text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            {providerLabel} · {room.slug}
          </p>
        </div>
        <RecentRoomActions
          room={room}
          roomLabel={roomLabel}
          onTogglePinned={onTogglePinned}
          onRemove={onRemove}
        />
      </div>
      <p className="mt-3 truncate text-sm text-muted-foreground">
        {room.surfaceName || "Surface not chosen yet"}
      </p>
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="truncate text-xs text-muted-foreground">
          Last seen {new Date(room.lastVisitedAt).toLocaleString()}
        </p>
        <Button asChild size="sm" variant="outline" className="min-w-[7rem] justify-between">
          <Link to={`/rooms/${room.slug}`} aria-label={`Open ${roomLabel}`}>
            Open room
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}

function RecentRoomModalCard({
  room,
  onTogglePinned,
  onRemove,
}: RecentRoomItemProps) {
  const roomLabel = room.roomName || `Room ${room.slug}`;
  const providerLabel = resolveProviderLabel(room.providerId);

  return (
    <div className="overflow-hidden rounded-2xl border bg-white/75 p-5 transition-colors hover:bg-white">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p
              className={cn(
                "min-w-0 text-lg font-medium",
                room.roomName ? "break-words" : "truncate"
              )}
              title={roomLabel}
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
          <p
            className="mt-1 truncate text-xs uppercase tracking-[0.2em] text-muted-foreground"
            title={`${providerLabel} · ${room.slug}`}
          >
            {providerLabel} · {room.slug}
          </p>
          <p className="mt-3 truncate text-sm text-muted-foreground" title={room.surfaceName || "Surface not chosen yet"}>
            {room.surfaceName || "Surface not chosen yet"}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Last seen {new Date(room.lastVisitedAt).toLocaleString()}
          </p>
        </div>
        <div className="flex shrink-0 items-center justify-between gap-3 lg:flex-col lg:items-end">
          <RecentRoomActions
            room={room}
            roomLabel={roomLabel}
            onTogglePinned={onTogglePinned}
            onRemove={onRemove}
          />
          <Button asChild variant="outline" className="min-w-[10rem] justify-between">
            <Link to={`/rooms/${room.slug}`} aria-label={`Open ${roomLabel}`}>
              Open room
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

interface RecentRoomActionsProps {
  room: RecentRoom;
  roomLabel: string;
  onTogglePinned: (slug: string) => void;
  onRemove: (slug: string) => void;
}

function RecentSessionCard({ session }: { session: SessionSummary }) {
  const topClimb = session.top_voted[0]?.climb;
  const topVotes = session.top_voted[0]?.vote_count ?? 0;
  const providerLabel = resolveProviderLabel(session.provider_id);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/6 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-lg font-medium text-white" title={session.room_name || session.room_slug}>
            {session.room_name || `Room ${session.room_slug}`}
          </p>
          <p className="mt-1 truncate text-[11px] uppercase tracking-[0.2em] text-slate-400">
            {providerLabel} · {session.surface_name || "surface pending"}
          </p>
        </div>
        <span className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-200">
          {session.participant_count} climber{session.participant_count === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white/6 p-3">
          <p className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-400">
            <Trophy className="h-3.5 w-3.5" />
            Top voted
          </p>
          <p className="mt-2 truncate text-sm font-medium text-white" title={topClimb?.name || "No votes recorded"}>
            {topClimb?.name || "No votes recorded"}
          </p>
          <p className="mt-1 text-xs text-slate-300">
            {topVotes > 0 ? `${topVotes} vote${topVotes === 1 ? "" : "s"}` : "No fist bumps captured"}
          </p>
        </div>

        <div className="rounded-xl bg-white/6 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Wrap-up</p>
          <p className="mt-2 text-sm text-white">
            {session.final_queue.length} queued · {session.finalists.length} finalists
          </p>
          <p className="mt-1 text-xs text-slate-300">
            Closed {new Date(session.closed_at).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

function RecentRoomActions({
  room,
  roomLabel,
  onTogglePinned,
  onRemove,
}: RecentRoomActionsProps) {
  return (
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
        onClick={() => onTogglePinned(room.slug)}
      >
        <Pin className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 rounded-full text-muted-foreground hover:text-destructive"
        aria-label={`Remove ${roomLabel} from recent rooms`}
        onClick={() => onRemove(room.slug)}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
