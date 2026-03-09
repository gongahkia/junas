import { useState, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import AboutPage from "./components/AboutPage";
import BoardSelector from "./components/BoardSelector";
import BottomBar from "./components/BottomBar";
import ClickCheerOverlay from "./components/ClickCheerOverlay";
import ClimbView from "./components/ClimbView";
import LandingPage from "./components/LandingPage";
import RoomCreatePage from "./components/RoomCreatePage";
import RoomDiscoveryPage from "./components/RoomDiscoveryPage";
import RoomJoinPage from "./components/RoomJoinPage";
import RoomView from "./components/RoomView";
import SettingsPage from "./components/SettingsPage";
import { ToastProvider } from "./components/ui/toast";
import { useErrorToast } from "./hooks/use-toast";
import { loadUserPrefs, USER_PREFS_CHANGE_EVENT } from "./lib/user-prefs";
import type { Board } from "./types";
import "./App.css";

function AppContent() {
  const location = useLocation();
  const showErrorToast = useErrorToast();
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);
  const isLandingRoute = location.pathname === "/";

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
        showErrorToast("Unable to load the board list right now. Try refreshing the page.");
      } finally {
        setLoading(false);
      }
    };

    fetchBoards();
  }, [shouldLoadBoards, showErrorToast]);

  useEffect(() => {
    const syncMotionClass = () => {
      document.body.classList.toggle(
        "playful-motion-disabled",
        !loadUserPrefs().settings.playfulMotionEnabled
      );
    };

    syncMotionClass();
    window.addEventListener(USER_PREFS_CHANGE_EVENT, syncMotionClass);

    return () => {
      window.removeEventListener(USER_PREFS_CHANGE_EVENT, syncMotionClass);
      document.body.classList.remove("playful-motion-disabled");
    };
  }, []);

  return (
    <div className={isLandingRoute ? "h-[100dvh] overflow-hidden" : "min-h-screen pb-20"}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/settings" element={<SettingsPage />} />
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
      <ClickCheerOverlay />
      <BottomBar />
    </div>
  );
}

function App() {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
}

export default App;
