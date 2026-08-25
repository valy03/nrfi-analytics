import { useState } from "react";
import type { Pitcher } from "../api/types";

// MLB's own static photo CDN, keyed by the same player id our API already
// returns — verified live (200, image/jpeg), and it already degrades to a
// generic silhouette server-side for an id with no photo on file, same
// spirit as sourcing team logos from MLB's own static CDN.
function headshotUrl(pitcherId: number): string {
  return (
    "https://img.mlbstatic.com/mlb-photos/image/upload/" +
    "w_213,d_people:generic:headshot:67:current.png,q_auto:best,f_auto/" +
    `v1/people/${pitcherId}/headshot/67/current`
  );
}

interface PitcherHeadshotProps {
  pitcher: Pitcher;
  size?: number;
}

export function PitcherHeadshot({ pitcher, size = 32 }: PitcherHeadshotProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className="flex shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground"
        style={{ width: size, height: size }}
        title={pitcher.full_name}
      >
        {pitcher.full_name.charAt(0)}
      </div>
    );
  }

  return (
    <img
      src={headshotUrl(pitcher.id)}
      alt={pitcher.full_name}
      width={size}
      height={size}
      className="shrink-0 rounded-full object-cover"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}
