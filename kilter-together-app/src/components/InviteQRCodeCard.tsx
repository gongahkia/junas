import { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { buildInviteLink } from "@/lib/room-links";
import { useErrorToast } from "@/hooks/use-toast";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface InviteQRCodeCardProps {
  slug: string;
  compact?: boolean;
  embedded?: boolean;
  className?: string;
}

export default function InviteQRCodeCard({
  slug,
  compact = false,
  embedded = false,
  className,
}: InviteQRCodeCardProps) {
  const showErrorToast = useErrorToast();
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState("");
  const [qrUnavailable, setQrUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const generateQRCode = async () => {
      try {
        const { default: QRCode } = await import("qrcode");
        const inviteLink = buildInviteLink(slug);
        const nextDataUrl = await QRCode.toDataURL(inviteLink, {
          errorCorrectionLevel: "M",
          margin: 1,
          width: compact ? 176 : 256,
          color: {
            dark: "#0f172a",
            light: "#ffffff",
          },
        });
        if (!cancelled) {
          setQrCodeDataUrl(nextDataUrl);
          setQrUnavailable(false);
        }
      } catch (caughtError) {
        console.error("Generate QR code failed", caughtError);
        if (!cancelled) {
          setQrCodeDataUrl("");
          setQrUnavailable(true);
          showErrorToast("Unable to render the invite QR code on this device.");
        }
      }
    };

    void generateQRCode();

    return () => {
      cancelled = true;
    };
  }, [compact, showErrorToast, slug]);

  const qrFrameClassName = compact ? "w-40 rounded-xl p-2.5" : "w-full max-w-56 rounded-2xl p-3";
  const qrPlaceholderClassName = compact
    ? "w-40 rounded-xl px-5 text-xs"
    : "w-full max-w-56 rounded-2xl px-6 text-sm";
  const qrGraphic = qrCodeDataUrl ? (
    <img
      src={qrCodeDataUrl}
      alt={`QR code invite for room ${slug}`}
      className={cn("aspect-square w-full border bg-white shadow-sm", qrFrameClassName)}
    />
  ) : qrUnavailable ? (
    <div
      className={cn(
        "flex aspect-square w-full items-center justify-center border bg-muted/30 text-center text-muted-foreground",
        qrPlaceholderClassName
      )}
    >
      QR unavailable on this device.
    </div>
  ) : (
    <div
      className={cn(
        "flex aspect-square w-full items-center justify-center border bg-muted/30 text-muted-foreground",
        qrPlaceholderClassName
      )}
    >
      Generating QR...
    </div>
  );

  if (embedded) {
    return (
      <div className={cn("flex w-full flex-col items-center gap-2 sm:w-auto", className)}>
        {qrGraphic}
        <p className="text-center text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
          Scan to join
        </p>
      </div>
    );
  }

  return (
    <Card className={cn("h-full", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Link2 className="h-4 w-4" />
          Scan to join
        </CardTitle>
        <CardDescription>
          Guests can open their camera from the join flow and scan this invite code.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-3">
        {qrGraphic}
        <p className="text-center text-xs text-muted-foreground">
          Room slug: <span className="font-medium text-foreground">{slug}</span>
        </p>
      </CardContent>
    </Card>
  );
}
