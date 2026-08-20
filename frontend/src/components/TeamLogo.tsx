import { useState } from "react";
import type { Team } from "../api/types";

// MLB's own static asset CDN, keyed by the same team id our API already
// returns — verified live (200, image/svg+xml) rather than assumed.
function logoUrl(teamId: number): string {
  return `https://www.mlbstatic.com/team-logos/${teamId}.svg`;
}

interface TeamLogoProps {
  team: Team;
  size?: number;
}

export function TeamLogo({ team, size = 40 }: TeamLogoProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className="flex items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-500"
        style={{ width: size, height: size }}
        title={team.name}
      >
        {team.abbreviation}
      </div>
    );
  }

  return (
    <img
      src={logoUrl(team.id)}
      alt={`${team.name} logo`}
      width={size}
      height={size}
      className="object-contain"
      onError={() => setFailed(true)}
    />
  );
}
