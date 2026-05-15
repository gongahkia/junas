import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HomePage from "@/app/page";
import type { RecentSummary, SummaryPayload, TargetsPayload } from "@/lib/contracts";
import * as api from "@/lib/api";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");

  return {
    ...actual,
    searchTitles: vi.fn(),
    fetchTargets: vi.fn(),
    createSummary: vi.fn(),
  };
});

const mockedSearchTitles = vi.mocked(api.searchTitles);
const mockedFetchTargets = vi.mocked(api.fetchTargets);
const mockedCreateSummary = vi.mocked(api.createSummary);

const RECENTS_STORAGE_KEY = "sayless.recent-summaries";

const sampleTargets: TargetsPayload = {
  media: {
    id: "31240",
    title: "Re:ZERO -Starting Life in Another World-",
    subtitle: "TV • 2016 • 25 eps",
    source: "myanimelistanime",
    source_label: "MyAnimeList Anime",
    media_type: "anime",
    image_url: "https://cdn.example/anime.jpg",
    external_url: "https://myanimelist.net/anime/31240",
  },
  target_mode: "segment",
  targets: [
    {
      id: "1",
      type: "episode",
      label: "Episode 1 • The End of the Beginning and the Beginning of the End",
      description: "Subaru is pulled into another world and quickly gets overwhelmed.",
      episode_number: 1,
    },
  ],
};

const sampleSummary: SummaryPayload = {
  media: sampleTargets.media,
  target: sampleTargets.targets[0],
  summary: {
    characters: ["Subaru", "Emilia"],
    key_events: [
      "Subaru arrives in another world and stumbles into a dangerous situation.",
    ],
    plot_points: [
      "Subaru meets Emilia and gets dragged into a loop of escalating events.",
    ],
    skip_context:
      "Subaru is now emotionally invested in helping Emilia and has already been destabilized by the world he entered.",
  },
  meta: {
    spoiler_level: "standard",
    source_name: "MyAnimeList Anime",
    generated_at: "2026-03-14T01:00:00Z",
    attribution: {
      label: "MyAnimeList Anime",
      url: "https://myanimelist.net/anime/31240",
    },
  },
};

describe("HomePage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockedSearchTitles.mockReset();
    mockedFetchTargets.mockReset();
    mockedCreateSummary.mockReset();
  });

  it("walks through search, target selection, and summary generation", async () => {
    mockedSearchTitles.mockResolvedValue([
      {
        ...sampleTargets.media,
        supports_segments: true,
      },
    ]);
    mockedFetchTargets.mockResolvedValue(sampleTargets);
    mockedCreateSummary.mockResolvedValue(sampleSummary);

    const user = userEvent.setup();

    render(<HomePage />);

    const searchInput = screen.getByLabelText(/search anime/i);
    await user.type(searchInput, "rezero");

    await waitFor(() => {
      expect(mockedSearchTitles).toHaveBeenCalledWith(
        "myanimelistanime",
        "rezero",
      );
    }, { timeout: 2000 });

    await user.click(
      await screen.findByRole("button", {
        name: /re:zero -starting life in another world-/i,
      }),
    );

    await waitFor(() => {
      expect(mockedFetchTargets).toHaveBeenCalledWith(
        "myanimelistanime",
        "31240",
      );
    });

    await user.click(
      screen.getByRole("button", { name: /generate structured summary/i }),
    );

    await waitFor(() => {
      expect(mockedCreateSummary).toHaveBeenCalledWith({
        source: "myanimelistanime",
        mediaId: "31240",
        targetType: "episode",
        targetId: "1",
        spoilerLevel: "standard",
      });
    });

    expect(
      await screen.findByText(
        /Subaru is now emotionally invested in helping Emilia/i,
      ),
    ).toBeInTheDocument();

    const storedRecents = window.localStorage.getItem(RECENTS_STORAGE_KEY);
    expect(storedRecents).not.toBeNull();
    expect(storedRecents).toContain("Re:ZERO -Starting Life in Another World-");
  });

  it("hydrates recent summaries from local storage for quick reopening", async () => {
    const recentEntry: RecentSummary = {
      stored_at: "2026-03-14T01:05:00Z",
      payload: sampleSummary,
    };

    window.localStorage.setItem(
      RECENTS_STORAGE_KEY,
      JSON.stringify([recentEntry]),
    );

    const user = userEvent.setup();

    render(<HomePage />);

    await user.click(
      await screen.findByRole("button", {
        name: /re:zero -starting life in another world-/i,
      }),
    );

    expect(
      screen.getByText(
        /Subaru is now emotionally invested in helping Emilia/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reopen/i }),
    ).toBeInTheDocument();
  });
});
