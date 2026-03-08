import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AngleSelector from "./AngleSelector";
import type { Board } from "../types";
import { DEFAULT_ANGLE } from "@/lib/climbs";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

interface BoardSelectorProps {
  boards: Board[];
  loading: boolean;
}

export default function BoardSelector({ boards, loading }: BoardSelectorProps) {
  const navigate = useNavigate();
  const [angle, setAngle] = useState(DEFAULT_ANGLE);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-8">
        <h1 className="text-4xl mb-4">Kilter Together</h1>
        <div className="text-muted-foreground">Loading boards...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-4xl">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl">Kilter Together</h1>
          <AngleSelector angle={angle} onAngleChange={setAngle} />
        </div>

        {boards.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
            No Kilter boards were returned by the API.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {Array.isArray(boards) &&
            boards.map((board) => (
              <Card
                key={board.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() =>
                  navigate(`/boards/${board.id}?angle=${angle}&sort=popular`)
                }
              >
                <CardHeader>
                  <CardContent className="text-base text-center">
                    {board.kilter_name}
                  </CardContent>
                  <CardContent className="text-sm text-center">
                    {board.name}
                  </CardContent>
                </CardHeader>
              </Card>
            ))}
          </div>
        )}

        <footer className="mt-8 pt-8 border-t text-center text-muted-foreground">
          <p>
            Made with ❤️ by Ze Ming and Gabriel.{" "}
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
