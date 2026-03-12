import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "@/api";
import CoachMarkOverlay, { type CoachMarkStep } from "@/components/CoachMarkOverlay";
import FeedbackPrompt from "@/components/FeedbackPrompt";
import MobilePageHeader from "@/components/MobilePageHeader";
import { getApiErrorDetails } from "@/lib/api-errors";
import {
  clearPendingSoloRoomSeed,
  completeGuideBranch,
  loadUserPrefs,
  markFeedbackPromptSeen,
  rememberCruxToken,
  rememberDisplayName,
  rememberKilterCredentials,
  rememberLastProvider,
  rememberRoomVisit,
  resolveHostRoomNameTemplate,
  resetGuides,
  shouldShowFeedbackPrompt,
} from "@/lib/user-prefs";
import { trackProductEvent } from "@/lib/product-analytics";
import type { ProviderId } from "@/types";
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
import { SecretInput } from "@/components/ui/secret-input";
import { useErrorToast } from "@/hooks/use-toast";
import { useIsMobile } from "@/hooks/use-mobile";
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
  getProviderLabel,
  getRoomProviderCapabilities,
} from "@/lib/provider-capabilities";
import { reportError, reportEvent } from "@/lib/observability";

const HOST_GUIDE_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="host-room-name"]',
    title: "Name the session first",
    description: "Give the room a recognizable name before you send the invite around.",
  },
  {
    target: '[data-guide="host-provider"]',
    title: "Choose the provider for this room",
    description: "The host connects one provider account here so everyone else can browse from their phones.",
  },
  {
    target: '[data-guide="host-auth"]',
    title: "Authenticate on this device",
    description: "This phone or browser becomes the control surface for provider auth and later room management.",
  },
  {
    target: '[data-guide="host-submit"]',
    title: "Open the room, then pick the surface",
    description: "After creation, the host chooses the shared board or wall, then shares the invite link or QR code.",
    placement: "top",
  },
];

export default function RoomCreatePage() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const savedPrefsRef = useRef(loadUserPrefs());
  const [prefs, setPrefs] = useState(() => savedPrefsRef.current);
  const [pendingRoomSeed, setPendingRoomSeed] = useState(
    () => savedPrefsRef.current.pendingRoomSeed
  );
  const { capabilities, loading: capabilitiesLoading } = useProviderCapabilities();
  const showErrorToast = useErrorToast();
  const [showGuide, setShowGuide] = useState(false);
  const [showFailureFeedback, setShowFailureFeedback] = useState(false);
  const [providerId, setProviderId] = useState<ProviderId>(
    () => pendingRoomSeed?.provider_id || savedPrefsRef.current.lastProviderId || "kilter"
  );
  const [roomName, setRoomName] = useState(() =>
    resolveHostRoomNameTemplate(savedPrefsRef.current.hostDefaults.roomNameTemplate)
  );
  const [displayName, setDisplayName] = useState(
    () => savedPrefsRef.current.savedDisplayName
  );
  const [fistBumpsEnabled, setFistBumpsEnabled] = useState(
    () => savedPrefsRef.current.hostDefaults.defaultFistBumpsEnabled
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

  useEffect(() => {
    if (
      isMobile &&
      prefs.settings.autoGuidesEnabled &&
      prefs.guidedTour.activeBranch === "host" &&
      !prefs.guidedTour.hostCompleted
    ) {
      setShowGuide(true);
    }
  }, [
    isMobile,
    prefs.guidedTour.activeBranch,
    prefs.guidedTour.hostCompleted,
    prefs.settings.autoGuidesEnabled,
  ]);

  useEffect(() => {
    if (!pendingRoomSeed?.provider_id) {
      return;
    }

    setProviderId(pendingRoomSeed.provider_id);
  }, [pendingRoomSeed?.provider_id]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCapability) {
      return;
    }
    setSubmitting(true);
    reportEvent("room.create", "host create room submitted", {
      providerId,
    });
    trackProductEvent("room.create.started", {
      viewerRole: "host",
      properties: {
        provider_id: providerId,
        has_pending_seed: Boolean(pendingRoomSeed),
      },
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
        fistBumpsEnabled,
      });
      reportEvent("room.create", "host create room succeeded", {
        providerId,
        slug: room.slug,
      });
      trackProductEvent("room.create.succeeded", {
        roomSlug: room.slug,
        viewerRole: "host",
        properties: {
          provider_id: providerId,
        },
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
      trackProductEvent("room.create.failed", {
        viewerRole: "host",
        properties: {
          provider_id: providerId,
          code: typeof details.code === "string" ? details.code : "unknown",
        },
      });
      reportError(caughtError, {
        extra: { providerId },
        tags: {
          code: typeof details.code === "string" ? details.code : "unknown",
          flow: "room_create",
        },
      });
      if (shouldShowFeedbackPrompt("room-create-failure")) {
        setShowFailureFeedback(true);
      }
      showErrorToast(details.message);
    } finally {
      setSubmitting(false);
    }
  };

  const pendingSeedDescription = pendingRoomSeed
    ? `${getProviderLabel(pendingRoomSeed.provider_id, capabilities)} plan for ${pendingRoomSeed.surface.name}`
    : "";

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(240,253,250,0.95),_rgba(255,255,255,1))] px-4 py-4 sm:px-6 sm:py-8">
      <CoachMarkOverlay
        open={showGuide}
        steps={HOST_GUIDE_STEPS}
        onClose={() => {
          setShowGuide(false);
          trackProductEvent("onboarding.skipped", {
            viewerRole: "host",
            properties: { branch: "host" },
          });
        }}
        onComplete={() => {
          const nextPrefs = completeGuideBranch("host");
          savedPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
          trackProductEvent("onboarding.completed", {
            viewerRole: "host",
            properties: { branch: "host" },
          });
        }}
      />
      <FeedbackPrompt
        open={showFailureFeedback}
        title="Was room creation blocked in a useful way?"
        description="A quick thumbs-up or thumbs-down helps tune provider auth and room setup failures."
        onClose={() => {
          const nextPrefs = markFeedbackPromptSeen("room-create-failure");
          savedPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
          setShowFailureFeedback(false);
        }}
        onSubmit={async ({ sentiment, message }) => {
          await api.submitFeedback({
            promptFamily: "room-create-failure",
            sentiment,
            message,
            metadata: {
              provider_id: providerId,
            },
          });
          const nextPrefs = markFeedbackPromptSeen("room-create-failure");
          savedPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
          setShowFailureFeedback(false);
        }}
      />
      <div className="mx-auto max-w-2xl">
        <MobilePageHeader
          title="Create a room"
          backTo="/"
          backLabel="Community mode"
          onHelp={() => {
            const nextPrefs = resetGuides();
            savedPrefsRef.current = nextPrefs;
            setPrefs(nextPrefs);
            setShowGuide(true);
          }}
        />
        <div className="mb-6 hidden flex-wrap items-center justify-between gap-2 md:flex">
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
                const nextPrefs = resetGuides();
                savedPrefsRef.current = nextPrefs;
                setPrefs(nextPrefs);
                setShowGuide(true);
              }}
            >
              Help
            </HeaderNavButton>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
          </div>
        </div>

        {pendingRoomSeed ? (
          <div className="mb-5 rounded-2xl border border-teal-200 bg-teal-50/80 px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-medium text-teal-900">Saved plan seed is ready</p>
                <p className="text-sm text-teal-900/80">
                  <span className="block">{pendingSeedDescription}</span>
                  This room can start from the saved {pendingRoomSeed.surface.kind} context and
                  import {pendingRoomSeed.climbs.length} queued climb
                  {pendingRoomSeed.climbs.length === 1 ? "" : "s"} after you confirm the shared
                  surface inside the room.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                className="border-teal-200 bg-white/80"
                onClick={() => {
                  const nextPrefs = clearPendingSoloRoomSeed();
                  savedPrefsRef.current = nextPrefs;
                  setPrefs(nextPrefs);
                  setPendingRoomSeed(undefined);
                }}
              >
                Discard seed
              </Button>
            </div>
          </div>
        ) : null}

        <Card className="shadow-lg shadow-teal-950/10">
          <CardHeader>
            <CardTitle className="text-2xl sm:text-3xl">Create a collaborative room</CardTitle>
            <CardDescription className="text-sm sm:text-base">
              Authenticate the host account once before the room opens. Hosts and guests can both
              manage the live session from a phone-first room view after setup.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label
                  htmlFor="room-name"
                  className="text-sm font-medium"
                  data-guide="host-room-name"
                >
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

              <div className="rounded-2xl border bg-slate-50/80 px-4 py-4">
                <label className="flex items-start gap-3 text-sm font-medium text-foreground">
                  <input
                    type="checkbox"
                    checked={fistBumpsEnabled}
                    onChange={(event) => setFistBumpsEnabled(event.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300"
                  />
                  <span className="space-y-1">
                    <span className="block">Start with fist bumps enabled</span>
                    <span className="block text-sm font-normal text-muted-foreground">
                      This room default comes from your saved host preset, and you can override it
                      per session here.
                    </span>
                  </span>
                </label>
              </div>

              <div className="space-y-2" data-guide="host-provider">
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
                <div className="grid gap-5 md:grid-cols-2" data-guide="host-auth">
                  {selectedCapability.auth_fields.map((field) => (
                    <div key={field.key} className="space-y-2">
                      <label htmlFor={`provider-${field.key}`} className="text-sm font-medium">
                        {field.label}
                      </label>
                      {field.type === "password" ? (
                        <SecretInput
                          id={`provider-${field.key}`}
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
                      ) : (
                        <Input
                          id={`provider-${field.key}`}
                          type="text"
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
                      )}
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
                      Stores the username and this preference locally. You still enter the password
                      each time.
                    </p>
                  </div>
                </div>
              ) : selectedCapability ? (
                <div className="space-y-2" data-guide="host-auth">
                  {selectedCapability.auth_fields.map((field) => (
                    <div key={field.key} className="space-y-2">
                      <label htmlFor={`provider-${field.key}`} className="text-sm font-medium">
                        {field.label}
                      </label>
                      {field.type === "password" ? (
                        <SecretInput
                          id={`provider-${field.key}`}
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
                      ) : (
                        <Input
                          id={`provider-${field.key}`}
                          type="text"
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
                      )}
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
                data-guide="host-submit"
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
