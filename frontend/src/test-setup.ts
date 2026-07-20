import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement scrollIntoView — stub it so components that call it
// (e.g. the search-suggestion-click row-scroll behavior, Task 13) don't throw.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// jsdom doesn't implement ResizeObserver — cmdk's Command primitive (used by
// TeamPicker, Task 9) observes item sizes on mount and throws without it.
if (!window.ResizeObserver) {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
