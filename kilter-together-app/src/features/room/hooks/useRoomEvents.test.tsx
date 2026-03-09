import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  parseRoomEventPayload,
  shouldRefreshCatalogOnly,
  shouldRefreshRoomAndCatalog,
  shouldRefreshRoomOnly,
} from "@/features/room/room-events";
import { useRoomEvents } from "@/features/room/hooks/useRoomEvents";

vi.mock("@/api", () => ({
  api: {
    getRoomEventsUrl: (slug: string) => `/api/rooms/${slug}/events`,
  },
}));

class MockEventSource {
  static instances: MockEventSource[] = [];

  onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
  private listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>();
  readonly url: string;
  readonly options?: EventSourceInit;

  constructor(url: string, options?: EventSourceInit) {
    this.url = url;
    this.options = options;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  close() {}

  emit(type: string, data: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data } as MessageEvent<string>);
    }
  }
}

function UseRoomEventsHarness(props: {
  slug: string;
  roomStatus: "open" | "closed";
  refreshRoom?: () => Promise<void>;
  refreshCatalog?: () => Promise<void>;
  refreshRoomAndCatalog?: () => Promise<void>;
}) {
  useRoomEvents({
    slug: props.slug,
    roomStatus: props.roomStatus,
    refreshRoom: props.refreshRoom ?? (async () => {}),
    refreshCatalog: props.refreshCatalog ?? (async () => {}),
    refreshRoomAndCatalog: props.refreshRoomAndCatalog ?? (async () => {}),
  });

  return null;
}

describe("room event helpers", () => {
  it("parses valid SSE payloads and routes catalog-only events narrowly", () => {
    const payload = parseRoomEventPayload(
      JSON.stringify({ type: "catalog.updated", resources: ["catalog"] })
    );

    expect(payload).toMatchObject({
      type: "catalog.updated",
      resources: ["catalog"],
    });
    expect(shouldRefreshCatalogOnly(payload)).toBe(true);
    expect(shouldRefreshRoomOnly(payload)).toBe(false);
    expect(shouldRefreshRoomAndCatalog(payload)).toBe(true);
  });

  it("treats room resources as snapshot-only refreshes", () => {
    const payload = parseRoomEventPayload(
      JSON.stringify({ type: "queue.updated", resources: ["queue", "votes"] })
    );

    expect(shouldRefreshRoomOnly(payload)).toBe(true);
    expect(shouldRefreshCatalogOnly(payload)).toBe(false);
  });

  it("falls back safely when the event payload is invalid", () => {
    expect(parseRoomEventPayload("{invalid")).toBeNull();
    expect(shouldRefreshCatalogOnly(null)).toBe(false);
    expect(shouldRefreshRoomOnly(null)).toBe(false);
    expect(shouldRefreshRoomAndCatalog(null)).toBe(true);
  });
});

describe("useRoomEvents", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("opens a single event stream and refreshes only the catalog for catalog-only updates", async () => {
    const refreshRoom = vi.fn().mockResolvedValue(undefined);
    const refreshCatalog = vi.fn().mockResolvedValue(undefined);
    const refreshRoomAndCatalog = vi.fn().mockResolvedValue(undefined);

    render(
      <UseRoomEventsHarness
        slug="session-1"
        roomStatus="open"
        refreshRoom={refreshRoom}
        refreshCatalog={refreshCatalog}
        refreshRoomAndCatalog={refreshRoomAndCatalog}
      />
    );

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0]?.url).toBe("/api/rooms/session-1/events");

    MockEventSource.instances[0]?.emit(
      "room",
      JSON.stringify({ type: "catalog.updated", resources: ["catalog"] })
    );

    await waitFor(() => expect(refreshCatalog).toHaveBeenCalledTimes(1));
    expect(refreshRoom).not.toHaveBeenCalled();
    expect(refreshRoomAndCatalog).not.toHaveBeenCalled();
  });

  it("refreshes the full room state when surface-scoped updates arrive", async () => {
    const refreshRoom = vi.fn().mockResolvedValue(undefined);
    const refreshCatalog = vi.fn().mockResolvedValue(undefined);
    const refreshRoomAndCatalog = vi.fn().mockResolvedValue(undefined);

    render(
      <UseRoomEventsHarness
        slug="session-2"
        roomStatus="open"
        refreshRoom={refreshRoom}
        refreshCatalog={refreshCatalog}
        refreshRoomAndCatalog={refreshRoomAndCatalog}
      />
    );

    MockEventSource.instances[0]?.emit(
      "room",
      JSON.stringify({ type: "surface.updated", resources: ["surface", "catalog"] })
    );

    await waitFor(() => expect(refreshRoomAndCatalog).toHaveBeenCalledTimes(1));
    expect(refreshRoom).not.toHaveBeenCalled();
    expect(refreshCatalog).not.toHaveBeenCalled();
  });

  it("reconnects with backoff after SSE errors", async () => {
    vi.useFakeTimers();

    render(<UseRoomEventsHarness slug="session-3" roomStatus="open" />);
    expect(MockEventSource.instances).toHaveLength(1);

    const firstSource = MockEventSource.instances[0];
    firstSource?.onerror?.call(firstSource as unknown as EventSource, new Event("error"));
    await vi.advanceTimersByTimeAsync(1000);

    expect(MockEventSource.instances).toHaveLength(2);
  });
});
