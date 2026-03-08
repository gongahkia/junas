import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { api } from "./api";
import type { RoomSnapshot } from "./types";

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
    addRoomFinalist: vi.fn(),
    reorderRoomFinalists: vi.fn(),
    deleteRoomFinalist: vi.fn(),
    pickRandomRoomClimb: vi.fn(),
    promoteRoomQueueClimb: vi.fn(),
    reorderRoomQueue: vi.fn(),
    updateRoomQueueEntry: vi.fn(),
    deleteRoomQueueEntry: vi.fn(),
    clearRoomVotes: vi.fn(),
    closeRoom: vi.fn(),
    removeRoomParticipant: vi.fn(),
    updateMyParticipantStatus: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const buildRoomSnapshot = (slug: string): RoomSnapshot => ({
  slug,
  status: "open" as const,
  provider_id: "kilter" as const,
  version: 1,
  connection: {
    provider_id: "kilter" as const,
    connected: false,
  },
  participants: [
    {
      id: 1,
      display_name: "Host",
      role: "host",
      status: "watching" as const,
      is_online: true,
    },
  ],
  finalists: [],
  queue: [],
  vote_counts: {},
  my_votes: [],
  can_manage: true,
  display_name: "Host",
});

describe("App routes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    MockEventSource.instances = [];
    window.localStorage.clear();
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
      ...buildRoomSnapshot("session-1"),
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
          status: "watching" as const,
          is_online: true,
        },
        {
          id: 2,
          display_name: "Guest",
          role: "participant",
          status: "ready" as const,
          is_online: true,
        },
      ],
      finalists: [
        {
          id: 9,
          position: 1,
          added_by: "Host",
          climb: {
            id: "kilter:14:uuid-1",
            external_id: "uuid-1",
            provider_id: "kilter",
            surface_id: "14",
            name: "Shared Project",
            setter_name: "Setter A",
            primary_grade: "V6",
          },
        },
      ],
      queue: [
        {
          id: 4,
          status: "current" as const,
          position: 1,
          added_by: "Host",
          climb: {
            id: "kilter:14:uuid-1",
            external_id: "uuid-1",
            provider_id: "kilter",
            surface_id: "14",
            name: "Shared Project",
            setter_name: "Setter A",
            primary_grade: "V6",
          },
        },
      ],
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
    expect(screen.getByText("Finalists")).toBeInTheDocument();
    expect(screen.getAllByText("ready").length).toBeGreaterThan(0);
    expect(screen.getByText(/join\/session-1/)).toBeInTheDocument();
    expect(MockEventSource.instances[0]?.url).toBe("/api/rooms/session-1/events");
    expect(mockedApi.getBoards).not.toHaveBeenCalled();
  });

  it("supports host decision actions inside a room", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("host-room"),
      version: 2,
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
        },
      ],
      has_more: false,
      page_size: 12,
      vote_counts: {
        "kilter:14:uuid-1": 2,
      },
      my_votes: ["kilter:14:uuid-1"],
    });
    mockedApi.addRoomFinalist.mockResolvedValue(undefined);
    mockedApi.promoteRoomQueueClimb.mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={["/rooms/host-room?climb=kilter:14:uuid-1"]}>
        <App />
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Shared Project")).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Add finalist" }));
    await waitFor(() =>
      expect(mockedApi.addRoomFinalist).toHaveBeenCalledWith(
        "host-room",
        "kilter:14:uuid-1"
      )
    );

    await user.click(screen.getByRole("button", { name: "Promote to current" }));
    await waitFor(() =>
      expect(mockedApi.promoteRoomQueueClimb).toHaveBeenCalledWith(
        "host-room",
        "kilter:14:uuid-1",
        "current"
      )
    );
  });

  it("shows the backend provider-connect error in the room UI", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("connect-room"),
      provider_id: "crux",
      connection: {
        provider_id: "crux",
        connected: false,
      },
    });
    mockedApi.connectRoomProvider.mockRejectedValue({
      response: {
        status: 500,
        data: {
          error: "KILTER_TOGETHER_ENCRYPTION_KEY is required",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/rooms/connect-room"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Room connect-room" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Crux API token"), "demo-token");
    await user.click(screen.getByRole("button", { name: "Connect provider" }));

    expect(
      await screen.findByText("KILTER_TOGETHER_ENCRYPTION_KEY is required")
    ).toBeInTheDocument();
  });

  it("supports creating a room from the room-first flow", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.createRoom.mockResolvedValue(buildRoomSnapshot("created-room"));
    mockedApi.getRoom.mockResolvedValue(buildRoomSnapshot("created-room"));

    render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText("Host display name"), "Host");
    await user.click(screen.getByRole("button", { name: "Create room" }));

    await waitFor(() =>
      expect(mockedApi.createRoom).toHaveBeenCalledWith({
        providerId: "kilter",
        displayName: "Host",
      })
    );

    expect(
      await screen.findByRole("heading", { name: "Room created-room" })
    ).toBeInTheDocument();
  });

  it("supports joining a room from an invite route", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.joinRoom.mockResolvedValue(buildRoomSnapshot("join-room"));
    mockedApi.getRoom.mockResolvedValue(buildRoomSnapshot("join-room"));

    render(
      <MemoryRouter initialEntries={["/join/join-room"]}>
        <App />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText("Display name"), "Guest");
    await user.click(screen.getByRole("button", { name: "Join room" }));

    await waitFor(() =>
      expect(mockedApi.joinRoom).toHaveBeenCalledWith("join-room", "Guest")
    );

    expect(
      await screen.findByRole("heading", { name: "Room join-room" })
    ).toBeInTheDocument();
  });

  it("shows recent rooms and resume solo browse from local prefs", async () => {
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        savedDisplayName: "Guest",
        lastProviderId: "kilter",
        lastKilter: {
          boardId: "14",
          angle: 45,
        },
        lastCrux: {
          gymSlug: "",
          wallId: "",
        },
        recentRooms: [
          {
            slug: "saved-room",
            providerId: "crux",
            surfaceName: "Main Wall",
            lastVisitedAt: "2026-03-08T09:00:00.000Z",
          },
        ],
        soloResume: {
          boardId: "14",
          angle: 45,
          q: "Compression",
          setter: "setter-a",
          sort: "newest",
          climb: "uuid-1",
        },
        intro: {
          version: 1,
          landingDismissed: true,
          soloDismissed: true,
        },
        onboarding: {
          version: 1,
          dismissed: false,
          hostCompleted: false,
          guestCompleted: false,
        },
      })
    );
    mockedApi.getBoards.mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Recent rooms")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Resume solo browse/i })).toHaveAttribute(
      "href",
      "/solo/boards/14?angle=45&sort=newest&q=Compression&setter=setter-a&climb=uuid-1"
    );
    expect(screen.getByRole("link", { name: /Room saved-room/i })).toHaveAttribute(
      "href",
      "/rooms/saved-room"
    );
  });

  it("shows a first-visit intro before onboarding and lets the user replay onboarding", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);

    const view = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("button", { name: "Start exploring" })).toBeInTheDocument();
    expect(screen.queryByText("First-time guide")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start exploring" }));
    expect(await screen.findByText("First-time guide")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("First-time guide")).not.toBeInTheDocument();

    view.unmount();

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.queryByRole("button", { name: "Start exploring" })).not.toBeInTheDocument();
    expect(screen.queryByText("First-time guide")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Help/i }));
    expect(await screen.findByText("First-time guide")).toBeInTheDocument();
  });

  it("shows the solo intro dialog only on the first solo visit", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);

    const view = render(
      <MemoryRouter initialEntries={["/solo"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Choose a board")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Open solo browse" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open solo browse" }));
    expect(screen.queryByRole("button", { name: "Open solo browse" })).not.toBeInTheDocument();

    view.unmount();

    render(
      <MemoryRouter initialEntries={["/solo"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Choose a board")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open solo browse" })).not.toBeInTheDocument();
  });

  it("shows role-specific onboarding on host and guest entry pages", async () => {
    mockedApi.getBoards.mockResolvedValue([]);

    const { unmount } = render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Host flow: create first, connect second")).toBeInTheDocument();

    unmount();

    render(
      <MemoryRouter initialEntries={["/join/join-room"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Guest flow: join fast, then vote")).toBeInTheDocument();
  });

  it("prefills room creation from saved browser prefs", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        savedDisplayName: "Alex",
        lastProviderId: "crux",
      })
    );
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.createRoom.mockResolvedValue({
      ...buildRoomSnapshot("created-room"),
      provider_id: "crux",
      connection: {
        provider_id: "crux",
        connected: false,
      },
    });
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("created-room"),
      provider_id: "crux",
      connection: {
        provider_id: "crux",
        connected: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByLabelText("Host display name")).toHaveValue("Alex");

    await user.click(screen.getByRole("button", { name: "Create room" }));

    await waitFor(() =>
      expect(mockedApi.createRoom).toHaveBeenCalledWith({
        providerId: "crux",
        displayName: "Alex",
      })
    );
  });

  it("redirects expired room auth back to join with the saved display name", async () => {
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockRejectedValue({
      response: {
        status: 401,
      },
    });
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        savedDisplayName: "Guest",
      })
    );

    render(
      <MemoryRouter initialEntries={["/rooms/session-1"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByLabelText("Display name")).toHaveValue("Guest");
  });
});
