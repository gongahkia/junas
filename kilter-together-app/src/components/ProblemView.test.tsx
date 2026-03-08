import { render, screen } from "@testing-library/react";
import ProblemView from "./ProblemView";

describe("ProblemView", () => {
  it("renders climb metadata and image empty state", () => {
    render(
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
      />
    );

    expect(screen.getByText("Sample Problem")).toBeInTheDocument();
    expect(screen.getByText("Technical compression on small holds.")).toBeInTheDocument();
    expect(screen.getByText("Boulder grade: 7a/V6")).toBeInTheDocument();
    expect(screen.getByText("Route grade: 5.12d")).toBeInTheDocument();
    expect(
      screen.getByText("No board images are available for this climb.")
    ).toBeInTheDocument();
  });

  it("renders the filtered empty state when there are no climbs", () => {
    render(<ProblemView angle={40} hasResults={false} selectedClimb={null} />);

    expect(
      screen.getByText("No climbs match the current filters.")
    ).toBeInTheDocument();
  });
});
