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

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6">
        <Link to="/" className="flex items-center gap-2.5">
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
        <nav className="flex gap-1">
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
      </div>
    </header>
  );
}
