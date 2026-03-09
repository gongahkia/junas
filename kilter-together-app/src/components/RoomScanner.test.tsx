import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import jsQR from "jsqr";
import RoomScanner from "./RoomScanner";
import { ToastProvider } from "@/components/ui/toast";

vi.mock("jsqr", () => ({
  default: vi.fn(),
}));

const mockedJsQR = vi.mocked(jsQR);

describe("RoomScanner", () => {
  const originalRequestAnimationFrame = window.requestAnimationFrame;
  const originalCancelAnimationFrame = window.cancelAnimationFrame;
  const originalMediaDevices = navigator.mediaDevices;

  beforeEach(() => {
    vi.resetAllMocks();

    Object.defineProperty(HTMLMediaElement.prototype, "readyState", {
      configurable: true,
      get: () => HTMLMediaElement.HAVE_CURRENT_DATA,
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
      configurable: true,
      get: () => 200,
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
      configurable: true,
      get: () => 200,
    });

    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
      () =>
        ({
          drawImage: vi.fn(),
          getImageData: vi.fn(() => ({
            data: new Uint8ClampedArray(200 * 200 * 4),
            width: 200,
            height: 200,
          })),
        }) as unknown as CanvasRenderingContext2D
    );

    vi.stubGlobal(
      "requestAnimationFrame",
      ((callback: FrameRequestCallback) =>
        window.setTimeout(() => callback(performance.now()), 0)) as typeof window.requestAnimationFrame
    );
    vi.stubGlobal(
      "cancelAnimationFrame",
      ((handle: number) => window.clearTimeout(handle)) as typeof window.cancelAnimationFrame
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: originalMediaDevices,
    });
    vi.stubGlobal("requestAnimationFrame", originalRequestAnimationFrame);
    vi.stubGlobal("cancelAnimationFrame", originalCancelAnimationFrame);
  });

  it("starts the camera scanner and detects a room invite QR code", async () => {
    const user = userEvent.setup();
    const onDetected = vi.fn();
    const stopTrack = vi.fn();

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: stopTrack }],
        }),
      },
    });
    mockedJsQR.mockReturnValue({
      binaryData: [],
      data: "http://localhost:3000/join/scanned-room",
      chunks: [],
      version: 1,
      location: {
        topLeftCorner: { x: 0, y: 0 },
        topRightCorner: { x: 1, y: 0 },
        bottomLeftCorner: { x: 0, y: 1 },
        bottomRightCorner: { x: 1, y: 1 },
        topLeftFinderPattern: { x: 0, y: 0 },
        topRightFinderPattern: { x: 1, y: 0 },
        bottomLeftFinderPattern: { x: 0, y: 1 },
        bottomRightAlignmentPattern: { x: 1, y: 1 },
      },
    } as NonNullable<ReturnType<typeof jsQR>>);

    render(
      <ToastProvider>
        <RoomScanner onDetected={onDetected} />
      </ToastProvider>
    );

    await user.click(screen.getByRole("button", { name: "Start scanner" }));

    await waitFor(() => expect(onDetected).toHaveBeenCalledWith("scanned-room"));
    expect(stopTrack).toHaveBeenCalled();
  });

  it("shows a fallback error when camera scanning is unavailable", async () => {
    const user = userEvent.setup();
    const onDetected = vi.fn();

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });

    render(
      <ToastProvider>
        <RoomScanner onDetected={onDetected} />
      </ToastProvider>
    );

    await user.click(screen.getByRole("button", { name: "Start scanner" }));

    expect(
      await screen.findByText(
        "Camera scanning is not available in this browser. Paste the invite link instead."
      )
    ).toBeInTheDocument();
    expect(onDetected).not.toHaveBeenCalled();
  });
});
