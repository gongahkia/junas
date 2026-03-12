import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CoachMarkOverlay from "./CoachMarkOverlay";

describe("CoachMarkOverlay", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("skips steps whose targets are no longer present", async () => {
    const user = userEvent.setup();

    render(
      <div>
        <button data-guide="create-room" type="button">
          Create room
        </button>
        <button data-guide="help" type="button">
          Help
        </button>
        <CoachMarkOverlay
          open={true}
          steps={[
            {
              target: '[data-guide="missing-target"]',
              title: "Scout first",
              description: "This step should be skipped because the target no longer exists.",
            },
            {
              target: '[data-guide="create-room"]',
              title: "Host a session",
              description: "Create the room here.",
            },
            {
              target: '[data-guide="help"]',
              title: "Replay the guide",
              description: "Reopen the walkthrough from help.",
            },
          ]}
          onClose={vi.fn()}
        />
      </div>
    );

    expect(await screen.findByText("Host a session")).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Replay the guide")).toBeInTheDocument();
    expect(screen.getByText("Step 2 of 2")).toBeInTheDocument();
  });

  it("flips top-placed steps below the target when there is not enough space above", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function () {
      if (this instanceof HTMLElement && this.dataset.guide === "help") {
        return new DOMRect(560, 12, 92, 40);
      }

      if (this instanceof HTMLElement && this.dataset.slot === "coachmark-card") {
        return new DOMRect(0, 0, 288, 248);
      }

      return new DOMRect(0, 0, 120, 44);
    });

    render(
      <div>
        <button data-guide="help" type="button">
          Help
        </button>
        <CoachMarkOverlay
          open={true}
          steps={[
            {
              target: '[data-guide="help"]',
              title: "Replay the guide",
              description: "Reopen the walkthrough from help.",
              placement: "top",
            },
          ]}
          onClose={vi.fn()}
        />
      </div>
    );

    expect(await screen.findByText("Replay the guide")).toBeInTheDocument();
    expect(document.querySelector('[data-slot="coachmark-pointer"]')).toHaveClass("-top-2");
  });
});
