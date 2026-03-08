import { useState, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import BoardSelector from "./components/BoardSelector";
import ClimbView from "./components/ClimbView";
import LandingPage from "./components/LandingPage";
import RoomCreatePage from "./components/RoomCreatePage";
import RoomDiscoveryPage from "./components/RoomDiscoveryPage";
import RoomJoinPage from "./components/RoomJoinPage";
import RoomView from "./components/RoomView";
import type { Board } from "./types";
import "./App.css";

function App() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBoards = async () => {
      try {
        const boardsData = await api.getBoards();
        setBoards(boardsData);
      } catch (error) {
        console.error("API Error:", error);
        setBoards([]);
      } finally {
        setLoading(false);
      }
    };

    fetchBoards();
  }, []);

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/rooms/new" element={<RoomCreatePage />} />
      <Route path="/join" element={<RoomDiscoveryPage />} />
      <Route path="/join/:slug" element={<RoomJoinPage />} />
      <Route path="/rooms/:slug" element={<RoomView />} />
      <Route
        path="/solo"
        element={<BoardSelector boards={boards} loading={loading} boardPathPrefix="/solo/boards" />}
      />
      <Route
        path="/boards/:boardId"
        element={<ClimbView boards={boards} boardsLoading={loading} />}
      />
      <Route
        path="/solo/boards/:boardId"
        element={<ClimbView boards={boards} boardsLoading={loading} backPath="/solo" />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
