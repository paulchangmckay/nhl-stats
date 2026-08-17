import { describe, it, expect } from "vitest";
import { buildHeroGradient } from "./heroGradient";
import { teamColors } from "./teamBranding";

describe("buildHeroGradient", () => {
  it("builds a 135deg linear-gradient from the fixed team-color stops", () => {
    const gradient = buildHeroGradient();
    expect(gradient.startsWith("linear-gradient(135deg,")).toBe(true);
    expect(gradient).toContain(teamColors("COL")!.primary);
    expect(gradient).toContain(teamColors("VGK")!.primary);
    expect(gradient).toContain(teamColors("TOR")!.primary);
  });
});
