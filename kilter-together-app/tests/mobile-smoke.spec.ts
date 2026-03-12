import { expect, test, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";

const BACKEND_URL = "http://127.0.0.1:38082";
const USER_PREFS_STORAGE_KEY = "kilter-together:user-prefs:v1";
const DISMISSED_GUIDES_PREFS = {
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
  settings: {
    autoGuidesEnabled: false,
  },
};

test.describe.configure({ mode: "serial" });
test.setTimeout(60000);

function uniqueName(prefix: string) {
  return `${prefix} ${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function parseSetCookie(headerValue: string | undefined) {
  if (!headerValue) {
    return null;
  }

  const [cookiePair] = headerValue.split(";", 1);
  const separatorIndex = cookiePair.indexOf("=");
  if (separatorIndex <= 0) {
    return null;
  }

  return {
    name: cookiePair.slice(0, separatorIndex),
    value: cookiePair.slice(separatorIndex + 1),
  };
}

async function seedDismissedGuides(context: BrowserContext) {
  await context.addInitScript(
    ({ key, prefs }) => {
      window.localStorage.setItem(key, JSON.stringify(prefs));
    },
    { key: USER_PREFS_STORAGE_KEY, prefs: DISMISSED_GUIDES_PREFS }
  );
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    document: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));

  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport + 1);
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport + 1);
}

async function createRoomViaApi(request: APIRequestContext, roomName: string) {
  const response = await request.post(`${BACKEND_URL}/api/rooms`, {
    data: {
      provider_id: "test",
      room_name: roomName,
      display_name: "Host",
      secret: {
        token: "integration-token",
      },
      fist_bumps_enabled: true,
    },
  });

  expect(response.ok()).toBeTruthy();
  const room = (await response.json()) as { slug: string };
  expect(room.slug).toBeTruthy();

  return room.slug;
}

async function createRoomViaUi(page: Page, roomName: string) {
  await page.goto("/rooms/new");
  await page.getByLabel("Room name").fill(roomName);
  await page.getByLabel("Host display name").fill("Host");
  await page.getByLabel("Provider").click();
  await page.getByRole("option", { name: "Test Provider" }).click();
  await page.getByLabel("Test provider token").fill("integration-token");
  await page.getByRole("button", { name: "Authenticate and create room" }).click();

  await expect(page).toHaveURL(/\/rooms\/[^/]+$/);
  return page.url().split("/rooms/")[1] ?? "";
}

async function loadFirstBoardAndClimb(request: APIRequestContext) {
  const boardsResponse = await request.get(`${BACKEND_URL}/api/boards`);
  expect(boardsResponse.ok()).toBeTruthy();
  const boardsPayload = (await boardsResponse.json()) as {
    boards: Array<{ id: number; climb_count?: number }>;
  };
  const board = boardsPayload.boards.find((candidate) => (candidate.climb_count ?? 0) > 0);
  expect(board).toBeTruthy();

  for (const angle of [40, 45, 50, 55, 60]) {
    const climbsResponse = await request.get(`${BACKEND_URL}/api/climbs`, {
      params: {
        board_id: String(board!.id),
        angle: String(angle),
        page_size: "10",
      },
    });
    expect(climbsResponse.ok()).toBeTruthy();
    const climbsPayload = (await climbsResponse.json()) as {
      climbs: Array<{ uuid: string; climb_name: string }>;
    };

    if (climbsPayload.climbs.length > 0) {
      return {
        angle,
        boardId: board!.id,
        climbId: climbsPayload.climbs[0].uuid,
        climbName: climbsPayload.climbs[0].climb_name,
      };
    }
  }

  throw new Error(`No climbs were returned for board ${board!.id}.`);
}

test("navigates from landing to room creation on a phone viewport", async ({
  context,
  isMobile,
  page,
}) => {
  test.skip(!isMobile, "Mobile-only smoke coverage.");

  await seedDismissedGuides(context);

  await page.goto("/");
  await expect(
    page.getByRole("button", { name: /open collaborative board sessions menu/i })
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "Create room" }).click();
  await expect(page).toHaveURL(/\/rooms\/new$/);
  await expect(page.getByText("Create a collaborative room")).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("joins a room cleanly from the phone join flow", async ({
  context,
  isMobile,
  page,
  request,
}) => {
  test.skip(!isMobile, "Mobile-only smoke coverage.");

  await seedDismissedGuides(context);

  const roomName = uniqueName("Playwright Phone Join");
  const slug = await createRoomViaApi(request, roomName);

  await page.goto(`/join/${slug}`);
  await expect(
    page.getByRole("button", { name: /open join room menu/i })
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByLabel("Display name").fill("Guest");
  await page.getByRole("button", { name: "Join room", exact: true }).click();

  await expect(page).toHaveURL(new RegExp(`/rooms/${slug}$`));
  await expect(page.getByRole("heading", { name: roomName })).toBeVisible();
  await expect(page.getByText("Room pulse")).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("opens the mobile climb sheet while keeping climb detail visible", async ({
  context,
  isMobile,
  page,
  request,
}) => {
  test.skip(!isMobile, "Mobile-only smoke coverage.");

  await seedDismissedGuides(context);

  const { angle, boardId, climbId, climbName } = await loadFirstBoardAndClimb(request);
  await page.goto(`/solo/boards/${boardId}?angle=${angle}&climb=${encodeURIComponent(climbId)}`);

  await expect(page.getByRole("button", { name: "Filters & climbs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: climbName })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("button", { name: "Filters & climbs" }).click();
  await expect(page.getByPlaceholder("Search climbs")).toBeVisible();
  await page.getByPlaceholder("Search climbs").fill(climbName.split(" ")[0] ?? climbName);
  await expect(page.getByText(climbName, { exact: true }).first()).toBeVisible();
});

test("exposes host queue and finalist controls in the mobile room flow", async ({
  context,
  isMobile,
  page,
  request,
}) => {
  test.skip(!isMobile, "Mobile-only smoke coverage.");

  await seedDismissedGuides(context);

  const roomName = uniqueName("Playwright Mobile Host");
  const slug = await createRoomViaUi(page, roomName);
  await expect(page.getByRole("heading", { name: roomName })).toBeVisible();

  const setSurfaceResult = await page.evaluate(async ({ backendUrl, roomSlug }) => {
    const response = await fetch(`${backendUrl}/api/rooms/${roomSlug}/surface`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        surface_id: "wall-alpha",
        context: {
          gym_slug: "gym-test",
          parent_id: "gym-test",
        },
      }),
    });

    return {
      ok: response.ok,
      status: response.status,
    };
  }, { backendUrl: BACKEND_URL, roomSlug: slug });
  expect(setSurfaceResult).toMatchObject({ ok: true, status: 200 });

  const joinResponse = await request.post(`${BACKEND_URL}/api/rooms/${slug}/join`, {
    data: {
      display_name: "Guest",
    },
  });
  expect(joinResponse.ok()).toBeTruthy();
  const guestSessionCookie = parseSetCookie(joinResponse.headers()["set-cookie"]);
  expect(guestSessionCookie).not.toBeNull();
  const guestCookieHeader = `${guestSessionCookie!.name}=${guestSessionCookie!.value}`;

  const addQueueResponse = await request.post(`${BACKEND_URL}/api/rooms/${slug}/queue`, {
    headers: {
      Cookie: guestCookieHeader,
    },
    data: {
      climb_id: "test:beta",
    },
  });
  expect(addQueueResponse.ok()).toBeTruthy();

  const toggleVoteResponse = await request.put(
    `${BACKEND_URL}/api/rooms/${slug}/votes/${encodeURIComponent("test:beta")}`,
    {
      headers: {
        Cookie: guestCookieHeader,
      },
    }
  );
  expect(toggleVoteResponse.ok()).toBeTruthy();

  const addFinalistResult = await page.evaluate(async ({ backendUrl, roomSlug }) => {
    const response = await fetch(`${backendUrl}/api/rooms/${roomSlug}/finalists`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        climb_id: "test:beta",
      }),
    });

    return {
      ok: response.ok,
      status: response.status,
    };
  }, { backendUrl: BACKEND_URL, roomSlug: slug });
  expect(addFinalistResult).toMatchObject({ ok: true, status: 201 });

  await expect(page.getByRole("button", { name: "Queue", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Queue", exact: true }).click();
  await expect(
    page.getByRole("group", { name: "Queue entry Beta Crimp" })
  ).toBeVisible({ timeout: 15000 });
  await expect(
    page.getByRole("button", { name: /Beta Crimp.*1 fist bump/i }).first()
  ).toBeVisible({ timeout: 15000 });
  await expect(
    page.getByRole("button", { name: /Move Beta Crimp up in queue/i })
  ).toBeVisible();

  const finalistGroup = page.getByRole("group", { name: "Finalist Beta Crimp" });
  await finalistGroup.scrollIntoViewIfNeeded();
  await expect(finalistGroup).toBeVisible({ timeout: 15000 });
  await expect(
    page.getByRole("button", { name: /Move Beta Crimp up in finalists/i })
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
