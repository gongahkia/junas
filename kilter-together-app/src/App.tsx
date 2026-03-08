import { useState, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { api } from "./api";
import BoardSelector from "./components/BoardSelector";
import ClimbView from "./components/ClimbView";
import type { Board } from "./types";
import "./App.css";

function App() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);
  const [angle, setAngle] = useState<number>(40); // Default angle

  useEffect(() => {
    const fetchBoards = async () => {
      try {
        const boardsData = await api.getBoards();
        console.log("API Response:", boardsData);
        setBoards(boardsData);
        setLoading(false);
      } catch (error) {
        console.error("API Error:", error);
        setBoards([]);
        setLoading(false);
      }
    };

    fetchBoards();
  }, []);

  return (
    <Routes>
      <Route
        path="/"
        element={
          <BoardSelector
            boards={boards}
            loading={loading}
            angle={angle}
            onAngleChange={setAngle}
          />
        }
      />
      <Route
        path="/dashboard"
        element={<ClimbView angle={angle} onAngleChange={setAngle} />}
      />
    </Routes>
  );
}

export default App;
