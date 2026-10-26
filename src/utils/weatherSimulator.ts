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
    rotation: 0,
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

  // Find city in database
  const matchedCity = CITIES_DATABASE.find(
    (c) =>
      c.name.toLowerCase() === cityName.toLowerCase() ||
      settings.weather.city.toLowerCase().includes(c.name.toLowerCase())
  );

  let baseF = 74;
  let highF = 79;
  let lowF = 56;
  let condition = 'Sunny';
  let description = 'Clear sky, gentle breeze';
  let humidity = 42;
  let windSpeedF = 9;
  let windDirection = 'WSW';
  let heroIcon = '01d';
  let aqiVal = 34;

  if (matchedCity) {
    lat = matchedCity.lat;
    lon = matchedCity.lon;
    const nameLower = matchedCity.name.toLowerCase();
    if (nameLower === 'seattle') {
      baseF = 54;
      highF = 58;
      lowF = 46;
      condition = 'Rain Showers';
      description = 'Light rain and overcast';
      humidity = 78;
      windSpeedF = 11;
      windDirection = 'SSW';
      heroIcon = '10d';
      aqiVal = 22;
    } else if (nameLower === 'london') {
      baseF = 57;
      highF = 62;
      lowF = 48;
      condition = 'Overcast';
      description = 'Cloudy with drizzle';
      humidity = 82;
      windSpeedF = 10;
      windDirection = 'W';
      heroIcon = '04d';
      aqiVal = 28;
    } else if (nameLower === 'miami') {
      baseF = 84;
      highF = 88;
      lowF = 76;
      condition = 'Partly Cloudy';
      description = 'Warm, ocean breeze';
      humidity = 74;
      windSpeedF = 14;
      windDirection = 'ENE';
      heroIcon = '02d';
      aqiVal = 31;
    } else if (nameLower === 'new york') {
      baseF = 62;
      highF = 67;
      lowF = 50;
      condition = 'Mostly Clear';
      description = 'Fair, mild afternoon';
      humidity = 55;
      windSpeedF = 12;
      windDirection = 'NW';
      heroIcon = '01d';
      aqiVal = 44;
    } else if (nameLower === 'chicago') {
      baseF = 52;
      highF = 56;
      lowF = 42;
      condition = 'Breezy';
      description = 'Scattered clouds, fresh wind';
      humidity = 48;
      windSpeedF = 18;
      windDirection = 'NNE';
      heroIcon = '03d';
      aqiVal = 38;
    } else if (nameLower === 'tokyo') {
      baseF = 68;
      highF = 72;
      lowF = 58;
      condition = 'Clear';
      description = 'Clear autumn sky';
      humidity = 52;
      windSpeedF = 8;
      windDirection = 'E';
      heroIcon = '01d';
      aqiVal = 35;
    }
  }

  const currentTemp = isMetric ? Math.round(((baseF - 32) * 5) / 9) : baseF;
  const highTemp = isMetric ? Math.round(((highF - 32) * 5) / 9) : highF;
  const lowTemp = isMetric ? Math.round(((lowF - 32) * 5) / 9) : lowF;

  // Sunrise at ~6:45 AM, Sunset at ~6:15 PM today
  const srDate = new Date(now);
  srDate.setHours(6, 45, 0, 0);
  const ssDate = new Date(now);
  ssDate.setHours(18, 15, 0, 0);

  // Hourly curve (8 intervals of 3 hours)
  const hourlyOffsets = [-5, 0, 4, 3, -1, -7, -12, -14];
  const hourlyCurveF = hourlyOffsets.map((offset) => baseF + offset);
  const basePops = condition.includes('Rain') ? [40, 60, 50, 40, 30, 20, 10, 10] : [0, 5, 0, 10, 0, 0, 0, 0];

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
      pop: basePops[i] ?? 0,
      icon: isDay ? heroIcon : '01n',
      condition: condition,
    };
  });

  // Daily forecast (4 days)
  const daysOfWeek = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const dailyHighOffsets = [2, 4, 0, -3];
  const dailyLowOffsets = [-17, -15, -19, -22];

  const daily: WeatherData['daily'] = dailyHighOffsets.map((off, idx) => {
    const dh = baseF + off;
    const dl = baseF + dailyLowOffsets[idx];
    const dDate = new Date(now.getTime() + (idx + 1) * 24 * 3600 * 1000);
    return {
      dayName: daysOfWeek[dDate.getDay()],
      maxTemp: isMetric ? Math.round(((dh - 32) * 5) / 9) : dh,
      minTemp: isMetric ? Math.round(((dl - 32) * 5) / 9) : dl,
      pop: condition.includes('Rain') ? 50 - idx * 10 : (idx === 1 ? 15 : 0),
      icon: heroIcon,
      condition: condition,
    };
  });

  const aqiCat: 'Good' | 'Moderate' | 'Unhealthy' | 'Hazardous' =
    aqiVal <= 50 ? 'Good' : aqiVal <= 100 ? 'Moderate' : 'Unhealthy';

  return {
    city: cityName.toUpperCase(),
    country: matchedCity ? matchedCity.country : 'US',
    currentTemp,
    highTemp,
    lowTemp,
    condition,
    description,
    humidity,
    windSpeed: isMetric ? Math.round(windSpeedF * 1.609) : windSpeedF,
    windDirection,
    uvi: 6,
    pressure: 1014,
    sunriseTime: '06:45 AM',
    sunsetTime: '06:15 PM',
    sunriseTimestamp: Math.floor(srDate.getTime() / 1000),
    sunsetTimestamp: Math.floor(ssDate.getTime() / 1000),
    lat,
    lon,
    aqiValue: aqiVal,
    aqiCategory: aqiCat,
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
