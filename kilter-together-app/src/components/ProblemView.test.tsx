import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProblemView from "./ProblemView";
import { ToastProvider } from "@/components/ui/toast";

function renderProblemView(node: ReactNode) {
  return render(<ToastProvider>{node}</ToastProvider>);
}

describe("ProblemView", () => {
  it("renders climb metadata and image empty state", () => {
    renderProblemView(
      <ProblemView
        angle={40}
        hasResults={true}
        selectedClimb={{
          uuid: "uuid-1",
          climb_name: "Sample Problem",
          description: "Technical compression on small holds.",
          frames: "frames",
          grades: {
            "40": {
              boulder: "7a/V6",
              route: "5.12d",
            },
          },
          setter_name: "setter-a",
          image_filenames: [],
          product_size_id: 14,
          ascends: 9,
          created_at: "2026-01-01 00:00:00.000000",
        }}
      />,
    );

    expect(screen.getByText("Sample Problem")).toBeInTheDocument();
    expect(
      screen.getByText("Technical compression on small holds."),
    ).toBeInTheDocument();
    expect(screen.getByText("Boulder grade: 7a/V6")).toBeInTheDocument();
    expect(screen.getByText("Route grade: 5.12d")).toBeInTheDocument();
    expect(
      screen.getByText("No board images are available for this climb."),
    ).toBeInTheDocument();
  });

  it("renders the filtered empty state when there are no climbs", () => {
    renderProblemView(<ProblemView angle={40} hasResults={false} selectedClimb={null} />);

    expect(
      screen.getByText("No climbs match the current filters."),
    ).toBeInTheDocument();
  });

  it("renders highlighted hold overlays when board images are present", () => {
    const { container } = renderProblemView(
      <ProblemView
        angle={40}
        hasResults={true}
        selectedClimb={{
          uuid: "uuid-1",
          climb_name: "Sample Problem",
          frames: "p200r12p300r15",
          grades: {
            "40": {
              boulder: "7a/V6",
              route: "5.12d",
            },
          },
          setter_name: "setter-a",
          image_filenames: ["original-16x12-bolt-ons-v2.png"],
          highlighted_holds: [
            {
              position: 200,
              x: 50,
              y: 25,
              role: "start",
              color: "#00DD00",
            },
            {
              position: 300,
              x: 70,
              y: 65,
              role: "foot",
              color: "#FFA500",
            },
          ],
          product_size_id: 14,
          ascends: 9,
          created_at: "2026-01-01 00:00:00.000000",
        }}
      />,
    );

    expect(container.querySelectorAll("svg circle").length).toBeGreaterThan(0);
  });

  it("renders solo action buttons and calls their handlers", async () => {
    const user = userEvent.setup();
    const onToggleFavorite = vi.fn();
    const onToggleShortlist = vi.fn();

    renderProblemView(
      <ProblemView
        angle={40}
        hasResults={true}
        isFavorite={false}
        isShortlisted={true}
        onToggleFavorite={onToggleFavorite}
        onToggleShortlist={onToggleShortlist}
        selectedClimb={{
          uuid: "uuid-1",
          climb_name: "Sample Problem",
          frames: "frames",
          grades: {
            "40": {
              boulder: "7a/V6",
              route: "5.12d",
            },
          },
          setter_name: "setter-a",
          image_filenames: [],
          product_size_id: 14,
          ascends: 9,
          created_at: "2026-01-01 00:00:00.000000",
        }}
      />
    );

    expect(screen.getByRole("button", { name: "Add to favorites" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "In shortlist" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add to favorites" }));
    await user.click(screen.getByRole("button", { name: "In shortlist" }));

    expect(onToggleFavorite).toHaveBeenCalledTimes(1);
    expect(onToggleShortlist).toHaveBeenCalledTimes(1);
  });
});
