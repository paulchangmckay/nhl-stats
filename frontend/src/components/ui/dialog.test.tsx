import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dialog, DialogContent, DialogTitle } from "./dialog";

describe("DialogContent", () => {
  it("is bounded to viewport height and scrolls internally when content overflows (issue #115)", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Test dialog</DialogTitle>
          <div>body content</div>
        </DialogContent>
      </Dialog>
    );

    const content = screen.getByText("body content").closest('[data-slot="dialog-content"]');
    expect(content).not.toBeNull();
    expect(content).toHaveClass("overflow-y-auto");
    expect(content?.className).toMatch(/max-h-\[calc\(100vh-2rem\)\]/);
  });
});
