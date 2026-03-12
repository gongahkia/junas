import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BoardSelector from "./BoardSelector";

vi.mock("@/hooks/useProviderCapabilities", () => ({
  useProviderCapabilities: () => ({
    loading: false,
    capabilities: [
      {
        id: "kilter",
        label: "Kilter",
        room_supported: true,
        solo_supported: true,
        surface_hierarchy: "board",
        auth_fields: [],
      },
      {
        id: "crux",
        label: "Crux",
        room_supported: true,
        solo_supported: true,
        surface_hierarchy: "nested",
        auth_fields: [],
      },
    ],
  }),
}));

function renderBoardSelector() {
  return render(
    <MemoryRouter>
      <BoardSelector boards={[]} loading={false} />
    </MemoryRouter>
  );
}

describe("BoardSelector", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("anchors the saved solo guide step to the first saved-state card", () => {
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        savedSoloFilters: [
          {
            id: "preset-1",
            label: "Project night",
            board_id: "17",
            board_name: "7x10",
            angle: 40,
            sort: "popular",
            saved_at: "2026-03-12T00:00:00Z",
          },
        ],
        soloFavorites: [
          {
            uuid: "uuid-1",
            product_size_id: 17,
            climb_name: "Moon Landing",
            setter_name: "Setter A",
            board_id: "17",
            board_name: "7x10",
            angle: 40,
            grade: "6a/V3",
            ascends: 10,
            saved_at: "2026-03-12T00:00:00Z",
          },
        ],
      })
    );

    renderBoardSelector();

    const savedStateTarget = document.querySelector('[data-guide="solo-collections"]');

    expect(savedStateTarget).not.toBeNull();
    expect(within(savedStateTarget as HTMLElement).getByText("Saved filters")).toBeInTheDocument();
    expect(within(savedStateTarget as HTMLElement).queryByText("Favorites")).not.toBeInTheDocument();
  });

  it("falls back to the next saved-state card when filters are absent", () => {
    window.localStorage.setItem(
      "kilter-together:user-prefs:v1",
      JSON.stringify({
        soloFavorites: [
          {
            uuid: "uuid-1",
            product_size_id: 17,
            climb_name: "Moon Landing",
            setter_name: "Setter A",
            board_id: "17",
            board_name: "7x10",
            angle: 40,
            grade: "6a/V3",
            ascends: 10,
            saved_at: "2026-03-12T00:00:00Z",
          },
        ],
      })
    );

    renderBoardSelector();

    const savedStateTarget = document.querySelector('[data-guide="solo-collections"]');
    const providerTarget = document.querySelector('[data-guide="solo-providers"]');

    expect(savedStateTarget).not.toBeNull();
    expect(within(savedStateTarget as HTMLElement).getByText("Favorites")).toBeInTheDocument();
    expect(screen.getByText("Other solo providers")).toBeInTheDocument();
    expect(providerTarget).not.toBeNull();
    expect(within(providerTarget as HTMLElement).getByText("Crux")).toBeInTheDocument();
  });
});
