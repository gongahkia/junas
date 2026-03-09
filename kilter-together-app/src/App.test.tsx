import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

  emit(type: string, event: Event = new Event(type)) {
    this.listeners.get(type)?.forEach((listener) => {
      listener(event);
    });
  }
}

vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false;
}
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => {};
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => {};
}
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = () => {};
}

vi.mock("./api", () => ({
  api: {
    getBoards: vi.fn(),
    getPaginatedClimbs: vi.fn(),
    getImageUrl: vi.fn((filename: string) => {
      const baseName = filename.includes("/") ? filename.split("/").pop() : filename;
      return `/api/images/${baseName}`;
    }),
    createRoom: vi.fn(),
    joinRoom: vi.fn(),
    getRoom: vi.fn(),
    updateRoom: vi.fn(),
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
const DEFAULT_DISMISSED_GUIDES_PREFS = {
  intro: {
    version: 1,
    landingDismissed: true,
    soloDismissed: true,
  },
  onboarding: {
    version: 1,
    dismissed: true,
    hostCompleted: false,
    guestCompleted: false,
    hostConnectedProvider: false,
    hostSelectedSurface: false,
    guestJoinedRoom: false,
    guestParticipated: false,
  },
};

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
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify(DEFAULT_DISMISSED_GUIDES_PREFS)
    );
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

  it("shows the global community bottom bar", async () => {
    mockedApi.getBoards.mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/for the Climbing Community by/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gabriel Ong" })).toHaveAttribute(
      "href",
      "https://gabrielongzm.com"
    );
    expect(screen.getByRole("img", { name: /love/i })).toHaveAttribute(
      "src",
      "/heart.png"
    );
  });

  it("opens the About page from the landing header", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    await user.click(await screen.findByRole("link", { name: "About" }));

    expect(await screen.findByText(/Hi, I'm/i)).toBeInTheDocument();
    expect(
      screen.getByText(/too shy to ask if they can alternate sets/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gabriel" })).toHaveAttribute(
      "href",
      "https://gabrielongzm.com"
    );
    expect(screen.getByRole("link", { name: /here/i })).toHaveAttribute(
      "href",
      "https://github.com/gongahkia/kilter-together"
    );
  });

  it("persists browser-local settings from the settings page", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        savedDisplayName: "Alex",
        recentRooms: [
          {
            slug: "session-1",
            providerId: "kilter",
            lastVisitedAt: "2026-03-09T10:00:00.000Z",
          },
        ],
        ...DEFAULT_DISMISSED_GUIDES_PREFS,
      })
    );

    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Customize this browser")).toBeInTheDocument();

    await user.click(
      screen.getByRole("checkbox", { name: /Show cursor encouragement words/i })
    );
    await user.click(screen.getByRole("checkbox", { name: /Save recent rooms/i }));
    await user.clear(screen.getByLabelText("Preferred display name"));
    await user.type(screen.getByLabelText("Preferred display name"), "Gabriel");

    const storedPrefs = JSON.parse(
      window.localStorage.getItem("kilter-together:user-prefs:v1") || "{}"
    );
    expect(storedPrefs.settings.clickCheersEnabled).toBe(false);
    expect(storedPrefs.settings.recentRoomsEnabled).toBe(false);
    expect(storedPrefs.recentRooms).toEqual([]);
    expect(storedPrefs.savedDisplayName).toBe("Gabriel");
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

  it("keeps a single room event stream and avoids refetching surfaces on every room event", async () => {
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("session-setup"),
      connection: {
        provider_id: "kilter",
        connected: true,
      },
    });
    mockedApi.getRoomCatalogSurfaces.mockResolvedValue([
      {
        id: "14",
        kind: "board",
        name: "Kilter Board Original",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/rooms/session-setup"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole("heading", { name: "Room session-setup" })
    ).toBeInTheDocument();

    await waitFor(() =>
      expect(mockedApi.getRoomCatalogSurfaces).toHaveBeenCalledTimes(1)
    );

    MockEventSource.instances[0]?.emit("room");

    await waitFor(() => expect(mockedApi.getRoom).toHaveBeenCalledTimes(2));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(mockedApi.getRoomCatalogSurfaces).toHaveBeenCalledTimes(1);
  });

  it("lets the host set the room name from the room header", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue(buildRoomSnapshot("rename-room"));
    mockedApi.updateRoom.mockResolvedValue({
      ...buildRoomSnapshot("rename-room"),
      room_name: "After Work Session",
    });

    render(
      <MemoryRouter initialEntries={["/rooms/rename-room"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole("heading", { name: "Room rename-room" })
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Room name"), "After Work Session");
    await user.click(screen.getByRole("button", { name: "Set room name" }));

    await waitFor(() =>
      expect(mockedApi.updateRoom).toHaveBeenCalledWith("rename-room", {
        roomName: "After Work Session",
      })
    );

    expect(
      await screen.findByRole("heading", { name: "After Work Session" })
    ).toBeInTheDocument();
  });

  it("replays the room onboarding even after the host has finished setup", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("ready-room"),
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
      vote_counts: {},
      my_votes: [],
    });

    render(
      <MemoryRouter initialEntries={["/rooms/ready-room"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole("heading", { name: "Room ready-room" })
    ).toBeInTheDocument();
    expect(screen.queryByText("First-time guide")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Help" }));

    expect(await screen.findByText("First-time guide")).toBeInTheDocument();
    expect(screen.getByText(/Provider connected\. Move on to the shared surface selection\./i)).toBeInTheDocument();
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

  it("reorders queue entries through the drag handle instead of up and down buttons", async () => {
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("drag-room"),
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
      queue: [
        {
          id: 4,
          status: "queued" as const,
          position: 1,
          added_by: "Host",
          climb: {
            id: "kilter:14:uuid-1",
            external_id: "uuid-1",
            provider_id: "kilter",
            surface_id: "14",
            name: "First Project",
            setter_name: "Setter A",
            primary_grade: "V6",
          },
        },
        {
          id: 5,
          status: "next" as const,
          position: 2,
          added_by: "Host",
          climb: {
            id: "kilter:14:uuid-2",
            external_id: "uuid-2",
            provider_id: "kilter",
            surface_id: "14",
            name: "Second Project",
            setter_name: "Setter B",
            primary_grade: "V5",
          },
        },
      ],
    });
    mockedApi.getRoomCatalogClimbs.mockResolvedValue({
      climbs: [],
      has_more: false,
      page_size: 12,
      vote_counts: {},
      my_votes: [],
    });
    mockedApi.reorderRoomQueue.mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={["/rooms/drag-room"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Queue")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Up" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Down" })).not.toBeInTheDocument();

    const dragHandle = screen.getByRole("button", {
      name: "Drag First Project in queue",
    });
    const dropTarget = screen.getByRole("group", {
      name: "Queue entry Second Project",
    });
    const dataTransfer = {
      effectAllowed: "",
      dropEffect: "",
      setData: vi.fn(),
      getData: vi.fn(),
    } as unknown as DataTransfer;

    fireEvent.dragStart(dragHandle, { dataTransfer });
    fireEvent.dragOver(dropTarget, { dataTransfer });
    fireEvent.drop(dropTarget, { dataTransfer });
    fireEvent.dragEnd(dragHandle, { dataTransfer });

    await waitFor(() =>
      expect(mockedApi.reorderRoomQueue).toHaveBeenCalledWith("drag-room", [5, 4])
    );
    await waitFor(() => expect(mockedApi.getRoom).toHaveBeenCalledTimes(2));
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

  it("lets Crux hosts edit the shared gym and wall after the first selection", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("crux-room"),
      provider_id: "crux",
      connection: {
        provider_id: "crux",
        connected: true,
      },
      surface: {
        id: "wall-alpha",
        kind: "wall",
        name: "Alpha Wall",
        parent_id: "gym-a",
        meta: {
          gym_slug: "gym-a",
        },
      },
    });
    mockedApi.getRoomCatalogClimbs.mockResolvedValue({
      climbs: [],
      has_more: false,
      page_size: 12,
      vote_counts: {},
      my_votes: [],
    });
    mockedApi.getRoomCatalogSurfaces.mockImplementation(
      async (_slug: string, parentId?: string) => {
        if (!parentId) {
          return [
            { id: "gym-a", kind: "gym", name: "Alpha Gym" },
            { id: "gym-b", kind: "gym", name: "Beta Gym" },
          ];
        }

        if (parentId === "gym-a") {
          return [{ id: "wall-alpha", kind: "wall", name: "Alpha Wall" }];
        }

        return [
          { id: "wall-beta", kind: "wall", name: "Beta Cave" },
          { id: "wall-gamma", kind: "wall", name: "Moon Board" },
        ];
      }
    );
    mockedApi.setRoomSurface.mockResolvedValue({
      id: "wall-gamma",
      kind: "wall",
      name: "Moon Board",
      parent_id: "gym-b",
      meta: {
        gym_slug: "gym-b",
      },
    });

    render(
      <MemoryRouter initialEntries={["/rooms/crux-room"]}>
        <App />
      </MemoryRouter>
    );

    const editTitle = await screen.findByText("Edit the shared climbing surface");
    const editCard = editTitle.closest("[data-slot='card']");
    expect(editCard).not.toBeNull();

    const [gymSelect, wallSelect] = within(editCard as HTMLElement).getAllByRole("combobox");

    await user.click(gymSelect);
    await user.click(await screen.findByRole("option", { name: "Beta Gym" }));

    await waitFor(() =>
      expect(mockedApi.getRoomCatalogSurfaces).toHaveBeenCalledWith("crux-room", "gym-b")
    );

    await user.click(wallSelect);
    await user.click(await screen.findByRole("option", { name: "Moon Board" }));
    await user.click(within(editCard as HTMLElement).getByRole("button", { name: "Update wall" }));

    await waitFor(() =>
      expect(mockedApi.setRoomSurface).toHaveBeenCalledWith("crux-room", {
        surfaceId: "wall-gamma",
        context: {
          gym_slug: "gym-b",
          parent_id: "gym-b",
        },
      })
    );
  });

  it("supports creating a room from the room-first flow", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.createRoom.mockResolvedValue({
      ...buildRoomSnapshot("created-room"),
      room_name: "Monday Session",
    });
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("created-room"),
      room_name: "Monday Session",
    });

    render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText("Room name"), "Monday Session");
    await user.type(screen.getByLabelText("Host display name"), "Host");
    await user.type(screen.getByLabelText("Kilter username"), "host@example.com");
    await user.type(screen.getByLabelText("Kilter password"), "secret-pass");
    await user.click(screen.getByRole("button", { name: "Authenticate and create room" }));

    await waitFor(() =>
      expect(mockedApi.createRoom).toHaveBeenCalledWith({
        providerId: "kilter",
        roomName: "Monday Session",
        displayName: "Host",
        secret: {
          username: "host@example.com",
          password: "secret-pass",
        },
      })
    );

    expect(
      await screen.findByRole("heading", { name: "Monday Session" })
    ).toBeInTheDocument();
  });

  it("shows a useful fallback when room creation hits a blank proxy 500", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.createRoom.mockRejectedValue({
      message: "Request failed with status code 500",
      response: {
        status: 500,
        data: "",
      },
    });

    render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText("Host display name"), "Host");
    await user.type(screen.getByLabelText("Kilter username"), "host@example.com");
    await user.type(screen.getByLabelText("Kilter password"), "secret-pass");
    await user.click(screen.getByRole("button", { name: "Authenticate and create room" }));

    expect(
      await screen.findByText(
        "Unable to create the room. Make sure the API server is running and check the backend logs."
      )
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

  it("shows recent rooms on landing and resume solo browse on the solo page", async () => {
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
          dismissed: true,
          hostCompleted: false,
          guestCompleted: false,
        },
      })
    );
    mockedApi.getBoards.mockResolvedValue([]);

    const landingView = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Recent rooms")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Resume solo browse/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Room saved-room" })).toHaveAttribute(
      "href",
      "/rooms/saved-room"
    );

    landingView.unmount();

    render(
      <MemoryRouter initialEntries={["/solo"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole("link", { name: /Resume solo browse/i })
    ).toHaveAttribute(
      "href",
      "/solo/boards/14?angle=45&sort=newest&q=Compression&setter=setter-a&climb=uuid-1"
    );
  });

  it("lets the user pin and remove recent rooms", async () => {
    const user = userEvent.setup();
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
            slug: "older-room",
            providerId: "kilter",
            roomName: "Older Session",
            lastVisitedAt: "2026-03-08T09:00:00.000Z",
          },
          {
            slug: "newer-room",
            providerId: "crux",
            roomName: "Newer Session",
            lastVisitedAt: "2026-03-08T10:00:00.000Z",
          },
        ],
        intro: {
          version: 1,
          landingDismissed: true,
          soloDismissed: true,
        },
        onboarding: {
          version: 1,
          dismissed: true,
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

    await user.click(screen.getByRole("button", { name: "Pin Older Session" }));

    const storedAfterPin = JSON.parse(
      window.localStorage.getItem("kilter-together:user-prefs:v1") || "{}"
    );
    expect(storedAfterPin.recentRooms[0]).toMatchObject({
      slug: "older-room",
      pinned: true,
    });

    const recentRoomsCard = screen.getByText("Recent rooms").closest("[data-slot='card']");
    expect(recentRoomsCard).not.toBeNull();
    const openLinks = within(recentRoomsCard as HTMLElement).getAllByRole("link", {
      name: /Open /i,
    });
    expect(openLinks[0]).toHaveAttribute("href", "/rooms/older-room");

    await user.click(
      screen.getByRole("button", {
        name: "Remove Newer Session from recent rooms",
      })
    );

    const storedAfterRemove = JSON.parse(
      window.localStorage.getItem("kilter-together:user-prefs:v1") || "{}"
    );
    expect(storedAfterRemove.recentRooms).toHaveLength(1);
    expect(storedAfterRemove.recentRooms[0]).toMatchObject({
      slug: "older-room",
      pinned: true,
    });
    expect(screen.queryByText("Newer Session")).not.toBeInTheDocument();
  });

  it("shows three recent rooms inline and caps the expanded list at nine", async () => {
    const user = userEvent.setup();
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
        recentRooms: Array.from({ length: 10 }, (_, index) => ({
          slug: `room-${index + 1}`,
          providerId: index % 2 === 0 ? "kilter" : "crux",
          roomName: `Room ${index + 1}`,
          lastVisitedAt: new Date(Date.UTC(2026, 2, 8, index, 0, 0)).toISOString(),
        })),
        intro: {
          version: 1,
          landingDismissed: true,
          soloDismissed: true,
        },
        onboarding: {
          version: 1,
          dismissed: true,
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
    expect(screen.getAllByRole("link", { name: /Open /i })).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "See more" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getAllByRole("link", { name: /Open /i })).toHaveLength(9);
    expect(within(dialog).getByText("Room 10")).toBeInTheDocument();
    expect(within(dialog).queryByText("Room 1")).not.toBeInTheDocument();
  });

  it("shows onboarding first, then the landing intro once, and lets the user replay onboarding", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    window.localStorage.clear();

    const view = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("First-time guide")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start exploring" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(await screen.findByRole("button", { name: "Start exploring" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start exploring" }));
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
    window.localStorage.clear();

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

  it("shows board preview images and climb metrics in solo browse", async () => {
    mockedApi.getBoards.mockResolvedValue([
      {
        id: 17,
        name: "7x10",
        kilter_name: "Kilter Board Homewall",
        preview_image_filename: "product_sizes_layouts_sets/board-17.png",
        climb_count: 1234,
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/solo"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Choose a board")).toBeInTheDocument();
    expect(
      screen.getByAltText("Kilter Board Homewall 7x10 board preview")
    ).toHaveAttribute("src", "/api/images/board-17.png");
    expect(screen.getByText("1,234 climbs")).toBeInTheDocument();
  });

  it("shows role-specific onboarding on host and guest entry pages", async () => {
    mockedApi.getBoards.mockResolvedValue([]);
    window.localStorage.clear();

    const { unmount } = render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Host flow: sign in first, then share")).toBeInTheDocument();

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
        savedCredentials: {
          kilter: {
            username: "",
            password: "",
            remember: false,
          },
          crux: {
            token: "saved-crux-token",
            remember: true,
          },
        },
        ...DEFAULT_DISMISSED_GUIDES_PREFS,
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
    expect(screen.getByLabelText("Crux API token")).toHaveValue("saved-crux-token");
    expect(screen.getByLabelText("Remember Crux token on this browser")).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Authenticate and create room" }));

    await waitFor(() =>
      expect(mockedApi.createRoom).toHaveBeenCalledWith({
        providerId: "crux",
        roomName: "",
        displayName: "Alex",
        secret: {
          token: "saved-crux-token",
        },
      })
    );
  });

  it("remembers Kilter credentials after successful room creation when requested", async () => {
    const user = userEvent.setup();
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.createRoom.mockResolvedValue({
      ...buildRoomSnapshot("saved-kilter-room"),
      room_name: "Saved Session",
    });
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("saved-kilter-room"),
      room_name: "Saved Session",
    });

    render(
      <MemoryRouter initialEntries={["/rooms/new"]}>
        <App />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText("Room name"), "Saved Session");
    await user.type(screen.getByLabelText("Host display name"), "Host");
    await user.type(screen.getByLabelText("Kilter username"), "host@example.com");
    await user.type(screen.getByLabelText("Kilter password"), "secret-pass");
    await user.click(screen.getByLabelText("Remember Kilter credentials on this browser"));
    await user.click(screen.getByRole("button", { name: "Authenticate and create room" }));

    await waitFor(() =>
      expect(mockedApi.createRoom).toHaveBeenCalledWith({
        providerId: "kilter",
        roomName: "Saved Session",
        displayName: "Host",
        secret: {
          username: "host@example.com",
          password: "secret-pass",
        },
      })
    );

    const storedPrefs = JSON.parse(
      window.localStorage.getItem("kilter-together:user-prefs:v1") || "{}"
    );
    expect(storedPrefs.savedCredentials.kilter).toMatchObject({
      username: "host@example.com",
      password: "secret-pass",
      remember: true,
    });
  });

  it("prefills and remembers Crux credentials in the room connect flow", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        savedCredentials: {
          kilter: {
            username: "",
            password: "",
            remember: false,
          },
          crux: {
            token: "saved-crux-token",
            remember: true,
          },
        },
        ...DEFAULT_DISMISSED_GUIDES_PREFS,
      })
    );
    mockedApi.getBoards.mockResolvedValue([]);
    mockedApi.getRoom.mockResolvedValue({
      ...buildRoomSnapshot("connect-room"),
      provider_id: "crux",
      connection: {
        provider_id: "crux",
        connected: false,
      },
    });
    mockedApi.connectRoomProvider.mockResolvedValue({
      provider_id: "crux",
      connected: true,
    });

    render(
      <MemoryRouter initialEntries={["/rooms/connect-room"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Room connect-room" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Crux API token")).toHaveValue("saved-crux-token");
    expect(screen.getByLabelText("Remember Crux token on this browser")).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Connect provider" }));

    await waitFor(() =>
      expect(mockedApi.connectRoomProvider).toHaveBeenCalledWith("connect-room", {
        token: "saved-crux-token",
      })
    );

    const storedPrefs = JSON.parse(
      window.localStorage.getItem("kilter-together:user-prefs:v1") || "{}"
    );
    expect(storedPrefs.savedCredentials.crux).toMatchObject({
      token: "saved-crux-token",
      remember: true,
    });
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
        ...DEFAULT_DISMISSED_GUIDES_PREFS,
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
