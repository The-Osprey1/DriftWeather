import { Settings, WeatherData, DiagnosticsInfo } from '../types';

export const DEFAULT_SETTINGS: Settings = {
  weather: {
    city: 'Eastvale, US',
    display_text: 'Eastvale',
    api_key: '03e1c360794791f241cdd9630f0df7fb',
    use_metric: false,
    use_kcno: true,
    kcno_station: 'KCNO',
    use_avg_temp: false,
    update_interval_minutes: 30,
  },
  display: {
    use_24h_format: false,
    dark_mode: 'off',
    layout_style: 'classic',
    hero_size: 'standard',
    rotation: 180,
    full_refresh_cycles: 24,
    deep_purge_hour: 3,
  },
  quiet_hours: {
    enabled: true,
    start_time: '23:00',
    end_time: '06:00',
    allow_severe_alerts: true,
  },
  network: {
    watchdog_enabled: true,
    ping_host: '1.1.1.1',
    check_interval_seconds: 30,
    max_reconnect_attempts: 3,
  },
  web: {
    port: 8080,
    host: '0.0.0.0',
  },
  version: '2.1.0',
};

export const CITIES_DATABASE = [
  { name: 'Eastvale', state: 'CA', country: 'US', lat: 33.963, lon: -117.564 },
  { name: 'Corona', state: 'CA', country: 'US', lat: 33.8753, lon: -117.5664 },
  { name: 'Riverside', state: 'CA', country: 'US', lat: 33.9806, lon: -117.3755 },
  { name: 'Ontario', state: 'CA', country: 'US', lat: 34.0633, lon: -117.6509 },
  { name: 'Los Angeles', state: 'CA', country: 'US', lat: 34.0522, lon: -118.2437 },
  { name: 'San Francisco', state: 'CA', country: 'US', lat: 37.7749, lon: -122.4194 },
  { name: 'San Diego', state: 'CA', country: 'US', lat: 32.7157, lon: -117.1611 },
  { name: 'Seattle', state: 'WA', country: 'US', lat: 47.6062, lon: -122.3321 },
  { name: 'Denver', state: 'CO', country: 'US', lat: 39.7392, lon: -104.9903 },
  { name: 'Chicago', state: 'IL', country: 'US', lat: 41.8781, lon: -87.6298 },
  { name: 'New York', state: 'NY', country: 'US', lat: 40.7128, lon: -74.006 },
  { name: 'Austin', state: 'TX', country: 'US', lat: 30.2672, lon: -97.7431 },
  { name: 'Miami', state: 'FL', country: 'US', lat: 25.7617, lon: -80.1918 },
  { name: 'London', state: '', country: 'GB', lat: 51.5074, lon: -0.1278 },
  { name: 'Tokyo', state: '', country: 'JP', lat: 35.6762, lon: 139.6503 },
  { name: 'Paris', state: '', country: 'FR', lat: 48.8566, lon: 2.3522 },
  { name: 'Sydney', state: '', country: 'AU', lat: -33.8688, lon: 151.2093 },
];

export function generateWeatherData(
  settings: Settings,
  simulatedAlertTitle: string | null = null
): WeatherData {
  const isMetric = settings.weather.use_metric;
  const now = new Date();

  // Coordinates base
  let lat = 33.963;
  let lon = -117.564;
  const cityName = settings.weather.display_text || 'Eastvale';

  // Base temps for Eastvale / Southern California climate
  const baseF = 74;
  const highF = 79;
  const lowF = 56;

  const currentTemp = isMetric ? Math.round(((baseF - 32) * 5) / 9) : baseF;
  const highTemp = isMetric ? Math.round(((highF - 32) * 5) / 9) : highF;
  const lowTemp = isMetric ? Math.round(((lowF - 32) * 5) / 9) : lowF;

  // Sunrise at ~6:45 AM, Sunset at ~6:15 PM today
  const srDate = new Date(now);
  srDate.setHours(6, 45, 0, 0);
  const ssDate = new Date(now);
  ssDate.setHours(18, 15, 0, 0);

  // Hourly curve (8 intervals of 3 hours)
  const hourlyCurveF = [68, 74, 78, 77, 72, 65, 60, 58];
  const pops = [0, 5, 0, 10, 0, 0, 0, 0];

  const hourly: WeatherData['hourly'] = hourlyCurveF.map((tf, i) => {
    const hDate = new Date(now.getTime() + i * 3 * 3600 * 1000);
    const hourNum = hDate.getHours();
    const isDay = hourNum >= 6 && hourNum < 18;
    const timeLabel = settings.display.use_24h_format
      ? `${String(hourNum).padStart(2, '0')}:00`
      : `${hourNum % 12 || 12} ${hourNum >= 12 ? 'PM' : 'AM'}`;

    return {
      time: timeLabel,
      timestamp: Math.floor(hDate.getTime() / 1000),
      temp: isMetric ? Math.round(((tf - 32) * 5) / 9) : tf,
      pop: pops[i],
      icon: isDay ? '01d' : '01n',
      condition: 'Clear',
    };
  });

  // Daily forecast (4 days)
  const daysOfWeek = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const dailyHighsF = [81, 83, 78, 75];
  const dailyLowsF = [57, 59, 55, 52];
  const dailyIcons = ['01d', '02d', '03d', '01d'];
  const dailyPops = [0, 10, 20, 0];
  const dailyConds = ['Sunny', 'Partly Cloudy', 'Scattered Clouds', 'Sunny'];

  const daily: WeatherData['daily'] = dailyHighsF.map((dh, idx) => {
    const dDate = new Date(now.getTime() + (idx + 1) * 24 * 3600 * 1000);
    return {
      dayName: daysOfWeek[dDate.getDay()],
      maxTemp: isMetric ? Math.round(((dh - 32) * 5) / 9) : dh,
      minTemp: isMetric ? Math.round(((dailyLowsF[idx] - 32) * 5) / 9) : dailyLowsF[idx],
      pop: dailyPops[idx],
      icon: dailyIcons[idx],
      condition: dailyConds[idx],
    };
  });

  return {
    city: cityName.toUpperCase(),
    country: 'US',
    currentTemp,
    highTemp,
    lowTemp,
    condition: 'Sunny',
    description: 'Clear sky, gentle breeze',
    humidity: 42,
    windSpeed: isMetric ? 14 : 9,
    windDirection: 'WSW',
    uvi: 6,
    pressure: 1014,
    sunriseTime: '06:45 AM',
    sunsetTime: '06:15 PM',
    sunriseTimestamp: Math.floor(srDate.getTime() / 1000),
    sunsetTimestamp: Math.floor(ssDate.getTime() / 1000),
    lat,
    lon,
    aqiValue: 34,
    aqiCategory: 'Good',
    kcnoObservation: settings.weather.use_kcno
      ? {
          station: settings.weather.kcno_station || 'KCNO',
          temp: isMetric ? Math.round(((72 - 32) * 5) / 9) : 72,
          humidity: 44,
          wind: 'WSW 8 mph',
          rawText: 'METAR KCNO 261953Z 24007KT 10SM CLR 22/09 A3002 RMK AO2',
          timestamp: '19:53 UTC',
        }
      : undefined,
    hourly,
    daily,
    alertBanner: simulatedAlertTitle
      ? {
          active: true,
          title: simulatedAlertTitle,
          severity: 'Warning',
        }
      : null,
    lastUpdated: 'just now',
  };
}

export function getMockDiagnostics(refreshCount: number): DiagnosticsInfo {
  return {
    system: {
      cpu_temp_c: 43.8,
      cpu_temp_f: 110.8,
      uptime: '4 days, 18 hrs, 22 mins',
      memory: {
        used_mb: 184,
        total_mb: 512,
        percent: 36,
      },
      disk: {
        free_gb: 18.4,
        percent: 28,
      },
      version: '2.1.0',
    },
    network: {
      is_online: true,
      signal_percent: 88,
      signal_dbm: -58,
      ssid: 'Home_IoT_5G',
      ip_address: '192.168.1.65',
    },
    weather: {
      last_sync_time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      api_status: 'Operational (200 OK)',
    },
    display: {
      refresh_count: refreshCount,
      last_refresh: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    },
  };
}
