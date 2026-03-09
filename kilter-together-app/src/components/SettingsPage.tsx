import { useState } from "react";
import { History, Sparkles, User } from "lucide-react";
import { Link } from "react-router-dom";
import type { ClimbSort, ProviderId } from "@/types";
import BrandWordmark from "@/components/BrandWordmark";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  clearRecentRooms,
  clearSavedCredentials,
  clearSoloResume,
  loadUserPrefs,
  resetGuides,
  updateAppSettings,
  updateUserPrefs,
} from "@/lib/user-prefs";

function SettingsToggle({
  id,
  label,
  description,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label
      htmlFor={id}
      className="flex items-start justify-between gap-4 rounded-2xl border bg-white/70 px-4 py-4"
    >
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 rounded border-slate-300"
      />
    </label>
  );
}

function SettingsActionRow({
  title,
  description,
  actionLabel,
  disabled = false,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel: string;
  disabled?: boolean;
  onAction: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border bg-white/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <Button type="button" variant="outline" disabled={disabled} onClick={onAction}>
        {actionLabel}
      </Button>
    </div>
  );
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const preferredProvider = prefs.lastProviderId === "crux" ? "crux" : "kilter";
  const hasSavedCredentials =
    prefs.savedCredentials.kilter.remember || prefs.savedCredentials.crux.remember;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.16),_transparent_34%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 pb-24 pt-8">
        <header className="flex flex-wrap items-start justify-between gap-4 py-2">
          <h1 className="leading-none">
            <Link to="/" aria-label="Back to home page" className="inline-flex">
              <BrandWordmark />
            </Link>
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="ghost">
              <Link to="/about">About</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/">Community mode</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/solo">Solo browse</Link>
            </Button>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 py-8">
          <Card className="border-0 bg-white/88 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader className="gap-4">
              <div className="inline-flex w-fit items-center gap-2 rounded-full bg-teal-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-teal-700">
                <Sparkles className="h-3.5 w-3.5" />
                Settings
              </div>
              <div>
                <CardTitle className="text-3xl">Customize this browser</CardTitle>
                <CardDescription className="mt-3 max-w-3xl text-base leading-7">
                  These settings stay local to this browser. They control the playful touches,
                  default solo behavior, onboarding guides, and what data the app keeps around
                  between sessions.
                </CardDescription>
              </div>
            </CardHeader>
          </Card>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <Card className="border-0 bg-white/88 shadow-xl shadow-teal-950/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <Sparkles className="h-5 w-5" />
                  Experience
                </CardTitle>
                <CardDescription>
                  Toggle the parts of the interface that feel more playful or more guided.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3">
                <SettingsToggle
                  id="click-cheers-enabled"
                  label="Show cursor encouragement words"
                  description="Spawn floating cheers like allez and がんばって when you click with the mouse."
                  checked={prefs.settings.clickCheersEnabled}
                  onChange={(checked) => setPrefs(updateAppSettings({ clickCheersEnabled: checked }))}
                />
                <SettingsToggle
                  id="playful-motion-enabled"
                  label="Enable playful motion"
                  description="Keep the wordmark wiggle, link highlight wipe, and loading-frame cycling turned on."
                  checked={prefs.settings.playfulMotionEnabled}
                  onChange={(checked) => setPrefs(updateAppSettings({ playfulMotionEnabled: checked }))}
                />
                <SettingsToggle
                  id="auto-guides-enabled"
                  label="Show onboarding guides automatically"
                  description="Open landing, solo, and room help callouts by default for unfinished flows. Manual Help still works either way."
                  checked={prefs.settings.autoGuidesEnabled}
                  onChange={(checked) => setPrefs(updateAppSettings({ autoGuidesEnabled: checked }))}
                />
                <SettingsToggle
                  id="recent-rooms-enabled"
                  label="Save recent rooms"
                  description="Keep the latest room visits on the landing page for quick re-entry from this browser."
                  checked={prefs.settings.recentRoomsEnabled}
                  onChange={(checked) => setPrefs(updateAppSettings({ recentRoomsEnabled: checked }))}
                />
              </CardContent>
            </Card>

            <div className="grid gap-6">
              <Card className="border-0 bg-white/88 shadow-xl shadow-teal-950/10 backdrop-blur">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-2xl">
                    <User className="h-5 w-5" />
                    Defaults
                  </CardTitle>
                  <CardDescription>
                    Pre-fill the choices you keep using across rooms and solo browse.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-5">
                  <div className="space-y-2">
                    <label htmlFor="settings-display-name" className="text-sm font-medium">
                      Preferred display name
                    </label>
                    <Input
                      id="settings-display-name"
                      value={prefs.savedDisplayName}
                      onChange={(event) =>
                        setPrefs(
                          updateUserPrefs((currentPrefs) => ({
                            ...currentPrefs,
                            savedDisplayName: event.target.value,
                          }))
                        )
                      }
                      placeholder="Gabriel, Spotter, Session host"
                    />
                    <p className="text-xs leading-6 text-muted-foreground">
                      Used to pre-fill the join and host forms on this browser.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="settings-provider" className="text-sm font-medium">
                      Default host provider
                    </label>
                    <Select
                      value={preferredProvider}
                      onValueChange={(value) =>
                        setPrefs(
                          updateUserPrefs((currentPrefs) => ({
                            ...currentPrefs,
                            lastProviderId: value as ProviderId,
                          }))
                        )
                      }
                    >
                      <SelectTrigger id="settings-provider">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="kilter">Kilter</SelectItem>
                        <SelectItem value="crux">Crux</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="settings-solo-sort" className="text-sm font-medium">
                      Solo browse default sort
                    </label>
                    <Select
                      value={prefs.settings.soloDefaultSort}
                      onValueChange={(value) =>
                        setPrefs(
                          updateAppSettings({ soloDefaultSort: value as ClimbSort })
                        )
                      }
                    >
                      <SelectTrigger id="settings-solo-sort">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="popular">Popular</SelectItem>
                        <SelectItem value="newest">Newest</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs leading-6 text-muted-foreground">
                      Applied whenever you open a board from the solo board list.
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-0 bg-white/88 shadow-xl shadow-teal-950/10 backdrop-blur">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-2xl">
                    <History className="h-5 w-5" />
                    Stored data
                  </CardTitle>
                  <CardDescription>
                    Clear the local browser state that supports faster returns into the app.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <SettingsActionRow
                    title="Reset guides"
                    description="Replay the onboarding and intro dialogs the next time automatic guides are allowed."
                    actionLabel="Reset guides"
                    onAction={() => setPrefs(resetGuides())}
                  />
                  <SettingsActionRow
                    title="Clear recent rooms"
                    description={`Forget the ${prefs.recentRooms.length} saved room${prefs.recentRooms.length === 1 ? "" : "s"} shown on the landing page.`}
                    actionLabel="Clear recent rooms"
                    disabled={prefs.recentRooms.length === 0}
                    onAction={() => setPrefs(clearRecentRooms())}
                  />
                  <SettingsActionRow
                    title="Clear saved credentials"
                    description="Remove any locally remembered Kilter login or Crux token from this browser."
                    actionLabel="Clear saved credentials"
                    disabled={!hasSavedCredentials}
                    onAction={() => setPrefs(clearSavedCredentials())}
                  />
                  <SettingsActionRow
                    title="Forget solo resume"
                    description="Drop the saved board, filters, and selected climb used by Resume solo browse."
                    actionLabel="Forget solo resume"
                    disabled={!prefs.soloResume}
                    onAction={() => setPrefs(clearSoloResume())}
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
