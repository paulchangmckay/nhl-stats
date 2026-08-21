export const POSITION_COLORS: Record<
  "C" | "L" | "R" | "D" | "G",
  { toggleClass: string; badgeClass: string }
> = {
  C: {
    toggleClass: "text-green-500 aria-pressed:bg-green-500 aria-pressed:text-background",
    badgeClass: "border-green-500/40 bg-green-500/10 text-green-500",
  },
  L: {
    toggleClass: "text-blue-400 aria-pressed:bg-blue-400 aria-pressed:text-background",
    badgeClass: "border-blue-400/40 bg-blue-400/10 text-blue-400",
  },
  R: {
    toggleClass: "text-sky-300 aria-pressed:bg-sky-300 aria-pressed:text-background",
    badgeClass: "border-sky-300/40 bg-sky-300/10 text-sky-300",
  },
  D: {
    toggleClass: "text-purple-300 aria-pressed:bg-purple-300 aria-pressed:text-background",
    badgeClass: "border-purple-300/40 bg-purple-300/10 text-purple-300",
  },
  G: {
    toggleClass: "text-orange-400 aria-pressed:bg-orange-400 aria-pressed:text-background",
    badgeClass: "border-orange-400/40 bg-orange-400/10 text-orange-400",
  },
};
