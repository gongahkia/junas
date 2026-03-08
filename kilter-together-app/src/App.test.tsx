import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { api } from "./api";

vi.mock("./api", () => ({
  api: {
    getBoards: vi.fn(),
    getPaginatedClimbs: vi.fn(),
    getImageUrl: vi.fn((filename: string) => `/api/images/${filename}`),
  },
}));

const mockedApi = vi.mocked(api);

describe("App routes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
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
});
