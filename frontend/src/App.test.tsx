import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import App from "./App";

function renderApp(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<App />}>
          <Route index element={<div>home content</div>} />
          <Route path="players" element={<div>players content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("App shell", () => {
  it("renders the header brand alongside the matched route's content", () => {
    renderApp("/");
    expect(screen.getByText("NHL Stats")).toBeInTheDocument();
    expect(screen.getByText("home content")).toBeInTheDocument();
  });

  it("renders a different route's content via the Outlet", () => {
    renderApp("/players");
    expect(screen.getByText("players content")).toBeInTheDocument();
  });
});
