import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { api } from "./api";

class MockEventSource {
  static instances: MockEventSource[] = [];
  onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
  private listeners = new Map<string, Set<EventListener>>();
  readonly url: string;
  readonly options?: EventSourceInit;

  constructor(url: string, options?: EventSourceInit) {
    this.url = url;
    this.options = options;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const eventListener =
      typeof listener === "function"
        ? listener
        : listener.handleEvent.bind(listener);
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)?.add(eventListener);
  }

  removeEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject
  ) {
    const eventListener =
      typeof listener === "function"
        ? listener
        : listener.handleEvent.bind(listener);
    this.listeners.get(type)?.delete(eventListener);
  }

  close() {}
}

vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

vi.mock("./api", () => ({
  api: {
    getBoards: vi.fn(),
    getPaginatedClimbs: vi.fn(),
    getImageUrl: vi.fn((filename: string) => `/api/images/${filename}`),
    createRoom: vi.fn(),
    joinRoom: vi.fn(),
    getRoom: vi.fn(),
    getRoomEventsUrl: vi.fn((slug: string) => `/api/rooms/${slug}/events`),
    connectRoomProvider: vi.fn(),
    getRoomCatalogSurfaces: vi.fn(),
    setRoomSurface: vi.fn(),
    getRoomCatalogClimbs: vi.fn(),
    getRoomCatalogClimb: vi.fn(),
    toggleRoomVote: vi.fn(),
    addRoomQueueEntry: vi.fn(),
    reorderRoomQueue: vi.fn(),
    updateRoomQueueEntry: vi.fn(),
    deleteRoomQueueEntry: vi.fn(),
    clearRoomVotes: vi.fn(),
    closeRoom: vi.fn(),
    removeRoomParticipant: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("App routes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    MockEventSource.instances = [];
  });

  it("supports direct board route loads with URL-backed filters", async () => {
    mockedApi.getBoards.mockResolvedValue([
      { id: 14, name: "Original 7 x 10", kilter_name: "Kilter Board Original" },
    ]);
    mockedApi.getPaginatedClimbs.mockResolvedValue({
      climbs: [
        {
          uuid: "uuid-1",
          climb_name: "Sample Problem",
          description: "A direct-link test climb",
          frames: "frames",
          grades: {
            "45": {
              boulder: "7a/V6",
              route: "5.12d",
            },
          },
          setter_name: "setter-a",
          image_filenames: ["test-a.png"],
          product_size_id: 14,
          ascends: 12,
          created_at: "2026-01-01 00:00:00.000000",
        },
      ],
      has_more: false,
      page_size: 10,
    });

    render(
      <MemoryRouter
        initialEntries={[
          "/boards/14?angle=45&q=Sample&setter=setter-a&sort=newest&climb=uuid-1",
        ]}
      >
        <App />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(mockedApi.getPaginatedClimbs).toHaveBeenCalledWith(
        expect.objectContaining({
          boardId: "14",
          angle: 45,
          name: "Sample",
          setter: "setter-a",
          sort: "newest",
        })
      )
    );

    expect(
      await screen.findByRole("heading", { name: "Sample Problem" })
    ).toBeInTheDocument();
    expect(screen.getAllByText("Original 7 x 10").length).toBeGreaterThan(0);
    expect(screen.getByText("A direct-link test climb")).toBeInTheDocument();
  });

  it("supports direct collaborative room route loads", async () => {
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      slug: "session-1",
      status: "open",
      provider_id: "kilter",
      version: 3,
      surface: {
        id: "14",
        kind: "board",
        name: "Kilter Board Original",
        meta: {
          angle: "40",
          board_id: "14",
        },
      },
      connection: {
        provider_id: "kilter",
        connected: true,
      },
      participants: [
        {
          id: 1,
          display_name: "Host",
          role: "host",
          is_online: true,
        },
        {
          id: 2,
          display_name: "Guest",
          role: "participant",
          is_online: true,
        },
      ],
      queue: [],
      vote_counts: {
        "kilter:14:uuid-1": 2,
      },
      my_votes: ["kilter:14:uuid-1"],
      can_manage: true,
      display_name: "Host",
    });
    mockedApi.getRoomCatalogClimbs.mockResolvedValue({
      climbs: [
        {
          id: "kilter:14:uuid-1",
          external_id: "uuid-1",
          provider_id: "kilter",
          surface_id: "14",
          name: "Shared Project",
          description: "Vote on this one",
          setter_name: "Setter A",
          primary_grade: "V6",
          secondary_grade: "5.12d",
          created_at: "2026-02-01T00:00:00Z",
          popularity: 14,
          media: [
            {
              url: "/api/images/test-a.png",
              kind: "image",
            },
          ],
          meta: {
            board_id: "14",
          },
        },
      ],
      has_more: false,
      page_size: 12,
      vote_counts: {
        "kilter:14:uuid-1": 2,
      },
      my_votes: ["kilter:14:uuid-1"],
    });

    render(
      <MemoryRouter
        initialEntries={["/rooms/session-1?q=Shared&sort=popular&climb=kilter:14:uuid-1"]}
      >
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole("heading", { name: "Room session-1" })
    ).toBeInTheDocument();

    await waitFor(() =>
      expect(mockedApi.getRoomCatalogClimbs).toHaveBeenCalledWith(
        "session-1",
        expect.objectContaining({
          q: "Shared",
          sort: "popular",
        })
      )
    );

    expect((await screen.findAllByText("Shared Project")).length).toBeGreaterThan(0);
    expect(screen.getByText("Vote on this one")).toBeInTheDocument();
    expect(screen.getByText("Participants")).toBeInTheDocument();
    expect(screen.getByText(/join\/session-1/)).toBeInTheDocument();
    expect(MockEventSource.instances[0]?.url).toBe("/api/rooms/session-1/events");
  });
});
