import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

// Small hand-rolled outline icons (20x20, stroke-based) — wireframes.md
// asks for an outline set (Tabler) for a "professional analytics
// platform" feel; these approximate that without a new icon-library
// dependency for four glyphs.
function DashboardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="10" width="3.5" height="7" rx="0.5" />
      <rect x="8.25" y="6" width="3.5" height="11" rx="0.5" />
      <rect x="13.5" y="3" width="3.5" height="14" rx="0.5" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="4" width="14" height="13" rx="1.5" />
      <line x1="3" y1="8" x2="17" y2="8" />
      <line x1="7" y1="2" x2="7" y2="5.5" />
      <line x1="13" y1="2" x2="13" y2="5.5" />
    </svg>
  );
}

function AnalyticsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3,14 8,8 12,11 17,4" />
      <polyline points="12,4 17,4 17,9" />
    </svg>
  );
}

function AboutIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="10" cy="10" r="7.25" />
      <line x1="10" y1="9" x2="10" y2="14" strokeLinecap="round" />
      <circle cx="10" cy="6.25" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  isActive: (pathname: string) => boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    icon: <DashboardIcon />,
    isActive: (path) => path === "/" || path.startsWith("/games/"),
  },
  {
    to: "/history",
    label: "History",
    icon: <HistoryIcon />,
    isActive: (path) => path.startsWith("/history"),
  },
  {
    to: "/analytics",
    label: "Analytics",
    icon: <AnalyticsIcon />,
    isActive: (path) => path.startsWith("/analytics"),
  },
  {
    to: "/about",
    label: "About",
    icon: <AboutIcon />,
    isActive: (path) => path.startsWith("/about"),
  },
];

export function NavBar() {
  const location = useLocation();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link to="/" className="text-base font-bold text-slate-900">
          NRFI Analytics
        </Link>
        <nav className="flex gap-1">
          {NAV_ITEMS.map((item) => {
            const active = item.isActive(location.pathname);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-teal-50 text-teal-700"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
