import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import App from "./App";
import Home from "./pages/Home";
import Players from "./pages/Players";
import Teams from "./pages/Teams";
import TeamPage from "./pages/TeamPage";
import TopPlayers from "./pages/TopPlayers";
import PlaceholderPage from "./pages/PlaceholderPage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Home />} />
          <Route path="players" element={<Players />} />
          <Route path="teams" element={<Teams />} />
          <Route path="teams/:teamId" element={<TeamPage />} />
          <Route path="top-players" element={<TopPlayers />} />
          <Route path="betting" element={<PlaceholderPage title="Betting" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
