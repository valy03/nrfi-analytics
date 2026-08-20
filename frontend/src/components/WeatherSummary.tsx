import type { Weather } from "../api/types";

const CONDITION_ICONS: Record<string, string> = {
  Clear: "☀️",
  Clouds: "☁️",
  Rain: "🌧️",
  Drizzle: "🌦️",
  Thunderstorm: "⛈️",
  Snow: "❄️",
  Mist: "🌫️",
  Fog: "🌫️",
};

interface WeatherSummaryProps {
  weather: Weather | null;
}

export function WeatherSummary({ weather }: WeatherSummaryProps) {
  if (!weather) {
    return <span className="text-xs text-slate-400">Weather unavailable</span>;
  }

  const icon = CONDITION_ICONS[weather.conditions] ?? "🌡️";

  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-500">
      <span aria-hidden="true">{icon}</span>
      {Math.round(weather.temp_f)}°F, {weather.conditions.toLowerCase()},{" "}
      {Math.round(weather.wind_mph)} mph wind
    </span>
  );
}
