export interface WeatherSettings {
  city: string;
  display_text: string;
  api_key: string;
  use_metric: boolean;
  use_kcno: boolean;
  kcno_station: string;
  use_avg_temp: boolean;
  update_interval_minutes: number;
}

export type LayoutStyle = 'classic' | 'widgets' | 'dualtone' | 'minimalist';
export type HeroSize = 'compact' | 'standard' | 'large';
export type DarkModeSetting = 'off' | 'on' | 'auto';

export interface DisplaySettings {
  use_24h_format: boolean;
  dark_mode: DarkModeSetting;
  layout_style: LayoutStyle;
  hero_size: HeroSize;
  rotation: 0 | 180;
  full_refresh_cycles: number;
  deep_purge_hour: number;
  is_dark?: boolean;
  solar_summary?: string;
}

export interface QuietHoursSettings {
  enabled: boolean;
  start_time: string;
  end_time: string;
  allow_severe_alerts: boolean;
}

export interface NetworkSettings {
  watchdog_enabled: boolean;
  ping_host: string;
  check_interval_seconds: number;
  max_reconnect_attempts: number;
}

export interface Settings {
  weather: WeatherSettings;
  display: DisplaySettings;
  quiet_hours: QuietHoursSettings;
  network: NetworkSettings;
  web: {
    port: number;
    host: string;
  };
  version: string;
}

export interface HourlyForecast {
  time: string; // "14:00" or "2 PM"
  timestamp: number;
  temp: number;
  pop: number; // Probability of precipitation (0-100)
  icon: string;
  condition: string;
}

export interface DailyForecast {
  dayName: string; // "Tue", "Wed"
  minTemp: number;
  maxTemp: number;
  pop: number;
  icon: string;
  condition: string;
}

export interface WeatherData {
  city: string;
  country: string;
  currentTemp: number;
  highTemp: number;
  lowTemp: number;
  condition: string;
  description: string;
  humidity: number;
  windSpeed: number; // mph or km/h
  windDirection: string;
  uvi: number;
  pressure: number;
  sunriseTime: string;
  sunsetTime: string;
  sunriseTimestamp: number;
  sunsetTimestamp: number;
  lat: number;
  lon: number;
  aqiValue: number;
  aqiCategory: 'Good' | 'Moderate' | 'Unhealthy' | 'Hazardous';
  kcnoObservation?: {
    station: string;
    temp: number;
    humidity: number;
    wind: string;
    rawText: string;
    timestamp: string;
  };
  hourly: HourlyForecast[];
  daily: DailyForecast[];
  alertBanner?: {
    active: boolean;
    title: string;
    severity: string;
  } | null;
  lastUpdated: string;
}

export interface DiagnosticsInfo {
  system: {
    cpu_temp_c: number;
    cpu_temp_f: number;
    uptime: string;
    memory: { used_mb: number; total_mb: number; percent: number };
    disk: { free_gb: number; percent: number };
    version: string;
  };
  network: {
    is_online: boolean;
    signal_percent: number;
    signal_dbm: number;
    ssid: string;
    ip_address: string;
  };
  weather: {
    last_sync_time: string;
    api_status: string;
  };
  display: {
    refresh_count: number;
    last_refresh: string;
  };
}
