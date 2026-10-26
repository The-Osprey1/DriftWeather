import React, { useState } from 'react';
import { Settings, LayoutStyle, HeroSize, DarkModeSetting, DiagnosticsInfo } from '../types';
import { CITIES_DATABASE } from '../utils/weatherSimulator';

interface ControlPanelProps {
  settings: Settings;
  onUpdateSettings: (newSettings: Settings) => void;
  diagnostics: DiagnosticsInfo;
  onSimulateAlert: (title: string) => void;
  onClearAlert: () => void;
  onReconnectWifi: () => void;
  onShowToast: (msg: string, isError?: boolean) => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  settings,
  onUpdateSettings,
  diagnostics,
  onSimulateAlert,
  onClearAlert,
  onReconnectWifi,
  onShowToast,
}) => {
  const [activeTab, setActiveTab] = useState<
    'weather' | 'display' | 'customization' | 'schedule' | 'network' | 'diagnostics' | 'tools'
  >('weather');

  // Form states initialized from settings
  const [formData, setFormData] = useState<Settings>(settings);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<typeof CITIES_DATABASE>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [customAlertTitle, setCustomAlertTitle] = useState('');

  // Keep formData in sync if settings changes externally
  React.useEffect(() => {
    setFormData(settings);
  }, [settings]);

  const handleWeatherChange = <K extends keyof Settings['weather']>(
    key: K,
    val: Settings['weather'][K]
  ) => {
    setFormData((prev) => ({
      ...prev,
      weather: { ...prev.weather, [key]: val },
    }));
  };

  const handleDisplayChange = <K extends keyof Settings['display']>(
    key: K,
    val: Settings['display'][K]
  ) => {
    if (key === 'rotation') {
      try {
        localStorage.setItem('g4cast_rotation_explicit', 'true');
      } catch {
        // Ignore
      }
    }
    setFormData((prev) => {
      const updated = {
        ...prev,
        display: { ...prev.display, [key]: val },
      };
      onUpdateSettings(updated);
      return updated;
    });
  };

  const handleQuietChange = <K extends keyof Settings['quiet_hours']>(
    key: K,
    val: Settings['quiet_hours'][K]
  ) => {
    setFormData((prev) => ({
      ...prev,
      quiet_hours: { ...prev.quiet_hours, [key]: val },
    }));
  };

  const handleNetworkChange = <K extends keyof Settings['network']>(
    key: K,
    val: Settings['network'][K]
  ) => {
    setFormData((prev) => ({
      ...prev,
      network: { ...prev.network, [key]: val },
    }));
  };

  const saveSettings = () => {
    onUpdateSettings(formData);
    onShowToast('Settings saved successfully!');
  };

  const searchLocation = async () => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      onShowToast('Please enter a city name to search', true);
      return;
    }
    setIsSearching(true);
    try {
      // First check if OpenWeather API key is provided for live search
      if (formData.weather.api_key && formData.weather.api_key.length >= 20) {
        try {
          const res = await fetch(
            `https://api.openweathermap.org/geo/1.0/direct?q=${encodeURIComponent(
              searchQuery
            )}&limit=5&appid=${formData.weather.api_key}`
          );
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
              const mapped = data.map((item: any) => ({
                name: item.name,
                state: item.state || '',
                country: item.country || 'US',
                lat: Number(item.lat.toFixed(4)),
                lon: Number(item.lon.toFixed(4)),
              }));
              setSearchResults(mapped);
              setIsSearching(false);
              return;
            }
          }
        } catch {
          // Fall through to local database
        }
      }

      // Local fallback database
      const filtered = CITIES_DATABASE.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.state.toLowerCase().includes(q) ||
          c.country.toLowerCase().includes(q)
      );
      setSearchResults(filtered);
    } finally {
      setIsSearching(false);
    }
  };

  const selectLocation = (city: string, country: string, displayName: string) => {
    const full = country ? `${displayName}, ${country}` : displayName;
    setFormData((prev) => {
      const updated: Settings = {
        ...prev,
        weather: {
          ...prev.weather,
          city: full,
          display_text: displayName,
        },
      };
      onUpdateSettings(updated);
      return updated;
    });
    onShowToast(`Selected ${displayName}. Location and weather preview updated.`);
  };

  // Export JSON
  const handleExportConfig = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(formData, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', 'g4cast_settings.json');
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    onShowToast('Configuration exported as JSON');
  };

  // Import JSON with Schema Validation
  const handleImportConfig = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (typeof parsed !== 'object' || parsed === null) {
          throw new Error('Config must be a JSON object');
        }
        if (!parsed.weather && !parsed.display && !parsed.quiet_hours && !parsed.network) {
          throw new Error('Missing core configuration sections');
        }

        const merged: Settings = {
          ...formData,
          weather: { ...formData.weather, ...(parsed.weather || {}) },
          display: { ...formData.display, ...(parsed.display || {}) },
          quiet_hours: { ...formData.quiet_hours, ...(parsed.quiet_hours || {}) },
          network: { ...formData.network, ...(parsed.network || {}) },
        };

        setFormData(merged);
        onUpdateSettings(merged);
        onShowToast('Configuration successfully imported and saved!');
      } catch (err: any) {
        onShowToast(`Import failed: ${err.message || 'Invalid JSON format'}`, true);
      } finally {
        e.target.value = '';
      }
    };
    reader.readAsText(file);
  };

  return (
    <section className="card">
      {/* TABS HEADER */}
      <nav className="tabs">
        <button
          className={`tab-btn ${activeTab === 'weather' ? 'active' : ''}`}
          onClick={() => setActiveTab('weather')}
        >
          Weather
        </button>
        <button
          className={`tab-btn ${activeTab === 'display' ? 'active' : ''}`}
          onClick={() => setActiveTab('display')}
        >
          Display
        </button>
        <button
          className={`tab-btn ${activeTab === 'customization' ? 'active' : ''}`}
          onClick={() => setActiveTab('customization')}
        >
          Customization
        </button>
        <button
          className={`tab-btn ${activeTab === 'schedule' ? 'active' : ''}`}
          onClick={() => setActiveTab('schedule')}
        >
          Schedule
        </button>
        <button
          className={`tab-btn ${activeTab === 'network' ? 'active' : ''}`}
          onClick={() => setActiveTab('network')}
        >
          Network
        </button>
        <button
          className={`tab-btn ${activeTab === 'diagnostics' ? 'active' : ''}`}
          onClick={() => setActiveTab('diagnostics')}
        >
          Diagnostics
        </button>
        <button
          className={`tab-btn ${activeTab === 'tools' ? 'active' : ''}`}
          onClick={() => setActiveTab('tools')}
        >
          Tools & Backup
        </button>
      </nav>

      {/* TAB: WEATHER */}
      {activeTab === 'weather' && (
        <div className="tab-pane active">
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="cfg_city">OpenWeather City & Country</label>
              <input
                type="text"
                id="cfg_city"
                value={formData.weather.city}
                onChange={(e) => handleWeatherChange('city', e.target.value)}
                placeholder="e.g. Eastvale, US"
              />
            </div>

            <div className="form-group">
              <label htmlFor="cfg_display_text">Display Name on Screen</label>
              <input
                type="text"
                id="cfg_display_text"
                value={formData.weather.display_text}
                onChange={(e) => handleWeatherChange('display_text', e.target.value)}
                placeholder="e.g. Eastvale"
              />
            </div>

            <div className="form-group full-width">
              <label>Location Search (Look up Coordinates)</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && searchLocation()}
                  placeholder="Enter city name (e.g. Corona, Riverside, Seattle, New York)"
                />
                <button
                  className="btn-secondary"
                  type="button"
                  onClick={searchLocation}
                  disabled={isSearching}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {isSearching ? 'Searching...' : 'Search'}
                </button>
              </div>

              {searchResults.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {searchResults.map((r, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="btn-secondary"
                      style={{ fontSize: '12px', padding: '4px 8px' }}
                      onClick={() => selectLocation(r.name, r.country, r.name)}
                    >
                      {r.name}{r.state ? `, ${r.state}` : ''}, {r.country} ({r.lat}, {r.lon})
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="form-group full-width">
              <label htmlFor="cfg_api_key">OpenWeather API Key</label>
              <input
                type="password"
                id="cfg_api_key"
                value={formData.weather.api_key}
                onChange={(e) => handleWeatherChange('api_key', e.target.value)}
                placeholder="32-character hex key"
              />
            </div>

            <div className="form-group">
              <label htmlFor="cfg_kcno_station">NOAA Ground Sensor Station</label>
              <input
                type="text"
                id="cfg_kcno_station"
                value={formData.weather.kcno_station}
                onChange={(e) => handleWeatherChange('kcno_station', e.target.value)}
                placeholder="e.g. KCNO"
              />
            </div>

            <div className="form-group">
              <label>Physical Sensor Ground-Truth</label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  id="cfg_use_kcno"
                  checked={formData.weather.use_kcno}
                  onChange={(e) => handleWeatherChange('use_kcno', e.target.checked)}
                />
                <span>Enable live NOAA station observations</span>
              </label>
            </div>

            <div className="form-group">
              <label>Measurement Units</label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  id="cfg_use_metric"
                  checked={formData.weather.use_metric}
                  onChange={(e) => handleWeatherChange('use_metric', e.target.checked)}
                />
                <span>Use Metric Units (°C, km/h)</span>
              </label>
            </div>
          </div>
          <button className="btn-primary" onClick={saveSettings}>
            Save Weather Settings
          </button>
        </div>
      )}

      {/* TAB: DISPLAY */}
      {activeTab === 'display' && (
        <div className="tab-pane active">
          <div className="form-grid">
            <div className="form-group">
              <label>Clock Format</label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  id="cfg_use_24h"
                  checked={formData.display.use_24h_format}
                  onChange={(e) => handleDisplayChange('use_24h_format', e.target.checked)}
                />
                <span>Use 24-Hour Time Format (e.g. 14:00)</span>
              </label>
            </div>

            <div className="form-group">
              <label htmlFor="cfg_dark_mode">Visual Mode</label>
              <select
                id="cfg_dark_mode"
                value={formData.display.dark_mode}
                onChange={(e) => handleDisplayChange('dark_mode', e.target.value as DarkModeSetting)}
              >
                <option value="off">Off (Always Light)</option>
                <option value="on">On (Always Dark)</option>
                <option value="auto">Auto (Solar: Sunset → Sunrise)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="cfg_rotation">Physical Panel Hardware Mounting</label>
              <select
                id="cfg_rotation"
                value={formData.display.rotation}
                onChange={(e) =>
                  handleDisplayChange('rotation', Number(e.target.value) as 0 | 180)
                }
              >
                <option value="0">0° (Standard Upright)</option>
                <option value="180">180° (Inverted Cable Case)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="cfg_refresh_cycles">Full Refresh Cycle Interval</label>
              <input
                type="number"
                id="cfg_refresh_cycles"
                min="1"
                max="100"
                value={formData.display.full_refresh_cycles}
                onChange={(e) =>
                  handleDisplayChange('full_refresh_cycles', Number(e.target.value))
                }
              />
            </div>
          </div>
          <button className="btn-primary" onClick={saveSettings}>
            Save Display Settings
          </button>
        </div>
      )}

      {/* TAB: CUSTOMIZATION */}
      {activeTab === 'customization' && (
        <div className="tab-pane active">
          <div className="customization-section">
            <label style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Dashboard Visual Layout
            </label>
            <p className="section-subtitle">
              Select your favorite dashboard arrangement to keep your e-paper display fresh.
            </p>

            <div className="style-grid">
              {/* Classic */}
              <div
                className={`style-card ${formData.display.layout_style === 'classic' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('layout_style', 'classic')}
              >
                <span className="style-check">✓</span>
                <div className="style-thumb-wrap">
                  <img
                    src="/styles/classic.png"
                    alt="Classic Editorial Style"
                    className="style-thumb"
                  />
                </div>
                <div className="style-info">
                  <div className="style-title-row">
                    <span className="style-name">Classic</span>
                    <span className="style-badge">Default</span>
                  </div>
                  <span className="style-desc">
                    Clean floating spline graph, subtle vertical guidelines, and balanced hero card.
                  </span>
                </div>
              </div>

              {/* Widgets */}
              <div
                className={`style-card ${formData.display.layout_style === 'widgets' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('layout_style', 'widgets')}
              >
                <span className="style-check">✓</span>
                <div className="style-thumb-wrap">
                  <img
                    src="/styles/widgets.png"
                    alt="Tactile Widgets Style"
                    className="style-thumb"
                  />
                </div>
                <div className="style-info">
                  <div className="style-title-row">
                    <span className="style-name">Widgets</span>
                    <span className="style-badge">Tactile</span>
                  </div>
                  <span className="style-desc">
                    Modular 2x2 metric tiles, upper digital clock, and shaded trend graph.
                  </span>
                </div>
              </div>

              {/* Dual-Tone */}
              <div
                className={`style-card ${formData.display.layout_style === 'dualtone' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('layout_style', 'dualtone')}
              >
                <span className="style-check">✓</span>
                <div className="style-thumb-wrap">
                  <img
                    src="/styles/dualtone.png"
                    alt="Dual-Tone Style"
                    className="style-thumb"
                  />
                </div>
                <div className="style-info">
                  <div className="style-title-row">
                    <span className="style-name">Dual-Tone</span>
                    <span className="style-badge">Contrast</span>
                  </div>
                  <span className="style-desc">
                    Solid high-contrast inverted hero card with white typography on deep black.
                  </span>
                </div>
              </div>

              {/* Minimalist */}
              <div
                className={`style-card ${formData.display.layout_style === 'minimalist' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('layout_style', 'minimalist')}
              >
                <span className="style-check">✓</span>
                <div className="style-thumb-wrap">
                  <img
                    src="/styles/minimalist.png"
                    alt="Minimalist Style"
                    className="style-thumb"
                  />
                </div>
                <div className="style-info">
                  <div className="style-title-row">
                    <span className="style-name">Minimalist</span>
                    <span className="style-badge">Nordic</span>
                  </div>
                  <span className="style-desc">
                    Tactile chiclet keycap forecast, corner marks, and airy editorial layout.
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="customization-section">
            <label style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Temperature Glanceability Size
            </label>
            <p className="section-subtitle">
              Scale the focal temperature reading for your viewing distance and room setup.
            </p>

            <div className="size-grid">
              {/* Compact */}
              <div
                className={`size-card ${formData.display.hero_size === 'compact' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('hero_size', 'compact')}
              >
                <input
                  type="radio"
                  name="hero_size"
                  className="size-radio"
                  checked={formData.display.hero_size === 'compact'}
                  readOnly
                />
                <div className="size-info">
                  <span className="size-title">Compact Size</span>
                  <span className="size-desc">
                    54pt hero temperature. Subtle and space-efficient for desk or bedside viewing.
                  </span>
                </div>
              </div>

              {/* Standard */}
              <div
                className={`size-card ${formData.display.hero_size === 'standard' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('hero_size', 'standard')}
              >
                <input
                  type="radio"
                  name="hero_size"
                  className="size-radio"
                  checked={formData.display.hero_size === 'standard'}
                  readOnly
                />
                <div className="size-info">
                  <span className="size-title">Standard Size (Default)</span>
                  <span className="size-desc">
                    68pt hero temperature. Perfectly proportioned for balanced room viewing.
                  </span>
                </div>
              </div>

              {/* Large */}
              <div
                className={`size-card ${formData.display.hero_size === 'large' ? 'active' : ''}`}
                onClick={() => handleDisplayChange('hero_size', 'large')}
              >
                <input
                  type="radio"
                  name="hero_size"
                  className="size-radio"
                  checked={formData.display.hero_size === 'large'}
                  readOnly
                />
                <div className="size-info">
                  <span className="size-title">Large Glanceable</span>
                  <span className="size-desc">
                    82pt jumbo temperature. Maximum contrast, glanceable from 10+ feet across the room.
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="btn-group">
            <button className="btn-primary" onClick={saveSettings}>
              <span>✓</span> Apply & Refresh Display
            </button>
          </div>
        </div>
      )}

      {/* TAB: SCHEDULE (QUIET HOURS) */}
      {activeTab === 'schedule' && (
        <div className="tab-pane active">
          <div className="form-grid">
            <div className="form-group full-width">
              <label>Bedroom Quiet Hours</label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  id="cfg_quiet_enabled"
                  checked={formData.quiet_hours.enabled}
                  onChange={(e) => handleQuietChange('enabled', e.target.checked)}
                />
                <span>Pause minute e-paper refreshes during quiet hours</span>
              </label>
            </div>

            <div className="form-group">
              <label htmlFor="cfg_quiet_start">Quiet Window Start Time</label>
              <input
                type="time"
                id="cfg_quiet_start"
                value={formData.quiet_hours.start_time}
                onChange={(e) => handleQuietChange('start_time', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="cfg_quiet_end">Quiet Window End Time</label>
              <input
                type="time"
                id="cfg_quiet_end"
                value={formData.quiet_hours.end_time}
                onChange={(e) => handleQuietChange('end_time', e.target.value)}
              />
            </div>

            <div className="form-group full-width">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  id="cfg_allow_severe"
                  checked={formData.quiet_hours.allow_severe_alerts}
                  onChange={(e) => handleQuietChange('allow_severe_alerts', e.target.checked)}
                />
                <span>Allow Important Severe Weather Warnings to refresh during quiet hours</span>
              </label>
            </div>
          </div>
          <button className="btn-primary" onClick={saveSettings}>
            Save Schedule Settings
          </button>
        </div>
      )}

      {/* TAB: NETWORK */}
      {activeTab === 'network' && (
        <div className="tab-pane active">
          <div className="form-grid">
            <div className="form-group">
              <label>Wi-Fi Watchdog Self-Healing</label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  id="cfg_watchdog_enabled"
                  checked={formData.network.watchdog_enabled}
                  onChange={(e) => handleNetworkChange('watchdog_enabled', e.target.checked)}
                />
                <span>Enable automatic reconnection & recovery</span>
              </label>
            </div>

            <div className="form-group">
              <label htmlFor="cfg_ping_host">Liveness Ping Host</label>
              <input
                type="text"
                id="cfg_ping_host"
                value={formData.network.ping_host}
                onChange={(e) => handleNetworkChange('ping_host', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="net_ssid">Connected Network (SSID)</label>
              <input type="text" id="net_ssid" value={diagnostics.network.ssid} readOnly />
            </div>

            <div className="form-group">
              <label htmlFor="net_ip">Local IP Address</label>
              <input type="text" id="net_ip" value={diagnostics.network.ip_address} readOnly />
            </div>
          </div>

          <div className="btn-group">
            <button className="btn-primary" onClick={saveSettings}>
              Save Network Settings
            </button>
            <button className="btn-secondary" onClick={onReconnectWifi}>
              Reconnect Wi-Fi Now
            </button>
          </div>
        </div>
      )}

      {/* TAB: DIAGNOSTICS */}
      {activeTab === 'diagnostics' && (
        <div className="tab-pane active">
          <div className="diag-grid">
            <div className="diag-item">
              <div className="diag-label">CPU Temperature</div>
              <div className="diag-value">
                {diagnostics.system.cpu_temp_c}°C ({diagnostics.system.cpu_temp_f}°F)
              </div>
            </div>

            <div className="diag-item">
              <div className="diag-label">System Uptime</div>
              <div className="diag-value">{diagnostics.system.uptime}</div>
            </div>

            <div className="diag-item">
              <div className="diag-label">Memory Usage</div>
              <div className="diag-value">
                {diagnostics.system.memory.used_mb}MB / {diagnostics.system.memory.total_mb}MB (
                {diagnostics.system.memory.percent}%)
              </div>
            </div>

            <div className="diag-item">
              <div className="diag-label">Disk Free</div>
              <div className="diag-value">
                {diagnostics.system.disk.free_gb} GB free ({diagnostics.system.disk.percent}% used)
              </div>
            </div>

            <div className="diag-item">
              <div className="diag-label">Wi-Fi Signal</div>
              <div className="diag-value">
                {diagnostics.network.signal_percent}% ({diagnostics.network.signal_dbm} dBm)
              </div>
            </div>

            <div className="diag-item">
              <div className="diag-label">Last Weather Sync</div>
              <div className="diag-value">{diagnostics.weather.last_sync_time}</div>
            </div>

            <div className="diag-item">
              <div className="diag-label">Weather API Status</div>
              <div className="diag-value">{diagnostics.weather.api_status}</div>
            </div>

            <div className="diag-item">
              <div className="diag-label">E-Paper Refreshes</div>
              <div className="diag-value">{diagnostics.display.refresh_count}</div>
            </div>

            <div className="diag-item">
              <div className="diag-label">Application Version</div>
              <div className="diag-value">v{diagnostics.system.version}</div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: TOOLS & BACKUP */}
      {activeTab === 'tools' && (
        <div className="tab-pane active">
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ marginBottom: '8px', fontSize: '15px', fontWeight: 600 }}>
              Severe Weather Alert Simulation
            </h3>
            <p style={{ fontSize: '13px', color: '#888', marginBottom: '12px' }}>
              Test the high-contrast alert banner on your e-paper panel and preview mirror.
            </p>
            <div className="btn-group" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              <button
                className="btn-secondary"
                onClick={() => onSimulateAlert('High Wind Warning in effect')}
              >
                ⚠️ Wind Warning
              </button>
              <button
                className="btn-secondary"
                onClick={() => onSimulateAlert('Flash Flood Watch in effect')}
              >
                🌊 Flood Watch
              </button>
              <button
                className="btn-secondary"
                onClick={() => onSimulateAlert('Excessive Heat Warning in effect')}
              >
                🌡️ Heat Warning
              </button>
              <button className="btn-secondary" onClick={onClearAlert}>
                ✖ Clear Alert
              </button>
            </div>

            <div style={{ marginTop: '12px', display: 'flex', gap: '8px', maxWidth: '480px' }}>
              <input
                type="text"
                placeholder="Or type custom alert title (e.g. Blizzard Warning)..."
                value={customAlertTitle}
                onChange={(e) => setCustomAlertTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && customAlertTitle.trim()) {
                    onSimulateAlert(customAlertTitle.trim());
                    setCustomAlertTitle('');
                  }
                }}
              />
              <button
                className="btn-secondary"
                onClick={() => {
                  if (customAlertTitle.trim()) {
                    onSimulateAlert(customAlertTitle.trim());
                    setCustomAlertTitle('');
                  }
                }}
              >
                Simulate
              </button>
            </div>
          </div>

          <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #222' }}>
            <h3 style={{ marginBottom: '8px', fontSize: '15px', fontWeight: 600 }}>
              Configuration Backup & Restore
            </h3>
            <p style={{ fontSize: '13px', color: '#888', marginBottom: '12px' }}>
              Download a backup of your settings or restore from a previously exported JSON file.
            </p>
            <div className="btn-group" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              <button
                type="button"
                className="btn-primary"
                onClick={handleExportConfig}
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}
              >
                ⬇️ Export Config (JSON)
              </button>

              <label
                className="btn-secondary"
                style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
              >
                <span>⬆️ Import Config File</span>
                <input
                  type="file"
                  accept=".json"
                  style={{ display: 'none' }}
                  onChange={handleImportConfig}
                />
              </label>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
