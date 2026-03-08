import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import { loadUserPrefs, rememberDisplayName, rememberRoomVisit } from "@/lib/user-prefs";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function RoomJoinPage() {
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const [displayName, setDisplayName] = useState(
    () => loadUserPrefs().savedDisplayName
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const room = await api.joinRoom(slug, displayName);
      rememberDisplayName(displayName);
      rememberRoomVisit(room);
      navigate(`/rooms/${slug}`);
    } catch (caughtError) {
      console.error("Join room failed", caughtError);
      setError("Unable to join this room. It may be closed, expired, or require a different invite slug.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(247,254,231,0.75),_rgba(255,255,255,1))] px-6 py-10">
      <div className="mx-auto max-w-xl">
        <Button asChild variant="ghost" className="mb-6">
          <Link to="/join">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>

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

              {error ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

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
