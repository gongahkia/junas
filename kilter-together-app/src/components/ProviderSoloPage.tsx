import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Compass,
  KeyRound,
  MapPinned,
  Mountain,
  RefreshCw,
  Share2,
} from "lucide-react";
import { api } from "@/api";
import BrandWordmark from "@/components/BrandWordmark";
import LoadingSlideshow from "@/components/LoadingSlideshow";
import RoomProblemView from "@/components/RoomProblemView";
import SortSelector from "@/components/SortSelector";
import { HeaderNavLink } from "@/components/HeaderNavAction";
import { Badge } from "@/components/ui/badge";
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
import { useProviderCapabilities } from "@/hooks/useProviderCapabilities";
import { getApiErrorMessage } from "@/lib/api-errors";
import { getProviderCapability } from "@/lib/provider-capabilities";
import { normalizeSort } from "@/lib/climbs";
import {
  beginRoomSeed,
  loadUserPrefs,
  rememberLastCruxSurface,
  rememberLastProvider,
} from "@/lib/user-prefs";
import { trackProductEvent } from "@/lib/product-analytics";
import type {
  ClimbSort,
  ProviderCapability,
  ProviderClimb,
  ProviderId,
  ProviderSurface,
} from "@/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PAGE_SIZE = 10;

function formatProviderMetaLine(climb: ProviderClimb) {
  const parts = [
    climb.meta?.source_label,
    climb.meta?.color,
    climb.meta?.foot_rules,
  ].filter((value): value is string => Boolean(value?.trim()));
  return parts.join(" · ");
}

function normalizeSecretFields(
  capability: ProviderCapability | undefined,
  fields: Record<string, string>
) {
  if (!capability) {
    return {};
  }

  return capability.auth_fields.reduce<Record<string, string>>((secret, field) => {
    secret[field.key] = fields[field.key]?.trim() ?? "";
    return secret;
  }, {});
}

export default function ProviderSoloPage() {
  const { providerId = "" } = useParams();
  const resolvedProviderId = providerId as ProviderId;
  const navigate = useNavigate();
  const showErrorToast = useErrorToast();
  const savedPrefsRef = useRef(loadUserPrefs());
  const accessSecretRef = useRef<Record<string, string>>({});
  const cursorsRef = useRef<Record<number, string>>({});
  const lastFilterKeyRef = useRef("");
  const { capabilities, loading: capabilitiesLoading } = useProviderCapabilities();
  const capability = getProviderCapability(resolvedProviderId, capabilities);
  const [searchParams, setSearchParams] = useSearchParams();
  const [connectionFields, setConnectionFields] = useState<Record<string, string>>({});
  const [accessLoaded, setAccessLoaded] = useState(false);
  const [surfacesLoading, setSurfacesLoading] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [parentSurfaces, setParentSurfaces] = useState<ProviderSurface[]>([]);
  const [childSurfaces, setChildSurfaces] = useState<ProviderSurface[]>([]);
  const [climbs, setClimbs] = useState<ProviderClimb[]>([]);
  const [selectedClimb, setSelectedClimb] = useState<ProviderClimb | null>(null);
  const [plannedClimbs, setPlannedClimbs] = useState<ProviderClimb[]>([]);
  const [planTitle, setPlanTitle] = useState("");
  const [planNotes, setPlanNotes] = useState("");
  const [sharingPlan, setSharingPlan] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const selectedGymSlug = searchParams.get("gym") ?? "";
  const selectedWallId = searchParams.get("wall") ?? "";
  const rawQuery = searchParams.get("q") ?? "";
  const rawSort = searchParams.get("sort");
  const sort = normalizeSort(rawSort);
  const selectedClimbId = searchParams.get("climb") ?? "";
  const deferredQuery = useDeferredValue(rawQuery);
  const providerLabel = capability?.label ?? providerId;
  const canLoadCatalog = capability
    ? capability.auth_fields.every((field) => Boolean(connectionFields[field.key]?.trim()))
    : false;

  useEffect(() => {
    if (!capability) {
      return;
    }

    setConnectionFields((currentFields) =>
      capability.auth_fields.reduce<Record<string, string>>((nextFields, field) => {
        nextFields[field.key] = currentFields[field.key] ?? "";
        return nextFields;
      }, {})
    );
  }, [capability]);

  useEffect(() => {
    if (capabilitiesLoading || !capability) {
      return;
    }

    const nextSearchParams = new URLSearchParams(searchParams);
    let changed = false;

    if (rawSort !== sort) {
      nextSearchParams.set("sort", sort);
      changed = true;
    }

    if (resolvedProviderId === "crux") {
      if (!selectedGymSlug && savedPrefsRef.current.lastCrux.gymSlug) {
        nextSearchParams.set("gym", savedPrefsRef.current.lastCrux.gymSlug);
        changed = true;
      }
      if (!selectedWallId && savedPrefsRef.current.lastCrux.wallId) {
        nextSearchParams.set("wall", savedPrefsRef.current.lastCrux.wallId);
        changed = true;
      }
    }

    if (changed) {
      setSearchParams(nextSearchParams, { replace: true });
    }
  }, [
    capabilitiesLoading,
    capability,
    rawSort,
    resolvedProviderId,
    searchParams,
    selectedGymSlug,
    selectedWallId,
    setSearchParams,
    sort,
  ]);

  useEffect(() => {
    if (!accessLoaded || !selectedGymSlug) {
      setChildSurfaces([]);
      return;
    }

    let cancelled = false;
    setSurfacesLoading(true);

    void (async () => {
      try {
        const nextWalls = await api.getSoloProviderSurfaces(resolvedProviderId, {
          secret: accessSecretRef.current,
          parentId: selectedGymSlug,
        });
        if (cancelled) {
          return;
        }

        setChildSurfaces(nextWalls);
        const hasSelectedWall = nextWalls.some((surface) => surface.id === selectedWallId);
        if (!hasSelectedWall && selectedWallId) {
          const nextSearchParams = new URLSearchParams(searchParams);
          nextSearchParams.delete("wall");
          nextSearchParams.delete("climb");
          setSearchParams(nextSearchParams, { replace: true });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        setChildSurfaces([]);
        showErrorToast(
          getApiErrorMessage(error, `Unable to load ${providerLabel} wall options.`)
        );
      } finally {
        if (!cancelled) {
          setSurfacesLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    accessLoaded,
    providerLabel,
    resolvedProviderId,
    searchParams,
    selectedGymSlug,
    selectedWallId,
    setSearchParams,
    showErrorToast,
  ]);

  useEffect(() => {
    if (resolvedProviderId !== "crux" || !selectedGymSlug) {
      return;
    }

    savedPrefsRef.current = rememberLastCruxSurface(selectedGymSlug, selectedWallId);
  }, [resolvedProviderId, selectedGymSlug, selectedWallId]);

  useEffect(() => {
    if (!accessLoaded || !selectedGymSlug) {
      setClimbs([]);
      setSelectedClimb(null);
      setHasMore(false);
      return;
    }

    const nextFilterKey = JSON.stringify({
      providerId: resolvedProviderId,
      gym: selectedGymSlug,
      q: deferredQuery,
      sort,
    });
    const filtersChanged = lastFilterKeyRef.current !== nextFilterKey;
    if (filtersChanged) {
      lastFilterKeyRef.current = nextFilterKey;
      cursorsRef.current = {};
      setHasMore(false);
      if (currentPage !== 1) {
        setCurrentPage(1);
        return;
      }
    }

    let cancelled = false;
    setCatalogLoading(true);

    void (async () => {
      try {
        const response = await api.getSoloProviderClimbs(resolvedProviderId, {
          secret: accessSecretRef.current,
          surfaceId: selectedWallId || selectedGymSlug,
          context: {
            gym_slug: selectedGymSlug,
          },
          q: deferredQuery || undefined,
          sort,
          cursor: currentPage > 1 ? cursorsRef.current[currentPage] : undefined,
          pageSize: PAGE_SIZE,
        });
        if (cancelled) {
          return;
        }

        setClimbs(response.climbs);
        setHasMore(response.has_more);
        if (response.next_cursor) {
          cursorsRef.current = {
            ...cursorsRef.current,
            [currentPage + 1]: response.next_cursor,
          };
        }

        const nextSelectedClimb =
          response.climbs.find((climb) => climb.id === selectedClimbId) ||
          response.climbs[0] ||
          null;
        const nextSearchParams = new URLSearchParams(searchParams);
        if (nextSelectedClimb) {
          nextSearchParams.set("climb", nextSelectedClimb.id);
        } else {
          nextSearchParams.delete("climb");
        }
        if (nextSelectedClimb?.id !== selectedClimbId) {
          setSearchParams(nextSearchParams, { replace: true });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        setClimbs([]);
        setSelectedClimb(null);
        setHasMore(false);
        showErrorToast(
          getApiErrorMessage(error, `Unable to load ${providerLabel} climbs right now.`)
        );
      } finally {
        if (!cancelled) {
          setCatalogLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    accessLoaded,
    currentPage,
    deferredQuery,
    providerLabel,
    resolvedProviderId,
    searchParams,
    selectedClimbId,
    selectedGymSlug,
    selectedWallId,
    setSearchParams,
    showErrorToast,
    sort,
  ]);

  useEffect(() => {
    if (!accessLoaded || !selectedGymSlug || !selectedClimbId) {
      return;
    }

    const listSelectedClimb = climbs.find((climb) => climb.id === selectedClimbId) ?? null;
    let cancelled = false;
    setDetailLoading(true);

    void (async () => {
      try {
        const response = await api.getSoloProviderClimb(resolvedProviderId, selectedClimbId, {
          secret: accessSecretRef.current,
          surfaceId: selectedWallId || selectedGymSlug,
          context: {
            gym_slug: selectedGymSlug,
          },
        });
        if (cancelled) {
          return;
        }

        setSelectedClimb({
          ...response.climb,
          meta: {
            ...(listSelectedClimb?.meta ?? {}),
            ...(response.climb.meta ?? {}),
          },
        });
      } catch (error) {
        if (cancelled) {
          return;
        }

        setSelectedClimb(listSelectedClimb);
        showErrorToast(
          getApiErrorMessage(error, `Unable to load the ${providerLabel} climb detail.`)
        );
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    accessLoaded,
    climbs,
    providerLabel,
    resolvedProviderId,
    selectedClimbId,
    selectedGymSlug,
    selectedWallId,
    showErrorToast,
  ]);

  useEffect(() => {
    if (planTitle.trim()) {
      return;
    }

    const nextTitle =
      childSurfaces.find((surface) => surface.id === selectedWallId)?.name ||
      parentSurfaces.find((surface) => surface.id === selectedGymSlug)?.name;

    if (nextTitle) {
      setPlanTitle(`${nextTitle} plan`);
    }
  }, [childSurfaces, parentSurfaces, planTitle, selectedGymSlug, selectedWallId]);

  useEffect(() => {
    if (!selectedClimb) {
      return;
    }

    setPlannedClimbs((currentClimbs) =>
      currentClimbs.map((climb) =>
        climb.id === selectedClimb.id
          ? {
              ...climb,
              ...selectedClimb,
              meta: {
                ...(climb.meta ?? {}),
                ...(selectedClimb.meta ?? {}),
              },
            }
          : climb
      )
    );
  }, [selectedClimb]);

  if (capabilitiesLoading) {
    return (
      <LoadingSlideshow
        title="Loading provider solo browse"
        description="Checking which connected catalog providers support standalone solo browse."
        detail="This keeps the Kilter solo flow and the provider-specific solo flows on the same capabilities contract."
      />
    );
  }

  if (!capability || !capability.solo_supported || capability.surface_hierarchy === "board") {
    return <Navigate to="/solo" replace />;
  }

  const selectedGym =
    parentSurfaces.find((surface) => surface.id === selectedGymSlug) ??
    null;
  const selectedWall =
    childSurfaces.find((surface) => surface.id === selectedWallId) ??
    null;

  const updateSearchState = (updates: Record<string, string | undefined>) => {
    startTransition(() => {
      const nextSearchParams = new URLSearchParams(searchParams);
      for (const [key, value] of Object.entries(updates)) {
        if (value?.trim()) {
          nextSearchParams.set(key, value);
        } else {
          nextSearchParams.delete(key);
        }
      }

      if (Object.prototype.hasOwnProperty.call(updates, "q") ||
          Object.prototype.hasOwnProperty.call(updates, "sort") ||
          Object.prototype.hasOwnProperty.call(updates, "gym")) {
        nextSearchParams.delete("climb");
      }
      if (Object.prototype.hasOwnProperty.call(updates, "gym")) {
        nextSearchParams.delete("wall");
      }
      if (Object.prototype.hasOwnProperty.call(updates, "wall")) {
        nextSearchParams.delete("climb");
      }

      cursorsRef.current = {};
      setCurrentPage(1);
      setHasMore(false);
      setSearchParams(nextSearchParams);
    });
  };

  const handleLoadCatalog = async () => {
    if (!capability) {
      return;
    }

    const nextSecret = normalizeSecretFields(capability, connectionFields);
    if (capability.auth_fields.some((field) => !nextSecret[field.key])) {
      showErrorToast(`Enter the required ${providerLabel} credentials first.`);
      return;
    }

    setSurfacesLoading(true);
    try {
      const surfaces = await api.getSoloProviderSurfaces(resolvedProviderId, {
        secret: nextSecret,
      });
      accessSecretRef.current = nextSecret;
      setAccessLoaded(true);
      setParentSurfaces(surfaces);
      savedPrefsRef.current = rememberLastProvider(resolvedProviderId);

      const nextSearchParams = new URLSearchParams(searchParams);
      const nextGymSlug =
        surfaces.find((surface) => surface.id === selectedGymSlug)?.id ??
        surfaces[0]?.id ??
        "";
      if (nextGymSlug) {
        nextSearchParams.set("gym", nextGymSlug);
      } else {
        nextSearchParams.delete("gym");
      }
      if (nextGymSlug !== selectedGymSlug) {
        nextSearchParams.delete("wall");
        nextSearchParams.delete("climb");
      }
      setSearchParams(nextSearchParams, { replace: true });
    } catch (error) {
      setAccessLoaded(false);
      setParentSurfaces([]);
      setChildSurfaces([]);
      setClimbs([]);
      setSelectedClimb(null);
      showErrorToast(
        getApiErrorMessage(error, `Unable to unlock the ${providerLabel} solo catalog.`)
      );
    } finally {
      setSurfacesLoading(false);
    }
  };

  const handleCreateRoomFromContext = () => {
    const roomSurface = selectedWall ?? selectedGym;
    if (!roomSurface) {
      showErrorToast(`Choose a ${providerLabel} surface before creating a room.`);
      return;
    }

    savedPrefsRef.current = beginRoomSeed({
      providerId: resolvedProviderId,
      title: planTitle.trim() || `${roomSurface.name} session`,
      surface: roomSurface,
      climbs: plannedClimbs,
      openPath:
        typeof window !== "undefined"
          ? `${window.location.pathname}${window.location.search}`
          : undefined,
    });
    if (resolvedProviderId === "crux") {
      savedPrefsRef.current = rememberLastCruxSurface(selectedGymSlug, selectedWallId);
    }
    navigate("/rooms/new");
  };

  const togglePlannedClimb = (climb: ProviderClimb) => {
    setPlannedClimbs((currentClimbs) => {
      const alreadyPlanned = currentClimbs.some((item) => item.id === climb.id);
      if (alreadyPlanned) {
        return currentClimbs.filter((item) => item.id !== climb.id);
      }

      return [
        {
          ...climb,
          meta: {
            ...(climb.meta ?? {}),
            gym_slug: selectedGymSlug,
            wall_id: selectedWallId,
          },
        },
        ...currentClimbs,
      ];
    });
  };

  const handleSharePlan = async () => {
    const roomSurface = selectedWall ?? selectedGym;
    if (!roomSurface) {
      showErrorToast(`Choose a ${providerLabel} surface before creating a plan.`);
      return;
    }
    if (plannedClimbs.length === 0) {
      showErrorToast("Add at least one climb to the plan before sharing it.");
      return;
    }

    setSharingPlan(true);
    try {
      const plan = await api.createSoloPlan({
        providerId: resolvedProviderId,
        title: planTitle.trim() || `${roomSurface.name} plan`,
        notes: planNotes.trim() || undefined,
        surface: roomSurface,
        context: {
          gym_slug: selectedGymSlug,
          wall_id: selectedWallId,
        },
        filters: {
          q: rawQuery || "",
          sort,
          gym: selectedGymSlug,
          wall: selectedWallId,
        },
        climbs: plannedClimbs,
        openPath:
          typeof window !== "undefined"
            ? `${window.location.pathname}${window.location.search}`
            : undefined,
        createdBy: savedPrefsRef.current.savedDisplayName || undefined,
      });
      trackProductEvent("solo_plan.create", {
        properties: {
          provider_id: resolvedProviderId,
          climb_count: plannedClimbs.length,
        },
      });
      navigate(`/plans/${plan.share_id}`);
    } catch (error) {
      console.error("Create provider solo plan failed", error);
      showErrorToast("Unable to create a shareable plan from this provider view.");
    } finally {
      setSharingPlan(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(148,163,184,0.24),_transparent_36%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(241,245,249,0.94))]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="flex items-center justify-between py-4">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Solo {providerLabel} Browse
            </p>
            <h1 className="mt-3 leading-none">
              <Link to="/" aria-label="Back to home page" className="inline-flex">
                <BrandWordmark />
              </Link>
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <HeaderNavLink to="/solo">Kilter solo</HeaderNavLink>
            <HeaderNavLink to="/about">About</HeaderNavLink>
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
            <HeaderNavLink to="/">Community mode</HeaderNavLink>
          </div>
        </header>

        <main className="grid flex-1 gap-6 py-8 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
          <div className="grid gap-6">
            <Card className="border-0 bg-white/88 shadow-xl shadow-slate-900/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <KeyRound className="h-5 w-5" />
                  Access the {providerLabel} catalog
                </CardTitle>
                <CardDescription>
                  Credentials are sent only to your own Kilter Together backend for provider
                  requests and are not stored by solo browse in this browser.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                {capability.auth_fields.map((field) => (
                  <div key={field.key} className="grid gap-2">
                    <label htmlFor={`solo-${field.key}`} className="text-sm font-medium">
                      {field.label}
                    </label>
                    <Input
                      id={`solo-${field.key}`}
                      type={field.type}
                      autoComplete={field.autocomplete}
                      placeholder={field.placeholder}
                      value={connectionFields[field.key] ?? ""}
                      onChange={(event) =>
                        setConnectionFields((currentFields) => ({
                          ...currentFields,
                          [field.key]: event.target.value,
                        }))
                      }
                    />
                  </div>
                ))}

                <div className="flex flex-wrap gap-3 pt-1">
                  <Button
                    type="button"
                    onClick={() => void handleLoadCatalog()}
                    disabled={!canLoadCatalog || surfacesLoading}
                  >
                    {surfacesLoading ? "Loading catalog..." : `Load ${providerLabel} catalog`}
                  </Button>
                  {accessLoaded ? (
                    <Badge variant="secondary" className="px-3 py-1">
                      Catalog unlocked for this tab
                    </Badge>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-white/88 shadow-xl shadow-slate-900/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <MapPinned className="h-5 w-5" />
                  Surface context
                </CardTitle>
                <CardDescription>
                  Pick the gym first, then optionally keep a wall selected as the room handoff
                  context.
                  {resolvedProviderId === "crux"
                    ? " The current Crux provider catalog is gym-wide, so wall selection is preserved as session context rather than a hard solo filter."
                    : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Gym</label>
                  <Select
                    value={selectedGymSlug}
                    onValueChange={(value) => updateSearchState({ gym: value })}
                    disabled={!accessLoaded || surfacesLoading || parentSurfaces.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a gym" />
                    </SelectTrigger>
                    <SelectContent>
                      {parentSurfaces.map((surface) => (
                        <SelectItem key={surface.id} value={surface.id}>
                          {surface.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <label className="text-sm font-medium">Wall context</label>
                  <Select
                    value={selectedWallId || "__none__"}
                    onValueChange={(value) =>
                      updateSearchState({
                        wall: value === "__none__" ? undefined : value,
                      })
                    }
                    disabled={!accessLoaded || surfacesLoading || childSurfaces.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a wall" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">No wall selected</SelectItem>
                      {childSurfaces.map((surface) => (
                        <SelectItem key={surface.id} value={surface.id}>
                          {surface.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-wrap gap-3 pt-1">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCreateRoomFromContext}
                    disabled={!selectedGymSlug}
                  >
                    Start {providerLabel} room
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                  {selectedGym ? <Badge variant="secondary">{selectedGym.name}</Badge> : null}
                  {selectedWall ? <Badge variant="outline">{selectedWall.name}</Badge> : null}
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-white/88 shadow-xl shadow-slate-900/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <Compass className="h-5 w-5" />
                  Browse climbs
                </CardTitle>
                <CardDescription>
                  Search the current {providerLabel} catalog, sort the results, and inspect the
                  full climb detail on the right.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
                  <Input
                    value={rawQuery}
                    placeholder={`Search ${providerLabel} climbs`}
                    onChange={(event) => updateSearchState({ q: event.target.value })}
                    disabled={!accessLoaded || !selectedGymSlug}
                  />
                  <SortSelector
                    sort={sort}
                    onSortChange={(nextSort: ClimbSort) =>
                      updateSearchState({ sort: nextSort })
                    }
                    className="justify-between"
                  />
                </div>

                {!accessLoaded ? (
                  <div className="rounded-2xl border border-dashed bg-muted/15 p-6 text-sm text-muted-foreground">
                    Load the provider catalog first to choose a gym and start browsing.
                  </div>
                ) : catalogLoading ? (
                  <div className="rounded-2xl border border-dashed bg-muted/15 p-6 text-sm text-muted-foreground">
                    Loading climbs...
                  </div>
                ) : climbs.length === 0 ? (
                  <div className="rounded-2xl border border-dashed bg-muted/15 p-6 text-sm text-muted-foreground">
                    No climbs match the current search and gym selection.
                  </div>
                ) : (
                  <div className="grid gap-3">
                    {climbs.map((climb) => {
                      const providerMetaLine = formatProviderMetaLine(climb);
                      const isPlanned = plannedClimbs.some((item) => item.id === climb.id);
                      return (
                        <button
                          key={climb.id}
                          type="button"
                          onClick={() => updateSearchState({ climb: climb.id })}
                          className={`rounded-2xl border p-4 text-left transition-colors ${
                            selectedClimb?.id === climb.id
                              ? "border-primary bg-primary/5"
                              : "bg-card hover:bg-muted/40"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="font-medium">{climb.name}</p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {climb.setter_name || "Unknown setter"}
                              </p>
                              {providerMetaLine ? (
                                <p className="mt-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground/80">
                                  {providerMetaLine}
                                </p>
                              ) : null}
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <Badge variant="secondary">
                                {climb.primary_grade || "Unknown"}
                              </Badge>
                              {climb.secondary_grade ? (
                                <Badge variant="outline">{climb.secondary_grade}</Badge>
                              ) : null}
                              {isPlanned ? <Badge variant="outline">In plan</Badge> : null}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                <div className="flex items-center justify-between gap-2 pt-2">
                  <Button
                    variant="outline"
                    onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                    disabled={currentPage === 1 || catalogLoading}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">Page {currentPage}</span>
                  <Button
                    variant="outline"
                    onClick={() => setCurrentPage((page) => page + 1)}
                    disabled={!hasMore || catalogLoading}
                  >
                    Next
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6">
            <Card className="border-0 bg-white/88 shadow-xl shadow-slate-900/10 backdrop-blur">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <Mountain className="h-5 w-5" />
                  Current context
                </CardTitle>
                <CardDescription>
                  Carry the current gym and wall context into room creation once you are ready to
                  host a shared session.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="flex flex-wrap gap-2">
                  {selectedGym ? <Badge variant="secondary">{selectedGym.name}</Badge> : null}
                  {selectedWall ? <Badge variant="outline">{selectedWall.name}</Badge> : null}
                  {resolvedProviderId === "crux" ? (
                    <Badge variant="outline">Gym catalog</Badge>
                  ) : null}
                  <Badge variant="outline">{plannedClimbs.length} climbs in plan</Badge>
                  {accessLoaded ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => void handleLoadCatalog()}
                      className="ml-auto"
                    >
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Refresh provider data
                    </Button>
                  ) : null}
                </div>
                <div className="grid gap-3">
                  <Input
                    value={planTitle}
                    onChange={(event) => setPlanTitle(event.target.value)}
                    placeholder="Plan title"
                    disabled={!selectedGym}
                  />
                  <textarea
                    value={planNotes}
                    onChange={(event) => setPlanNotes(event.target.value)}
                    placeholder="Optional planning notes"
                    className="min-h-24 rounded-xl border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    disabled={!selectedGym}
                  />
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleCreateRoomFromContext}
                      disabled={!selectedGym}
                    >
                      Start room from plan
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void handleSharePlan()}
                      disabled={!selectedGym || plannedClimbs.length === 0 || sharingPlan}
                    >
                      <Share2 className="mr-2 h-4 w-4" />
                      {sharingPlan ? "Creating plan..." : "Create shareable plan"}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-white/88 shadow-xl shadow-slate-900/10 backdrop-blur">
              <CardHeader>
                <CardTitle>Climb detail</CardTitle>
                <CardDescription>
                  The detail view keeps provider-specific labels intact so you can decide whether
                  the climb is worth carrying into a shared session.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                {selectedClimb ? (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant={
                        plannedClimbs.some((climb) => climb.id === selectedClimb.id)
                          ? "secondary"
                          : "outline"
                      }
                      onClick={() => togglePlannedClimb(selectedClimb)}
                    >
                      {plannedClimbs.some((climb) => climb.id === selectedClimb.id)
                        ? "Remove from plan"
                        : "Add to plan"}
                    </Button>
                    {selectedClimb.primary_grade ? (
                      <Badge variant="secondary">{selectedClimb.primary_grade}</Badge>
                    ) : null}
                  </div>
                ) : null}
                {detailLoading ? (
                  <div className="rounded-2xl border border-dashed bg-muted/15 p-6 text-sm text-muted-foreground">
                    Loading climb detail...
                  </div>
                ) : (
                  <RoomProblemView
                    climb={selectedClimb}
                    providerId={resolvedProviderId}
                    hasResults={climbs.length > 0}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}
