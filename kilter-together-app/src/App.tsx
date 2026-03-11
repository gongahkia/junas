import { Suspense, lazy, useState, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import BottomBar from "./components/BottomBar";
import ClickCheerOverlay from "./components/ClickCheerOverlay";
import { ToastProvider } from "./components/ui/toast";
import { useErrorToast } from "./hooks/use-toast";
import { loadUserPrefs, USER_PREFS_CHANGE_EVENT } from "./lib/user-prefs";
import type { Board } from "./types";
import "./App.css";

const AboutPage = lazy(() => import("./components/AboutPage"));
const BoardSelector = lazy(() => import("./components/BoardSelector"));
const ClimbView = lazy(() => import("./components/ClimbView"));
const LandingPage = lazy(() => import("./components/LandingPage"));
const ProviderSoloPage = lazy(() => import("./components/ProviderSoloPage"));
const RoomCreatePage = lazy(() => import("./components/RoomCreatePage"));
const RoomDiscoveryPage = lazy(() => import("./components/RoomDiscoveryPage"));
const RoomJoinPage = lazy(() => import("./components/RoomJoinPage"));
const RoomView = lazy(() => import("./components/RoomView"));
const SettingsPage = lazy(() => import("./components/SettingsPage"));

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
    <div
      className={
        isLandingRoute ? "min-h-[100dvh] overflow-x-hidden" : "min-h-screen pb-20"
      }
    >
      <Suspense fallback={<div className="min-h-[40vh]" aria-hidden="true" />}>
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
          <Route path="/solo/providers/:providerId" element={<ProviderSoloPage />} />
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
      </Suspense>
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
