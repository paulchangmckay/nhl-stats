import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PlaceholderPage from "./PlaceholderPage";

describe("PlaceholderPage", () => {
  it("renders the given title and a coming-soon message", () => {
    render(<PlaceholderPage title="Teams" />);
    expect(screen.getByRole("heading", { name: "Teams" })).toBeInTheDocument();
    expect(screen.getByText("Coming soon.")).toBeInTheDocument();
  });
});
