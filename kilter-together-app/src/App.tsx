import { useState, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import BoardSelector from "./components/BoardSelector";
import BottomBar from "./components/BottomBar";
import ClimbView from "./components/ClimbView";
import LandingPage from "./components/LandingPage";
import RoomCreatePage from "./components/RoomCreatePage";
import RoomDiscoveryPage from "./components/RoomDiscoveryPage";
import RoomJoinPage from "./components/RoomJoinPage";
import RoomView from "./components/RoomView";
import type { Board } from "./types";
import "./App.css";

function App() {
  const location = useLocation();
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);

  const shouldLoadBoards =
    location.pathname === "/solo" ||
    location.pathname.startsWith("/solo/boards/") ||
    location.pathname.startsWith("/boards/");

  useEffect(() => {
    if (!shouldLoadBoards) {
      setLoading(false);
      return;
    }

    const fetchBoards = async () => {
      setLoading(true);
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
  }, [shouldLoadBoards]);

  return (
    <div className="min-h-screen pb-20">
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
      <BottomBar />
    </div>
  );
}

export default App;
