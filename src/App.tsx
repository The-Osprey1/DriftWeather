import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Settings, WeatherData, DiagnosticsInfo } from './types';
import {
  DEFAULT_SETTINGS,
  generateWeatherData,
  getMockDiagnostics,
} from './utils/weatherSimulator';
import { evaluateDarkMode, formatSolarSummary } from './utils/solar';
import { EPaperRenderer, EPaperRendererRef } from './components/EPaperRenderer';
import { ControlPanel } from './components/ControlPanel';

export function App() {
  // Load settings from localStorage or fallback to defaults
  const [settings, setSettings] = useState<Settings>(() => {
    try {
      const saved = localStorage.getItem('g4cast_settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          ...DEFAULT_SETTINGS,
          ...parsed,
          weather: { ...DEFAULT_SETTINGS.weather, ...(parsed.weather || {}) },
          display: { ...DEFAULT_SETTINGS.display, ...(parsed.display || {}), rotation: 0 },
          quiet_hours: { ...DEFAULT_SETTINGS.quiet_hours, ...(parsed.quiet_hours || {}) },
          network: { ...DEFAULT_SETTINGS.network, ...(parsed.network || {}) },
        };
      }
    } catch {
      // Fall through
    }
    return DEFAULT_SETTINGS;
  });

  const [refreshCount, setRefreshCount] = useState<number>(() => {
    const val = localStorage.getItem('g4cast_refresh_count');
    return val ? parseInt(val, 10) : 14;
  });

  const [simulatedAlertTitle, setSimulatedAlertTitle] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string>('');
  const [isToastError, setIsToastError] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<boolean>(false);
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [lastSyncMinutesAgo, setLastSyncMinutesAgo] = useState<number>(0);

  const epaperRef = useRef<EPaperRendererRef | null>(null);

  // Synchronize settings to localStorage
  const handleUpdateSettings = (newSettings: Settings) => {
    setSettings(newSettings);
    try {
      localStorage.setItem('g4cast_settings', JSON.stringify(newSettings));
    } catch {
      // Ignore
    }
  };

  // Weather data generated based on current settings and alerts
  const weather: WeatherData = useMemo(() => {
    return generateWeatherData(settings, simulatedAlertTitle);
  }, [settings, simulatedAlertTitle]);

  // Diagnostics information
  const diagnostics: DiagnosticsInfo = useMemo(() => {
    return getMockDiagnostics(refreshCount);
  }, [refreshCount]);

  // Dark mode calculation (evaluates off / on / auto solar)
  const isDarkEffective = useMemo(() => {
    return evaluateDarkMode(
      settings.display.dark_mode,
      weather.sunriseTimestamp,
      weather.sunsetTimestamp,
      weather.lat,
      weather.lon
    );
  }, [
    settings.display.dark_mode,
    weather.sunriseTimestamp,
    weather.sunsetTimestamp,
    weather.lat,
    weather.lon,
  ]);

  const solarSummary = useMemo(() => {
    return formatSolarSummary(
      weather.sunriseTimestamp,
      weather.sunsetTimestamp,
      weather.lat,
      weather.lon
    );
  }, [weather.sunriseTimestamp, weather.sunsetTimestamp, weather.lat, weather.lon]);

  // Toast feedback helper
  const displayToast = (msg: string, isError: boolean = false) => {
    setToastMessage(msg);
    setIsToastError(isError);
    setShowToast(true);
    setTimeout(() => {
      setShowToast(false);
    }, 3200);
  };

  // Trigger e-paper display refresh
  const triggerRefresh = () => {
    if (epaperRef.current) {
      epaperRef.current.triggerRefreshAnimation(false);
      const newCount = refreshCount + 1;
      setRefreshCount(newCount);
      localStorage.setItem('g4cast_refresh_count', String(newCount));
      setLastSyncMinutesAgo(0);
      displayToast('Display refreshed successfully.');
    }
  };

  // Trigger e-paper deep clean cycle (clears ghosting)
  const triggerClean = () => {
    if (epaperRef.current) {
      epaperRef.current.triggerRefreshAnimation(true);
      const newCount = refreshCount + 1;
      setRefreshCount(newCount);
      localStorage.setItem('g4cast_refresh_count', String(newCount));
      displayToast('Screen cleaned and refreshed.');
    }
  };

  // Download rendered PNG
  const downloadPreviewPng = () => {
    if (epaperRef.current) {
      const dataUrl = epaperRef.current.getCanvasDataUrl();
      if (dataUrl) {
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = `g4cast_epaper_${settings.display.layout_style}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        displayToast('800x480 e-paper bitmap downloaded');
      }
    }
  };

  // Alert simulation triggers
  const handleSimulateAlert = (title: string) => {
    setSimulatedAlertTitle(title);
    triggerRefresh();
    displayToast(`Simulated alert set: ${title}`);
  };

  const handleClearAlert = () => {
    setSimulatedAlertTitle(null);
    triggerRefresh();
    displayToast('Simulated alert cleared');
  };

  // Wi-Fi watchdog reconnect trigger
  const handleReconnectWifi = () => {
    displayToast('Reconnection sequence initiated...');
    setIsOnline(false);
    setTimeout(() => {
      setIsOnline(true);
      displayToast('Wi-Fi link re-established. Signal optimal.');
    }, 1800);
  };

  // Ensure legacy rotation in localStorage is reset so preview is never upside down
  useEffect(() => {
    try {
      localStorage.removeItem('g4cast_rotation_explicit');
      const saved = localStorage.getItem('g4cast_settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.display?.rotation !== 0) {
          parsed.display = { ...parsed.display, rotation: 0 };
          localStorage.setItem('g4cast_settings', JSON.stringify(parsed));
          setSettings((prev) => ({
            ...prev,
            display: { ...prev.display, rotation: 0 },
          }));
        }
      }
    } catch {
      // Ignore
    }
  }, []);

  // Update minute timer for sync age
  useEffect(() => {
    const timer = setInterval(() => {
      setLastSyncMinutesAgo((prev) => prev + 1);
    }, 60000);
    return () => clearInterval(timer);
  }, []);

  const cityDisplay = settings.weather.display_text || settings.weather.city || 'Eastvale';
  const ageString = lastSyncMinutesAgo === 0 ? 'just now' : `${lastSyncMinutesAgo}m ago`;

  return (
    <div className="container">
      {/* HEADER */}
      <header>
        <div className="brand-row">
          <div className="flex items-center gap-3">
            <h1>G4Cast</h1>
            <span className="text-xs px-2 py-0.5 rounded bg-[#21262d] text-[#8b949e] border border-[#30363d] font-mono">
              800×480 E-Paper
            </span>
          </div>

          <div className="status-badge" id="headerStatus">
            <span
              className={`status-dot ${!isOnline ? 'offline' : ''}`}
              id="statusDot"
            />
            <span id="statusText">
              {isOnline
                ? `Online • ${cityDisplay} • Sync ${ageString}`
                : 'Reconnecting Wi-Fi...'}
            </span>
          </div>
        </div>
      </header>

      {/* LIVE DISPLAY PREVIEW */}
      <section className="card">
        <div className="card-title justify-between">
          <div className="flex items-center gap-2">
            <span>Display Preview</span>
            <span className="text-xs text-[#8b949e] font-normal">
              (Waveshare 7.5&quot; V2 800×480 Monochrome Canvas)
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#8b949e]">
            <span>Visual Mode:</span>
            <span className="text-[#f0f6fc] font-semibold">
              {settings.display.dark_mode === 'auto'
                ? `Auto (${isDarkEffective ? '🌙 Night' : '☀️ Day'})`
                : settings.display.dark_mode === 'on'
                ? 'Dark (Inverted)'
                : 'Light (Paper)'}
            </span>
          </div>
        </div>

        <div className="preview-container">
          <EPaperRenderer
            ref={epaperRef}
            settings={settings}
            weather={weather}
            isDarkEffective={isDarkEffective}
          />
        </div>

        <div className="btn-group justify-between items-center">
          <div className="flex gap-2.5 flex-wrap">
            <button id="btnRefresh" className="btn-primary" onClick={triggerRefresh}>
              <span>↻</span> Refresh Display
            </button>
            <button id="btnClean" className="btn-secondary" onClick={triggerClean}>
              <span>✨</span> Clean Display
            </button>
            <button className="btn-secondary" onClick={downloadPreviewPng}>
              <span>⬇️</span> Download Bitmap PNG
            </button>
          </div>

          <div className="text-xs text-[#8b949e] italic font-sans hidden sm:block">
            {solarSummary}
          </div>
        </div>
      </section>

      {/* CONFIGURATION SECTIONS */}
      <ControlPanel
        settings={{
          ...settings,
          display: {
            ...settings.display,
            is_dark: isDarkEffective,
            solar_summary: solarSummary,
          },
        }}
        onUpdateSettings={handleUpdateSettings}
        diagnostics={diagnostics}
        onSimulateAlert={handleSimulateAlert}
        onClearAlert={handleClearAlert}
        onReconnectWifi={handleReconnectWifi}
        onShowToast={displayToast}
      />

      {/* TOAST NOTIFICATION */}
      <div
        id="toast"
        className={`${showToast ? 'show' : ''} ${isToastError ? 'error' : ''}`}
      >
        {toastMessage}
      </div>
    </div>
  );
}

export default App;
