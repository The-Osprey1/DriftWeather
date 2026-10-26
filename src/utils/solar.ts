/**
 * G4Cast Solar & Dark Mode Engine
 * Implements NOAA astronomical solar calculation and 3-way dark mode evaluation ("off", "on", "auto")
 */

import { DarkModeSetting } from '../types';

export function normalizeDarkMode(val: unknown): DarkModeSetting {
  if (typeof val === 'boolean') {
    return val ? 'on' : 'off';
  }
  if (typeof val === 'number') {
    return val === 1 ? 'on' : 'off';
  }
  if (typeof val === 'string') {
    const v = val.trim().toLowerCase();
    if (['on', 'true', '1', 'yes', 'dark'].includes(v)) return 'on';
    if (['auto', 'solar', 'automatic'].includes(v)) return 'auto';
    if (['off', 'false', '0', 'no', 'light'].includes(v)) return 'off';
  }
  return 'off';
}

/**
 * Computes astronomical sunrise and sunset in local minutes from midnight [0..1440)
 * using standard NOAA solar position equations.
 * Returns [sunrise_minutes, sunset_minutes] or null if polar night / polar day.
 */
export function calculateAstronomicalSolar(
  lat: number,
  lon: number,
  date: Date = new Date(),
  tzOffsetSeconds: number = -date.getTimezoneOffset() * 60
): [number | null, number | null] {
  const startOfYear = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const diff = date.getTime() - startOfYear.getTime();
  const dayOfYear = Math.floor(diff / (1000 * 60 * 60 * 24)) + 1;

  const gamma =
    ((2.0 * Math.PI) / 365.25) *
    (dayOfYear - 1 + (date.getUTCHours() - 12) / 24.0);

  const eqtime =
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(gamma) -
      0.032077 * Math.sin(gamma) -
      0.014615 * Math.cos(2 * gamma) -
      0.040849 * Math.sin(2 * gamma));

  const decl =
    0.006918 -
    0.399912 * Math.cos(gamma) +
    0.070257 * Math.sin(gamma) -
    0.006758 * Math.cos(2 * gamma) +
    0.000907 * Math.sin(2 * gamma) -
    0.002697 * Math.cos(3 * gamma) +
    0.00148 * Math.sin(3 * gamma);

  const latRad = (lat * Math.PI) / 180.0;
  const zenithRad = (90.833 * Math.PI) / 180.0;

  const num = Math.cos(zenithRad) - Math.sin(latRad) * Math.sin(decl);
  const denom = Math.cos(latRad) * Math.cos(decl);

  if (Math.abs(denom) < 1e-7) {
    return [null, null];
  }

  const cosHa = num / denom;
  if (cosHa >= 1.0) {
    return [null, null]; // Polar night
  } else if (cosHa <= -1.0) {
    return [-1, -1]; // Polar day
  }

  const ha = (Math.acos(cosHa) * 180.0) / Math.PI;

  const sunriseUtc = 720.0 - 4.0 * (lon + ha) - eqtime;
  const sunsetUtc = 720.0 - 4.0 * (lon - ha) - eqtime;

  const tzOffsetMin = tzOffsetSeconds / 60.0;
  const sunriseLocal = (sunriseUtc + tzOffsetMin + 1440.0) % 1440.0;
  const sunsetLocal = (sunsetUtc + tzOffsetMin + 1440.0) % 1440.0;

  return [sunriseLocal, sunsetLocal];
}

export function evaluateDarkMode(
  mode: DarkModeSetting,
  sunriseTimestamp?: number,
  sunsetTimestamp?: number,
  lat: number = 33.963,
  lon: number = -117.564,
  date: Date = new Date()
): boolean {
  const normMode = normalizeDarkMode(mode);
  if (normMode === 'on') return true;
  if (normMode === 'off') return false;

  // Auto mode: evaluate solar schedule
  const localMinutes = date.getHours() * 60 + date.getMinutes();

  let srMin: number | null = null;
  let ssMin: number | null = null;

  if (sunriseTimestamp && sunsetTimestamp) {
    const srDate = new Date(sunriseTimestamp * 1000);
    const ssDate = new Date(sunsetTimestamp * 1000);
    srMin = srDate.getHours() * 60 + srDate.getMinutes();
    ssMin = ssDate.getHours() * 60 + ssDate.getMinutes();
  }

  if (srMin === null || ssMin === null || srMin === ssMin) {
    const [astroSr, astroSs] = calculateAstronomicalSolar(lat, lon, date);
    if (astroSr === null || astroSs === null) return true; // Polar night -> dark
    if (astroSr === -1 || astroSs === -1) return false; // Polar day -> light
    srMin = Math.round(astroSr);
    ssMin = Math.round(astroSs);
  }

  // Check if current time is within day
  let isDay: boolean;
  if (srMin <= ssMin) {
    isDay = localMinutes >= srMin && localMinutes < ssMin;
  } else {
    isDay = localMinutes >= srMin || localMinutes < ssMin;
  }

  // Dark mode is ON when it is night
  return !isDay;
}

export function formatSolarSummary(
  sunriseTimestamp?: number,
  sunsetTimestamp?: number,
  lat: number = 33.963,
  lon: number = -117.564
): string {
  if (sunriseTimestamp && sunsetTimestamp) {
    const sr = new Date(sunriseTimestamp * 1000);
    const ss = new Date(sunsetTimestamp * 1000);
    const fmt = (d: Date) =>
      d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    return `Sunrise ${fmt(sr)}, Sunset ${fmt(ss)}`;
  }

  const [srMin, ssMin] = calculateAstronomicalSolar(lat, lon);
  if (srMin !== null && ssMin !== null && srMin >= 0 && ssMin >= 0) {
    const srH = Math.floor(srMin / 60);
    const srM = Math.floor(srMin % 60);
    const ssH = Math.floor(ssMin / 60);
    const ssM = Math.floor(ssMin % 60);
    return `Sunrise ${String(srH).padStart(2, '0')}:${String(srM).padStart(2, '0')}, Sunset ${String(ssH).padStart(2, '0')}:${String(ssM).padStart(2, '0')} (Solar)`;
  }

  return 'Sunrise 06:42 AM, Sunset 06:18 PM';
}
