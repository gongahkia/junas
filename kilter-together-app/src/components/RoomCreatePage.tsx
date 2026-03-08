import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import type { ProviderId } from "@/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function RoomCreatePage() {
  const navigate = useNavigate();
  const [providerId, setProviderId] = useState<ProviderId>("kilter");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const room = await api.createRoom({
        providerId,
        displayName,
      });
      navigate(`/rooms/${room.slug}`);
    } catch (caughtError) {
      console.error("Create room failed", caughtError);
      setError("Unable to create the room. Check the host session configuration and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(240,253,250,0.95),_rgba(255,255,255,1))] px-6 py-10">
      <div className="mx-auto max-w-2xl">
        <Button asChild variant="ghost" className="mb-6">
          <Link to="/">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>

        <Card className="shadow-lg shadow-teal-950/10">
          <CardHeader>
            <CardTitle className="text-3xl">Create a collaborative room</CardTitle>
            <CardDescription className="text-base">
              The host account connects once. Guests join with a display name and collaborate from their own devices.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="display-name" className="text-sm font-medium">
                  Host display name
                </label>
                <Input
                  id="display-name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Coach, Alex, Session Host"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="provider-select" className="text-sm font-medium">
                  Provider
                </label>
                <Select
                  value={providerId}
                  onValueChange={(value) => setProviderId(value as ProviderId)}
                >
                  <SelectTrigger id="provider-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="kilter">Kilter</SelectItem>
                    <SelectItem value="crux">Crux</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="rounded-2xl border bg-muted/40 p-4 text-sm text-muted-foreground">
                {providerId === "kilter"
                  ? "After the room is created, connect one authenticated Kilter account and choose the board plus angle for the session."
                  : "After the room is created, connect a Crux API token, then pick a gym and wall for the session."}
              </div>

              {error ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Creating room..." : "Create room"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
