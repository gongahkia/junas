import { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { buildInviteLink } from "@/lib/room-links";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface InviteQRCodeCardProps {
  slug: string;
}

export default function InviteQRCodeCard({ slug }: InviteQRCodeCardProps) {
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const generateQRCode = async () => {
      try {
        const { default: QRCode } = await import("qrcode");
        const inviteLink = buildInviteLink(slug);
        const nextDataUrl = await QRCode.toDataURL(inviteLink, {
          errorCorrectionLevel: "M",
          margin: 1,
          width: 256,
          color: {
            dark: "#0f172a",
            light: "#ffffff",
          },
        });
        if (!cancelled) {
          setQrCodeDataUrl(nextDataUrl);
          setError("");
        }
      } catch (caughtError) {
        console.error("Generate QR code failed", caughtError);
        if (!cancelled) {
          setError("Unable to render the invite QR code on this device.");
        }
      }
    };

    void generateQRCode();

    return () => {
      cancelled = true;
    };
  }, [slug]);

  return (
    <Card className="h-full">
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
        {error ? (
          <div className="w-full rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-center text-sm text-destructive">
            {error}
          </div>
        ) : qrCodeDataUrl ? (
          <img
            src={qrCodeDataUrl}
            alt={`QR code invite for room ${slug}`}
            className="aspect-square w-full max-w-56 rounded-2xl border bg-white p-3 shadow-sm"
          />
        ) : (
          <div className="flex aspect-square w-full max-w-56 items-center justify-center rounded-2xl border bg-muted/30 text-sm text-muted-foreground">
            Generating QR...
          </div>
        )}
        <p className="text-center text-xs text-muted-foreground">
          Room slug: <span className="font-medium text-foreground">{slug}</span>
        </p>
      </CardContent>
    </Card>
  );
}
