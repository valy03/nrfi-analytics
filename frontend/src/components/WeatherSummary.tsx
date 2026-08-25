import { Cloud, CloudFog, CloudLightning, CloudRain, Snowflake, Sun, Thermometer } from "lucide-react";
import type { Weather } from "../api/types";

const CONDITION_ICONS: Record<string, typeof Sun> = {
  Clear: Sun,
  Clouds: Cloud,
  Rain: CloudRain,
  Drizzle: CloudRain,
  Thunderstorm: CloudLightning,
  Snow: Snowflake,
  Mist: CloudFog,
  Fog: CloudFog,
};

interface WeatherSummaryProps {
  weather: Weather | null;
}

export function WeatherSummary({ weather }: WeatherSummaryProps) {
  if (!weather) {
    return <span className="text-xs text-muted-foreground">Weather unavailable</span>;
  }

  const Icon = CONDITION_ICONS[weather.conditions] ?? Thermometer;

  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Icon className="size-3.5" aria-hidden="true" />
      {Math.round(weather.temp_f)}°F, {weather.conditions.toLowerCase()},{" "}
      {Math.round(weather.wind_mph)} mph wind
    </span>
  );
}
