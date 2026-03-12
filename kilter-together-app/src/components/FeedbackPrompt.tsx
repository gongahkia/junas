import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface FeedbackPromptProps {
  open: boolean;
  title: string;
  description: string;
  onClose: () => void;
  onSubmit: (payload: { sentiment: "up" | "down"; message?: string }) => Promise<void>;
}

export default function FeedbackPrompt({
  open,
  title,
  description,
  onClose,
  onSubmit,
}: FeedbackPromptProps) {
  const [sentiment, setSentiment] = useState<"up" | "down" | "">("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-x-0 bottom-4 z-[110] px-4">
      <Card className="mx-auto max-w-xl border-0 bg-white/96 shadow-2xl shadow-slate-950/20 backdrop-blur">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">{title}</CardTitle>
          <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={sentiment === "up" ? "default" : "outline"}
              onClick={() => setSentiment("up")}
            >
              <ThumbsUp className="mr-2 h-4 w-4" />
              Helpful
            </Button>
            <Button
              type="button"
              variant={sentiment === "down" ? "default" : "outline"}
              onClick={() => setSentiment("down")}
            >
              <ThumbsDown className="mr-2 h-4 w-4" />
              Needs work
            </Button>
          </div>
          <Input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Optional note"
          />
          <div className="flex items-center justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Later
            </Button>
            <Button
              type="button"
              disabled={sentiment === "" || submitting}
              onClick={async () => {
                if (sentiment === "") {
                  return;
                }
                setSubmitting(true);
                try {
                  await onSubmit({
                    sentiment,
                    message: message.trim() || undefined,
                  });
                  onClose();
                  setSentiment("");
                  setMessage("");
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              {submitting ? "Sending..." : "Send"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
