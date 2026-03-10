import { Routes, Route, MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RoomJoinPage from "@/components/RoomJoinPage";
import { ToastProvider } from "@/components/ui/toast";

const joinRoomMock = vi.fn();

vi.mock("@/api", () => ({
  api: {
    joinRoom: (...args: unknown[]) => joinRoomMock(...args),
  },
}));

vi.mock("@/lib/observability", () => ({
  reportError: vi.fn(),
  reportEvent: vi.fn(),
}));

function renderJoinPage(initialEntry: string) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/join/:slug" element={<RoomJoinPage />} />
          <Route path="/rooms/:slug" element={<div>room destination</div>} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  );
}

describe("RoomJoinPage", () => {
  beforeEach(() => {
    joinRoomMock.mockReset();
    window.localStorage.clear();
  });

  it("shows a rejoin explanation when the room session expired", () => {
    renderJoinPage("/join/session-room?reason=session_expired");

    expect(
      screen.getByText(
        "Your last room session on this browser expired. Rejoin the room to continue."
      )
    ).toBeInTheDocument();
  });

  it("shows an inline rename prompt when the display name is already taken", async () => {
    joinRoomMock.mockRejectedValue({
      isAxiosError: true,
      message: "Request failed with status code 400",
      response: {
        data: {
          code: "display_name_taken",
          error: "display name is already taken",
          status: "400",
        },
        status: 400,
      },
    });

    renderJoinPage("/join/shared-session");
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Host" },
    });
    await user.click(screen.getByRole("button", { name: "Join room" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "That display name is already in use in this room. Try a different one."
        )
      ).toBeInTheDocument();
    });
  });
});
