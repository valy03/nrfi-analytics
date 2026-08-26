import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
  isActive: (pathname: string) => boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    isActive: (path) => path === "/" || path.startsWith("/games/"),
  },
  { to: "/history", label: "History", isActive: (path) => path.startsWith("/history") },
  { to: "/analytics", label: "Analytics", isActive: (path) => path.startsWith("/analytics") },
  { to: "/about", label: "About", isActive: (path) => path.startsWith("/about") },
];

export function NavBar() {
  const location = useLocation();
  // The logo block + all four links never fit a phone-width viewport as one
  // row (needs ~550px), so below md: they collapse into this toggle instead
  // of silently overflowing the page horizontally.
  const [open, setOpen] = useState(false);

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6">
        <Link to="/" className="flex items-center gap-2.5" onClick={() => setOpen(false)}>
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary font-mono text-sm font-bold text-primary-foreground">
            0
          </span>
          <span className="leading-tight">
            <span className="block text-sm font-bold text-foreground">NRFI Analytics</span>
            <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              No Run First Inning
            </span>
          </span>
        </Link>

        <nav className="hidden gap-1 md:flex">
          {NAV_ITEMS.map((item) => {
            const active = item.isActive(location.pathname);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          className="flex size-9 items-center justify-center rounded-md text-muted-foreground hover:text-foreground md:hidden"
        >
          {open ? <X className="size-5" aria-hidden="true" /> : <Menu className="size-5" aria-hidden="true" />}
        </button>
      </div>

      {open && (
        <nav className="border-t border-border px-4 py-2 md:hidden">
          <div className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const active = item.isActive(location.pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className={`rounded-md px-3 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </header>
  );
}
