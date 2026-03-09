import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import type { ProviderId } from "@/types";
import { getApiErrorMessage } from "@/lib/api-errors";
import {
  dismissOnboarding,
  loadUserPrefs,
  rememberCruxToken,
  rememberDisplayName,
  rememberKilterCredentials,
  rememberLastProvider,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function RoomCreatePage() {
  const navigate = useNavigate();
  const savedPrefsRef = useRef(loadUserPrefs());
  const showErrorToast = useErrorToast();
  const [showOnboarding, setShowOnboarding] = useState(
    () =>
      savedPrefsRef.current.settings.autoGuidesEnabled &&
      !savedPrefsRef.current.onboarding.dismissed
  );
  const [providerId, setProviderId] = useState<ProviderId>(
    () => savedPrefsRef.current.lastProviderId || "kilter"
  );
  const [roomName, setRoomName] = useState("");
  const [displayName, setDisplayName] = useState(
    () => savedPrefsRef.current.savedDisplayName
  );
  const [connectionFields, setConnectionFields] = useState(() => ({
    username: savedPrefsRef.current.savedCredentials.kilter.remember
      ? savedPrefsRef.current.savedCredentials.kilter.username
      : "",
    password: "",
    token: "",
  }));
  const [rememberCredentials, setRememberCredentials] = useState(() => ({
    kilter: savedPrefsRef.current.savedCredentials.kilter.remember,
    crux: savedPrefsRef.current.savedCredentials.crux.remember,
  }));
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);

    try {
      const secret: Record<string, string> = {};
      if (providerId === "kilter") {
        secret.username = connectionFields.username;
        secret.password = connectionFields.password;
      } else {
        secret.token = connectionFields.token;
      }

      const room = await api.createRoom({
        providerId,
        roomName,
        displayName,
        secret,
      });
      rememberDisplayName(displayName);
      rememberLastProvider(providerId);
      if (providerId === "kilter") {
        rememberKilterCredentials(
          connectionFields.username,
          connectionFields.password,
          rememberCredentials.kilter
        );
      } else {
        rememberCruxToken(connectionFields.token, rememberCredentials.crux);
      }
      rememberRoomVisit(room);
      navigate(`/rooms/${room.slug}`);
    } catch (caughtError) {
      console.error("Create room failed", caughtError);
      showErrorToast(
        getApiErrorMessage(
          caughtError,
          "Unable to create the room. Make sure the API server is running and check the backend logs."
        )
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(240,253,250,0.95),_rgba(255,255,255,1))] px-6 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
          <Button asChild variant="ghost">
            <Link to="/">
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
            title="Host flow: sign in first, then share"
            description="Authenticate the host account here before the room exists. Once the room opens, you only need to choose the shared board or wall before inviting everyone else."
            steps={[
              "Give the room a name so guests can recognize the session when they join.",
              "Enter the host display name you want guests to see on this device.",
              "Pick the provider for this room, then enter valid host credentials. Kilter uses username/password, while Crux uses an API token.",
              "After the room is created, choose the surface, then share the invite link or QR code.",
            ]}
            onDismiss={() => {
              dismissOnboarding();
              setShowOnboarding(false);
            }}
          />
        ) : null}

        <Card className="shadow-lg shadow-teal-950/10">
          <CardHeader>
            <CardTitle className="text-3xl">Create a collaborative room</CardTitle>
            <CardDescription className="text-base">
              Authenticate the host account once before the room opens. Guests join later with a display name and collaborate from their own devices.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="room-name" className="text-sm font-medium">
                  Room name
                </label>
                <Input
                  id="room-name"
                  value={roomName}
                  onChange={(event) => setRoomName(event.target.value)}
                  placeholder="Monday Session, Kilter Crew, Warmup Circuit"
                />
              </div>

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

              {providerId === "kilter" ? (
                <div className="grid gap-5 md:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="kilter-username" className="text-sm font-medium">
                      Kilter username
                    </label>
                    <Input
                      id="kilter-username"
                      value={connectionFields.username}
                      onChange={(event) =>
                        setConnectionFields((previousState) => ({
                          ...previousState,
                          username: event.target.value,
                        }))
                      }
                      autoComplete="username"
                      placeholder="Kilter username"
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="kilter-password" className="text-sm font-medium">
                      Kilter password
                    </label>
                    <Input
                      id="kilter-password"
                      type="password"
                      value={connectionFields.password}
                      onChange={(event) =>
                        setConnectionFields((previousState) => ({
                          ...previousState,
                          password: event.target.value,
                        }))
                      }
                      autoComplete="current-password"
                      placeholder="Kilter password"
                    />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <label className="flex items-center gap-3 text-sm font-medium">
                      <input
                        type="checkbox"
                        checked={rememberCredentials.kilter}
                        onChange={(event) =>
                          setRememberCredentials((previousState) => ({
                            ...previousState,
                            kilter: event.target.checked,
                          }))
                        }
                        className="h-4 w-4 rounded border-slate-300"
                      />
                      Remember Kilter username on this browser
                    </label>
                    <p className="text-xs text-muted-foreground">
                      Stores the username and this preference locally. You still enter the password each time.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <label htmlFor="crux-token" className="text-sm font-medium">
                    Crux API token
                  </label>
                  <Input
                    id="crux-token"
                    value={connectionFields.token}
                    onChange={(event) =>
                      setConnectionFields((previousState) => ({
                        ...previousState,
                        token: event.target.value,
                      }))
                    }
                    autoComplete="off"
                    placeholder="Crux API token"
                  />
                  <p className="text-sm text-muted-foreground">
                    Paste either the raw Crux token or the full <code>Bearer ...</code> value.
                  </p>
                  <label className="flex items-center gap-3 pt-1 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={rememberCredentials.crux}
                      onChange={(event) =>
                        setRememberCredentials((previousState) => ({
                          ...previousState,
                          crux: event.target.checked,
                        }))
                      }
                      className="h-4 w-4 rounded border-slate-300"
                    />
                    Remember this Crux auth preference on this browser
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Stores this preference locally. You still enter the Crux token each time.
                  </p>
                </div>
              )}

              <div className="rounded-2xl border bg-muted/40 p-4 text-sm text-muted-foreground">
                {providerId === "kilter"
                  ? "This room will only be created after the Kilter credentials are validated. The next step inside the room is choosing the board plus angle."
                  : "This room will only be created after the Crux token is validated. The next step inside the room is choosing the gym and wall."}
              </div>

              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Authenticating host..." : "Authenticate and create room"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
