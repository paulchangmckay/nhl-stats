import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PositionToggle } from "./PositionToggle";
import { POSITION_COLORS } from "@/lib/positionColors";

describe("PositionToggle", () => {
  it("calls onChange with the position added when an inactive toggle is clicked", async () => {
    const onChange = vi.fn();
    render(<PositionToggle active={new Set()} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "C" }));
    expect(onChange).toHaveBeenCalledWith(new Set(["C"]));
  });

  it("calls onChange with the position removed when an active toggle is clicked", async () => {
    const onChange = vi.fn();
    render(<PositionToggle active={new Set(["C", "D"])} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "C" }));
    expect(onChange).toHaveBeenCalledWith(new Set(["D"]));
  });

  it("renders all five position buttons", () => {
    render(<PositionToggle active={new Set()} onChange={() => {}} />);
    ["C", "L", "R", "D", "G"].forEach((pos) => {
      expect(screen.getByRole("button", { name: pos })).toBeInTheDocument();
    });
  });

  it("applies the POSITION_COLORS toggleClass to each position button", () => {
    render(<PositionToggle active={new Set()} onChange={() => {}} />);
    (["C", "L", "R", "D", "G"] as const).forEach((pos) => {
      const button = screen.getByRole("button", { name: pos });
      const expectedClasses = POSITION_COLORS[pos].toggleClass.split(" ");
      expectedClasses.forEach((cls) => expect(button).toHaveClass(cls));
    });
  });
});
