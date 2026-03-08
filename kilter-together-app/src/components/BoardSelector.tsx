import { useNavigate } from "react-router-dom";
import AngleSelector from "./AngleSelector";
import type { Board } from "../types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

interface BoardSelectorProps {
  boards: Board[];
  loading: boolean;
  angle: number;
  onAngleChange: (angle: number) => void;
}

export default function BoardSelector({
  boards,
  loading,
  angle,
  onAngleChange,
}: BoardSelectorProps) {
  const navigate = useNavigate();

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
          <AngleSelector angle={angle} onAngleChange={onAngleChange} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {Array.isArray(boards) &&
            boards.map((board) => (
              <Card
                key={board.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() =>
                  navigate("/dashboard", {
                    state: { boardId: board.id, boardName: board.name },
                  })
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

        <footer className="mt-8 pt-8 border-t text-center text-muted-foreground">
          <p>
            Made with ❤️ by Ze Ming and Gabriel.{" "}
            <a
              href="https://github.com/lczm/boardbuddy"
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
