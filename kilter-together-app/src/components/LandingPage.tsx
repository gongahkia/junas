import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Camera,
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
  type RecentRoom,
  removeRecentRoom,
  resetOnboardingPrefs,
  togglePinnedRecentRoom,
} from "@/lib/user-prefs";
import { cn } from "@/lib/utils";
import IntroDialog from "@/components/IntroDialog";
import OnboardingCallout from "@/components/OnboardingCallout";
import BrandWordmark from "@/components/BrandWordmark";
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

const INLINE_RECENT_ROOM_LIMIT = 3;
const RECENT_ROOM_MODAL_LIMIT = 9;

export default function LandingPage() {
  const navigate = useNavigate();
  const [inviteCode, setInviteCode] = useState("");
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const [showOnboarding, setShowOnboarding] = useState(
    () => prefs.settings.autoGuidesEnabled && !prefs.onboarding.dismissed
  );
  const [showIntro, setShowIntro] = useState(
    () =>
      prefs.settings.autoGuidesEnabled &&
      prefs.onboarding.dismissed &&
      !prefs.intro.landingDismissed
  );
  const [isRecentRoomsDialogOpen, setIsRecentRoomsDialogOpen] = useState(false);
  const recentRooms = prefs.settings.recentRoomsEnabled
    ? prefs.recentRooms.slice(0, RECENT_ROOM_MODAL_LIMIT)
    : [];
  const previewRecentRooms = recentRooms.slice(0, INLINE_RECENT_ROOM_LIMIT);
  const hasMoreRecentRooms = recentRooms.length > INLINE_RECENT_ROOM_LIMIT;

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
    <div className="min-h-full overflow-x-hidden bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
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
        onDismiss={() => {
          setPrefs(dismissLandingIntro());
          setShowIntro(false);
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
          <div className="min-w-0">
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Collaborative Board Sessions
            </p>
            <h1 className="mt-3 leading-none">
              <BrandWordmark imageClassName="h-[38px] sm:h-[50px]" />
            </h1>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
            <Button
              type="button"
              variant="ghost"
              className="justify-start sm:justify-center"
              onClick={() => {
                setPrefs(resetOnboardingPrefs());
                setShowIntro(false);
                setShowOnboarding(true);
              }}
            >
              Help
            </Button>
            <Button asChild variant="ghost" className="justify-start sm:justify-center">
              <Link to="/about">About</Link>
            </Button>
            <Button asChild variant="ghost" className="justify-start sm:justify-center">
              <Link to="/settings">Settings</Link>
            </Button>
            <Button asChild variant="ghost" className="justify-start sm:justify-center">
              <Link to="/solo">Solo browse</Link>
            </Button>
          </div>
        </header>

        {showOnboarding ? (
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
            onDismiss={() => {
              const nextPrefs = dismissOnboarding();
              setPrefs(nextPrefs);
              setShowOnboarding(false);
              if (nextPrefs.settings.autoGuidesEnabled && !nextPrefs.intro.landingDismissed) {
                setShowIntro(true);
              }
            }}
          />
        ) : null}

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
            {room.providerId} · {room.slug}
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
            title={`${room.providerId} · ${room.slug}`}
          >
            {room.providerId} · {room.slug}
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
