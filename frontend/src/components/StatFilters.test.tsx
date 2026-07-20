import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatFilters } from "./StatFilters";
import type { StatMins } from "@/lib/types";

const EMPTY: StatMins = { gp: null, goals: null, assists: null, points: null };

describe("StatFilters", () => {
  it("calls onChange with a number when a value is typed", async () => {
    const onChange = vi.fn();
    render(<StatFilters value={EMPTY} onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("GP≥"), "20");
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY, gp: 20 });
  });

  it("calls onChange with null when the field is cleared", async () => {
    const onChange = vi.fn();
    render(<StatFilters value={{ ...EMPTY, goals: 10 }} onChange={onChange} />);
    await userEvent.clear(screen.getByLabelText("G≥"));
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY, goals: null });
  });
});
