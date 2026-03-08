import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Layers3, Mountain, Radar } from "lucide-react";
import AngleSelector from "./AngleSelector";
import type { Board } from "../types";
import { DEFAULT_ANGLE } from "@/lib/climbs";
import {
  dismissSoloIntro,
  loadUserPrefs,
  rememberLastKilterSurface,
} from "@/lib/user-prefs";
import IntroDialog from "@/components/IntroDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface BoardSelectorProps {
  boards: Board[];
  loading: boolean;
  boardPathPrefix?: string;
}

export default function BoardSelector({
  boards,
  loading,
  boardPathPrefix = "/boards",
}: BoardSelectorProps) {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const [angle, setAngle] = useState(() => prefs.lastKilter.angle || DEFAULT_ANGLE);

  if (loading) {
    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))] px-6 py-10">
        <div className="mx-auto flex min-h-[70vh] max-w-6xl items-center justify-center">
          <Card className="w-full max-w-xl border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-3xl">Loading solo browse</CardTitle>
              <CardDescription className="text-base">
                Fetching the available Kilter boards for this local session.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              This page stays read-only and uses the same local catalog as the collaborative rooms.
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]">
      <IntroDialog
        open={!prefs.intro.soloDismissed}
        title="Inspect Kilter climbs without a room"
        description="Use the same local dataset, pick a board angle, and browse climbs in a cleaner read-only view before you start a shared session."
        features={[
          {
            icon: <Layers3 className="h-6 w-6" />,
            title: "Board-first entry",
            description: "Choose the board size first, then dive straight into the catalog.",
          },
          {
            icon: <Mountain className="h-6 w-6" />,
            title: "Angle-aware grades",
            description: "Keep the selected angle pinned so grade context stays consistent.",
          },
          {
            icon: <Radar className="h-6 w-6" />,
            title: "Fast scouting",
            description: "Search, filter by setter, and inspect overlays before you climb.",
          },
        ]}
        dismissLabel="Open solo browse"
        onDismiss={() => setPrefs(dismissSoloIntro())}
      />

      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="flex items-center justify-between py-4">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
              Solo Kilter Browse
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-6xl">
              kilter-together
            </h1>
          </div>
          <Button asChild variant="ghost">
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to rooms
            </Link>
          </Button>
        </header>

        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center gap-6 py-8">
          <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-center text-3xl sm:text-4xl">
                Inspect Kilter climbs without a room
              </CardTitle>
              <CardDescription className="mx-auto max-w-3xl text-center text-base leading-7">
                Use the same local dataset, pick a board angle, and browse climbs in a cleaner read-only view before you start a shared session.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border bg-white/70 p-5 text-center text-sm leading-7 text-muted-foreground">
                Solo mode is optimized for quick scouting. Keep the filters local to this browser, inspect image overlays, then jump into a collaborative room when you want shared decisions.
              </div>
              <div className="flex flex-wrap justify-center gap-2 text-sm text-muted-foreground">
                <span className="rounded-full bg-teal-100 px-3 py-1 font-medium text-teal-800">
                  Read-only catalog
                </span>
                <span className="rounded-full bg-teal-100 px-3 py-1 font-medium text-teal-800">
                  Angle-pinned grades
                </span>
                <span className="rounded-full bg-teal-100 px-3 py-1 font-medium text-teal-800">
                  Search + overlays
                </span>
              </div>
            </CardContent>
          </Card>

          <div className="mx-auto grid w-full max-w-4xl gap-6 md:grid-cols-2">
            <Card className="bg-card/90">
              <CardHeader>
                <CardTitle>Choose the default angle</CardTitle>
                <CardDescription>
                  This angle becomes the starting view whenever you open a board from this page.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <AngleSelector angle={angle} onAngleChange={setAngle} />
                <p className="text-sm text-muted-foreground">
                  The browser remembers your last solo angle locally for the next visit.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card/90">
              <CardHeader>
                <CardTitle>What solo mode is for</CardTitle>
                <CardDescription>
                  Solo browse stays read-only. Use rooms when you want voting, queueing, QR invites, or live session coordination.
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </main>

        <section className="mx-auto w-full max-w-5xl pb-8">
          <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-2xl">Choose a board</CardTitle>
              <CardDescription>
                Open a board to browse climbs at {angle}° by default.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {boards.length === 0 ? (
                <div className="rounded-2xl border border-dashed bg-muted/20 p-8 text-center text-muted-foreground">
                  No Kilter boards were returned by the API.
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {boards.map((board) => (
                    <button
                      key={board.id}
                      type="button"
                      className="rounded-2xl border bg-white/75 p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:bg-white hover:shadow-lg"
                      onClick={() => {
                        rememberLastKilterSurface(String(board.id), angle);
                        navigate(`${boardPathPrefix}/${board.id}?angle=${angle}&sort=popular`);
                      }}
                    >
                      <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                        Board {board.id}
                      </p>
                      <h2 className="mt-3 text-xl font-medium">{board.kilter_name}</h2>
                      <p className="mt-2 text-sm text-muted-foreground">{board.name}</p>
                      <p className="mt-4 text-sm font-medium text-teal-700">
                        Open at {angle}°
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <footer className="border-t pt-8 text-center text-muted-foreground">
          <p>
            Made with care by Ze Ming and Gabriel.{" "}
            <a
              href="https://github.com/lczm/kilter-together"
              className="text-primary hover:underline"
            >
              Source code here
            </a>
          </p>
        </footer>
      </div>
    </div>
  );
}
