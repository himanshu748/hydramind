import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import LandingPage from "./LandingPage";
import "./styles.css";

const currentPath = window.location.pathname.replace(/\/$/, "") || "/";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {currentPath === "/app" ? <App /> : <LandingPage />}
  </StrictMode>,
);
