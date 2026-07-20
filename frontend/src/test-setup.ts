import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement scrollIntoView — stub it so components that call it
// (e.g. the search-suggestion-click row-scroll behavior, Task 13) don't throw.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
