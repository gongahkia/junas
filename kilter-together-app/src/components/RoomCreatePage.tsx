import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import type { ProviderId } from "@/types";
import { getApiErrorDetails } from "@/lib/api-errors";
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
import { HeaderNavButton, HeaderNavLink } from "@/components/HeaderNavAction";
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
import { useProviderCapabilities } from "@/hooks/useProviderCapabilities";
import {
  getProviderCapability,
  getRoomProviderCapabilities,
} from "@/lib/provider-capabilities";
import { reportError, reportEvent } from "@/lib/observability";

export default function RoomCreatePage() {
  const navigate = useNavigate();
  const savedPrefsRef = useRef(loadUserPrefs());
  const { capabilities, loading: capabilitiesLoading } = useProviderCapabilities();
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
  const [connectionFields, setConnectionFields] = useState<Record<string, string>>(() => ({
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
  const roomCapabilities = getRoomProviderCapabilities(capabilities);
  const selectedCapability =
    getProviderCapability(providerId, roomCapabilities) ?? roomCapabilities[0];

  useEffect(() => {
    if (!selectedCapability && roomCapabilities.length > 0) {
      setProviderId(roomCapabilities[0].id);
    }
  }, [roomCapabilities, selectedCapability]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCapability) {
      return;
    }
    setSubmitting(true);
    reportEvent("room.create", "host create room submitted", {
      providerId,
    });

    try {
      const secret: Record<string, string> = {};
      for (const field of selectedCapability.auth_fields) {
        secret[field.key] = connectionFields[field.key] ?? "";
      }

      const room = await api.createRoom({
        providerId,
        roomName,
        displayName,
        secret,
      });
      reportEvent("room.create", "host create room succeeded", {
        providerId,
        slug: room.slug,
      });
      rememberDisplayName(displayName);
      rememberLastProvider(providerId);
      if (providerId === "kilter") {
        rememberKilterCredentials(
          connectionFields.username,
          connectionFields.password,
          rememberCredentials.kilter
        );
      } else if (providerId === "crux") {
        rememberCruxToken(connectionFields.token, rememberCredentials.crux);
      }
      rememberRoomVisit(room);
      navigate(`/rooms/${room.slug}`);
    } catch (caughtError) {
      console.error("Create room failed", caughtError);
      const details = getApiErrorDetails(
        caughtError,
        "Unable to create the room. Make sure the API server is running and check the backend logs."
      );
      reportError(caughtError, {
        extra: { providerId },
        tags: {
          code: typeof details.code === "string" ? details.code : "unknown",
          flow: "room_create",
        },
      });
      showErrorToast(details.message);
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
            <HeaderNavButton
              type="button"
              onClick={() => {
                resetOnboardingPrefs();
                setShowOnboarding(true);
              }}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
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
                    {roomCapabilities.map((capability) => (
                      <SelectItem key={capability.id} value={capability.id}>
                        {capability.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {selectedCapability?.id === "kilter" ? (
                <div className="grid gap-5 md:grid-cols-2">
                  {selectedCapability.auth_fields.map((field) => (
                    <div key={field.key} className="space-y-2">
                      <label htmlFor={`provider-${field.key}`} className="text-sm font-medium">
                        {field.label}
                      </label>
                      <Input
                        id={`provider-${field.key}`}
                        type={field.type === "password" ? "password" : "text"}
                        value={connectionFields[field.key] ?? ""}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            [field.key]: event.target.value,
                          }))
                        }
                        autoComplete={field.autocomplete ?? "off"}
                        placeholder={field.placeholder}
                      />
                    </div>
                  ))}
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
              ) : selectedCapability ? (
                <div className="space-y-2">
                  {selectedCapability.auth_fields.map((field) => (
                    <div key={field.key} className="space-y-2">
                      <label htmlFor={`provider-${field.key}`} className="text-sm font-medium">
                        {field.label}
                      </label>
                      <Input
                        id={`provider-${field.key}`}
                        type={field.type === "password" ? "password" : "text"}
                        value={connectionFields[field.key] ?? ""}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            [field.key]: event.target.value,
                          }))
                        }
                        autoComplete={field.autocomplete ?? "off"}
                        placeholder={field.placeholder}
                      />
                    </div>
                  ))}
                  {selectedCapability.id === "crux" ? (
                    <p className="text-sm text-muted-foreground">
                      Paste either the raw Crux token or the full <code>Bearer ...</code> value.
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      This provider is available only when the test mode env vars are enabled.
                    </p>
                  )}
                  {selectedCapability.id === "crux" ? (
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
                  ) : null}
                  {selectedCapability.id === "crux" ? (
                    <p className="text-xs text-muted-foreground">
                      Stores this preference locally. You still enter the Crux token each time.
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Loading supported providers...
                </div>
              )}

              <div className="rounded-2xl border bg-muted/40 p-4 text-sm text-muted-foreground">
                {selectedCapability?.id === "kilter"
                  ? "This room will only be created after the Kilter credentials are validated. The next step inside the room is choosing the board plus angle."
                  : selectedCapability?.id === "crux"
                    ? "This room will only be created after the Crux token is validated. The next step inside the room is choosing the gym and wall."
                    : "This room will only be created after the host credentials are validated. The next step inside the room is choosing the shared surface."}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={submitting || capabilitiesLoading || !selectedCapability}
              >
                {submitting ? "Authenticating host..." : "Authenticate and create room"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
