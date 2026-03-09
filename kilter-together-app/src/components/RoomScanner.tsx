import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CameraOff, ScanQrCode } from "lucide-react";
import { extractRoomSlugFromValue } from "@/lib/room-links";
import { Button } from "@/components/ui/button";
import { useErrorToast } from "@/hooks/use-toast";

type QRDecoder = typeof import("jsqr").default;

interface RoomScannerProps {
  autoStart?: boolean;
  onDetected: (slug: string) => void;
}

export default function RoomScanner({
  autoStart = false,
  onDetected,
}: RoomScannerProps) {
  const showErrorToast = useErrorToast();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRequestRef = useRef<number | null>(null);
  const decoderRef = useRef<QRDecoder | null>(null);
  const activeRef = useRef(false);
  const autoStartedRef = useRef(false);
  const [status, setStatus] = useState<"idle" | "starting" | "scanning">("idle");

  const stopScanner = useCallback(() => {
    activeRef.current = false;
    if (frameRequestRef.current !== null) {
      window.cancelAnimationFrame(frameRequestRef.current);
      frameRequestRef.current = null;
    }

    const stream = streamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setStatus("idle");
  }, []);

  const scanFrame = useCallback(() => {
    if (!activeRef.current) {
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      frameRequestRef.current = window.requestAnimationFrame(scanFrame);
      return;
    }

    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) {
      showErrorToast("This browser cannot read camera frames for QR scanning.");
      stopScanner();
      return;
    }

    if (
      video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
      video.videoWidth > 0 &&
      video.videoHeight > 0
    ) {
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }

      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
      const decodeQRCode = decoderRef.current;
      const result = decodeQRCode
        ? decodeQRCode(imageData.data, imageData.width, imageData.height)
        : null;
      const roomSlug = result?.data ? extractRoomSlugFromValue(result.data) : null;

      if (roomSlug) {
        onDetected(roomSlug);
        stopScanner();
        return;
      }
    }

    frameRequestRef.current = window.requestAnimationFrame(scanFrame);
  }, [onDetected, showErrorToast, stopScanner]);

  const startScanner = useCallback(async () => {
    if (activeRef.current) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      showErrorToast(
        "Camera scanning is not available in this browser. Paste the invite link instead."
      );
      return;
    }

    setStatus("starting");

    try {
      if (!decoderRef.current) {
        const { default: decodeQRCode } = await import("jsqr");
        decoderRef.current = decodeQRCode;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: {
            ideal: "environment",
          },
        },
      });

      streamRef.current = stream;
      activeRef.current = true;

      if (!videoRef.current) {
        throw new Error("Scanner video element is unavailable.");
      }

      videoRef.current.srcObject = stream;
      videoRef.current.setAttribute("playsinline", "true");
      videoRef.current.muted = true;
      await videoRef.current.play();
      setStatus("scanning");
      frameRequestRef.current = window.requestAnimationFrame(scanFrame);
    } catch (caughtError) {
      console.error("Start scanner failed", caughtError);
      showErrorToast(
        "Unable to access the camera. Check permissions, then try again or paste the invite link manually."
      );
      stopScanner();
    }
  }, [scanFrame, showErrorToast, stopScanner]);

  useEffect(() => {
    if (autoStart && !autoStartedRef.current) {
      autoStartedRef.current = true;
      void startScanner();
    }
  }, [autoStart, startScanner]);

  useEffect(() => stopScanner, [stopScanner]);

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-3xl border bg-slate-950">
        <div className="relative aspect-[4/3]">
          <video
            ref={videoRef}
            className="h-full w-full object-cover"
            aria-label="Room QR scanner preview"
          />
          <canvas ref={canvasRef} className="hidden" />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-44 w-44 rounded-[2.5rem] border-2 border-white/80 shadow-[0_0_0_999px_rgba(15,23,42,0.35)]" />
          </div>
          {status !== "scanning" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/70 px-6 text-center text-sm text-slate-100">
              <ScanQrCode className="h-8 w-8" />
              <p>Point your camera at the host QR code to open the room invite.</p>
            </div>
          ) : null}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        {status === "scanning"
          ? "Scanning for a room invite..."
          : status === "starting"
            ? "Opening the camera..."
            : "Use the rear camera when prompted for the best scan reliability."}
      </p>

      <div className="flex gap-3">
        <Button
          type="button"
          className="flex-1"
          onClick={() => void startScanner()}
          disabled={status === "starting" || status === "scanning"}
        >
          <Camera className="mr-2 h-4 w-4" />
          {status === "starting" ? "Opening camera..." : "Start scanner"}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="flex-1"
          onClick={stopScanner}
          disabled={status === "idle"}
        >
          <CameraOff className="mr-2 h-4 w-4" />
          Stop
        </Button>
      </div>
    </div>
  );
}
