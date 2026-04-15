import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { createBrowserRouter, RouterProvider } from "react-router-dom"
import "./index.css"
import { Home } from "./pages/Home"
import { Session } from "./pages/Session"
import { Join } from "./pages/Join"

const router = createBrowserRouter([
  { path: "/", element: <Home /> },
  { path: "/join/:code?", element: <Join /> },
  { path: "/s/:code", element: <Session /> },
])

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
