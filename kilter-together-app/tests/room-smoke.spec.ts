import { expect, test, type BrowserContext } from "@playwright/test";

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

test("runs a room session end to end with the fake provider", async ({
  browser,
  request,
  isMobile,
}) => {
  test.skip(isMobile, "Desktop smoke is covered separately from the phone-specific flow.");

  const hostContext = await browser.newContext();
  await seedDismissedGuides(hostContext);

  const hostPage = await hostContext.newPage();

  try {
    const readiness = await request.get(`${BACKEND_URL}/api/readyz`);
    expect(readiness.ok()).toBeTruthy();

    await hostPage.goto("/rooms/new");
    await hostPage.getByLabel("Room name").fill("Playwright Session");
    await hostPage.getByLabel("Host display name").fill("Host");
    await hostPage.getByLabel("Provider").click();
    await hostPage.getByRole("option", { name: "Test Provider" }).click();
    await hostPage.getByLabel("Test provider token").fill("integration-token");
    await hostPage.getByRole("button", { name: "Authenticate and create room" }).click();

    await expect(hostPage).toHaveURL(/\/rooms\/[^/]+$/);
    await expect(
      hostPage.getByRole("heading", { name: "Playwright Session" })
    ).toBeVisible();

    const slug = hostPage.url().split("/rooms/")[1];
    expect(slug).toBeTruthy();

    const setSurfaceResult = await hostPage.evaluate(async ({ backendUrl, roomSlug }) => {
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
        body: await response.text(),
      };
    }, { backendUrl: BACKEND_URL, roomSlug: slug });
    expect(setSurfaceResult).toMatchObject({ ok: true, status: 200 });

    await expect(hostPage.getByText("Alpha Wall").first()).toBeVisible();
    await expect(hostPage.getByText("Beta Crimp").first()).toBeVisible({
      timeout: 15000,
    });

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

    const hostQueueEntry = hostPage.getByRole("group", {
      name: "Queue entry Beta Crimp",
    });
    await expect(hostQueueEntry).toBeVisible({ timeout: 15000 });

    const toggleVoteResponse = await request.put(
      `${BACKEND_URL}/api/rooms/${slug}/votes/${encodeURIComponent("test:beta")}`,
      {
        headers: {
          Cookie: guestCookieHeader,
        },
      }
    );
    expect(toggleVoteResponse.ok()).toBeTruthy();
    await expect(
      hostPage.getByRole("button", { name: /Beta Crimp.*1 fist bump/i }).first()
    ).toBeVisible({ timeout: 15000 });

    const addFinalistResult = await hostPage.evaluate(async ({ backendUrl, roomSlug }) => {
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
    await expect
      .poll(async () => {
        const response = await request.get(`${BACKEND_URL}/api/rooms/${slug}`, {
          headers: {
            Cookie: guestCookieHeader,
          },
        });
        const snapshot = await response.json();
        return snapshot.finalists.length;
      })
      .toBe(1);
    const guestSnapshotResponse = await request.get(`${BACKEND_URL}/api/rooms/${slug}`, {
      headers: {
        Cookie: guestCookieHeader,
      },
    });
    const guestSnapshot = await guestSnapshotResponse.json();
    expect(guestSnapshot.finalists).toHaveLength(1);
    expect(guestSnapshot.finalists[0]?.climb?.id).toBe("test:beta");
    const queuedEntryId = guestSnapshot.queue[0]?.id;
    expect(typeof queuedEntryId).toBe("number");

    const promoteCurrentResult = await hostPage.evaluate(async ({ backendUrl, roomSlug, entryId }) => {
      const response = await fetch(`${backendUrl}/api/rooms/${roomSlug}/queue/${entryId}`, {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          status: "current",
        }),
      });

      return {
        ok: response.ok,
        status: response.status,
      };
    }, { backendUrl: BACKEND_URL, roomSlug: slug, entryId: queuedEntryId });
    expect(promoteCurrentResult).toMatchObject({ ok: true, status: 200 });
    await expect
      .poll(async () => {
        const response = await request.get(`${BACKEND_URL}/api/rooms/${slug}`, {
          headers: {
            Cookie: guestCookieHeader,
          },
        });
        const snapshot = await response.json();
        return snapshot.queue[0]?.status ?? "";
      })
      .toBe("current");
    const currentSnapshotResponse = await request.get(`${BACKEND_URL}/api/rooms/${slug}`, {
      headers: {
        Cookie: guestCookieHeader,
      },
    });
    const currentSnapshot = await currentSnapshotResponse.json();
    expect(currentSnapshot.queue[0]?.status).toBe("current");

    const metrics = await request.get(`${BACKEND_URL}/api/metrics`);
    expect(metrics.ok()).toBeTruthy();
    const metricsBody = await metrics.text();
    expect(metricsBody).toContain("kilter_together_http_requests_total");
    expect(metricsBody).toContain("kilter_together_room_events_total");
    expect(metricsBody).toContain("kilter_together_room_sse_subscribers");

    const closeRoomResult = await hostPage.evaluate(async ({ backendUrl, roomSlug }) => {
      const response = await fetch(`${backendUrl}/api/rooms/${roomSlug}/close`, {
        method: "POST",
        credentials: "include",
      });

      return {
        ok: response.ok,
        status: response.status,
      };
    }, { backendUrl: BACKEND_URL, roomSlug: slug });
    expect(closeRoomResult).toMatchObject({ ok: true, status: 200 });
    await expect
      .poll(async () => {
        const response = await request.get(`${BACKEND_URL}/api/rooms/${slug}`, {
          headers: {
            Cookie: guestCookieHeader,
          },
        });
        if (response.status() === 401) {
          return "401";
        }
        const snapshot = await response.json();
        return snapshot.status;
      })
      .toMatch(/^(closed|401)$/);
    const closedSnapshotResponse = await request.get(`${BACKEND_URL}/api/rooms/${slug}`, {
      headers: {
        Cookie: guestCookieHeader,
      },
    });
    if (closedSnapshotResponse.status() === 401) {
      expect(closedSnapshotResponse.status()).toBe(401);
    } else {
      const closedSnapshot = await closedSnapshotResponse.json();
      expect(closedSnapshot.status).toBe("closed");
    }
  } finally {
    await hostContext.close().catch(() => undefined);
  }
});
