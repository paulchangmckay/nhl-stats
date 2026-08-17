import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { MenuIcon } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/players", label: "Players", end: false },
  { to: "/teams", label: "Teams", end: false },
  { to: "/top-players", label: "Top Players", end: false },
  { to: "/betting", label: "Betting", end: false },
] as const;

function navLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "text-sm font-medium transition-colors hover:text-foreground",
    isActive ? "text-foreground" : "text-muted-foreground"
  );
}

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    function updateHeaderHeight() {
      const header = document.querySelector("[data-header]");
      if (header) {
        document.documentElement.style.setProperty(
          "--header-height",
          `${header.getBoundingClientRect().height}px`
        );
      }
    }
    updateHeaderHeight();
    window.addEventListener("resize", updateHeaderHeight);
    return () => window.removeEventListener("resize", updateHeaderHeight);
  }, []);

  return (
    <header
      data-header
      className="sticky top-0 z-40 flex items-center justify-between border-b border-border bg-card px-4 py-3"
    >
      <span className="text-base font-semibold">NHL Stats</span>

      <nav className="hidden items-center gap-6 md:flex">
        {NAV_LINKS.map(({ to, label, end }) => (
          <NavLink key={to} to={to} end={end} className={navLinkClass}>
            {label}
          </NavLink>
        ))}
      </nav>

      <button
        type="button"
        aria-label="Open menu"
        className="md:hidden"
        onClick={() => setMobileOpen(true)}
      >
        <MenuIcon />
      </button>

      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogContent>
          <DialogTitle>Menu</DialogTitle>
          <nav className="flex flex-col gap-4 pt-2">
            {NAV_LINKS.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={navLinkClass}
                onClick={() => setMobileOpen(false)}
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </DialogContent>
      </Dialog>
    </header>
  );
}
