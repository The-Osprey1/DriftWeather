import React, { useEffect, useRef, useState, useImperativeHandle, forwardRef } from 'react';
import { Settings, WeatherData } from '../types';

export interface EPaperRendererRef {
  triggerRefreshAnimation: (deepClean?: boolean) => void;
  getCanvasDataUrl: () => string;
}

interface EPaperRendererProps {
  settings: Settings;
  weather: WeatherData;
  isDarkEffective: boolean;
  onRefreshCompleted?: () => void;
}

export const EPaperRenderer = forwardRef<EPaperRendererRef, EPaperRendererProps>(
  ({ settings, weather, isDarkEffective, onRefreshCompleted }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [cleanPhase, setCleanPhase] = useState<number>(0);

    const triggerRefreshAnimation = (deepClean: boolean = false) => {
      setIsRefreshing(true);
      if (deepClean) {
        // Deep clean: 4 alternating black/white flashes
        let step = 1;
        setCleanPhase(step);
        const interval = setInterval(() => {
          step++;
          if (step > 4) {
            clearInterval(interval);
            setCleanPhase(0);
            setIsRefreshing(false);
            if (onRefreshCompleted) onRefreshCompleted();
          } else {
            setCleanPhase(step);
          }
        }, 220);
      } else {
        // Normal refresh: 2 quick flashes
        let step = 1;
        setCleanPhase(step);
        const interval = setInterval(() => {
          step++;
          if (step > 2) {
            clearInterval(interval);
            setCleanPhase(0);
            setIsRefreshing(false);
            if (onRefreshCompleted) onRefreshCompleted();
          } else {
            setCleanPhase(step);
          }
        }, 180);
      }
    };

    useImperativeHandle(ref, () => ({
      triggerRefreshAnimation,
      getCanvasDataUrl: () => {
        return canvasRef.current ? canvasRef.current.toDataURL('image/png') : '';
      },
    }));

    // Draw the 800x480 canvas
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const W = 800;
      const H = 480;

      // Handle clean phase flash simulation
      if (cleanPhase > 0) {
        ctx.fillStyle = cleanPhase % 2 === 1 ? '#000000' : '#ffffff';
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = cleanPhase % 2 === 1 ? '#ffffff' : '#000000';
        ctx.font = 'bold 20px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('E-PAPER CLEANING CYCLE...', W / 2, H / 2);
        return;
      }

      ctx.save();

      // Rotation
      if (settings.display.rotation === 180) {
        ctx.translate(W, H);
        ctx.rotate(Math.PI);
      }

      // Base Palette (Monochrome 1-bit style)
      const isDark = isDarkEffective;
      const bg = isDark ? '#000000' : '#ffffff';
      const fg = isDark ? '#ffffff' : '#000000';
      const subtleLine = isDark ? '#333333' : '#d0d0d0';

      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = fg;
      ctx.strokeStyle = fg;

      const style = settings.display.layout_style;
      const heroSizeOption = settings.display.hero_size;

      let heroFontPt = 68;
      if (heroSizeOption === 'compact') heroFontPt = 54;
      if (heroSizeOption === 'large') heroFontPt = 82;

      const degSymbol = '°';
      const unit = settings.weather.use_metric ? 'C' : 'F';
      const speedUnit = settings.weather.use_metric ? 'km/h' : 'mph';

      // Current time string
      const now = new Date();
      const timeStr = settings.display.use_24h_format
        ? now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
        : now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });

      const dateStr = now.toLocaleDateString([], {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });

      // ==========================================
      // STYLE 1: CLASSIC
      // ==========================================
      if (style === 'classic') {
        // Top Left: City, Time, Date
        ctx.font = 'bold 26px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(weather.city, 32, 48);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${dateStr} • ${timeStr}`, 32, 74);

        if (weather.kcnoObservation) {
          ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
          ctx.fillText(
            `NOAA ${weather.kcnoObservation.station} • ${weather.kcnoObservation.temp}${degSymbol}${unit} • RH ${weather.kcnoObservation.humidity}%`,
            32,
            96
          );
        }

        // Hero Left Card: Temperature
        ctx.font = `bold ${heroFontPt}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
        const tempText = `${weather.currentTemp}${degSymbol}`;
        ctx.fillText(tempText, 32, 175);

        ctx.font = 'bold 18px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${weather.condition}`, 32, 210);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(
          `High: ${weather.highTemp}${degSymbol}  Low: ${weather.lowTemp}${degSymbol}`,
          32,
          235
        );

        // Metric indicators under hero
        ctx.strokeStyle = subtleLine;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(32, 252);
        ctx.lineTo(280, 252);
        ctx.stroke();

        ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`Humidity: ${weather.humidity}%`, 32, 276);
        ctx.fillText(`Wind: ${weather.windDirection} ${weather.windSpeed} ${speedUnit}`, 150, 276);
        ctx.fillText(`UV Index: ${weather.uvi}`, 32, 298);
        ctx.fillText(`Baro: ${weather.pressure} hPa`, 150, 298);

        // Vertical divider
        ctx.strokeStyle = subtleLine;
        ctx.beginPath();
        ctx.moveTo(300, 30);
        ctx.lineTo(300, 310);
        ctx.stroke();

        // 24-Hour Graph Header (Right side: x: 320 to 764, y: 30 to 184)
        ctx.font = 'bold 15px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('24-HOUR TREND', 320, 50);

        // AQI pill badge at [676..764, 34..56]
        drawAqiPill(ctx, 676, 34, 88, 24, weather.aqiValue, weather.aqiCategory, isDark);

        // 24-Hour Spline Curve in box [320..764, 70..180]
        drawSplineGraph(
          ctx,
          weather.hourly,
          320,
          70,
          444,
          105,
          fg,
          subtleLine,
          isDark,
          degSymbol
        );

        // Horizontal divider before extended forecast
        ctx.strokeStyle = subtleLine;
        ctx.beginPath();
        ctx.moveTo(32, 320);
        ctx.lineTo(768, 320);
        ctx.stroke();

        // 4-Day Daily Forecast at bottom [32..768, 335..450]
        drawDailyForecastColumns(
          ctx,
          weather.daily,
          32,
          335,
          736,
          95,
          fg,
          subtleLine,
          isDark,
          degSymbol
        );
      }

      // ==========================================
      // STYLE 2: WIDGETS (TACTILE TILES)
      // ==========================================
      else if (style === 'widgets') {
        // Top Bar: Clock & Station header
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(weather.city, 32, 45);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${dateStr} • ${timeStr}`, 32, 68);

        // AQI pill badge top-right
        drawAqiPill(ctx, 676, 32, 88, 24, weather.aqiValue, weather.aqiCategory, isDark);

        // Widget 1: Hero Temp Card [32, 85, 240, 140]
        drawCardBorder(ctx, 32, 85, 240, 140, fg, isDark);
        ctx.font = `bold ${heroFontPt - 6}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
        ctx.fillText(`${weather.currentTemp}${degSymbol}`, 48, 165);
        ctx.font = 'bold 15px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${weather.condition}`, 48, 195);
        ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`H: ${weather.highTemp}${degSymbol}  L: ${weather.lowTemp}${degSymbol}`, 48, 215);

        // Widget 2: 2x2 Metric tiles [288, 85, 480, 140]
        drawCardBorder(ctx, 288, 85, 480, 140, fg, isDark);
        const colW = 230;
        // Tile A: Humidity
        ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('HUMIDITY', 308, 112);
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${weather.humidity}%`, 308, 138);

        // Tile B: Wind
        ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('WIND VELOCITY', 308 + colW, 112);
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${weather.windSpeed} ${speedUnit} ${weather.windDirection}`, 308 + colW, 138);

        // Tile C: UV Index
        ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('UV INDEX', 308, 178);
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${weather.uvi} of 10`, 308, 204);

        // Tile D: Atmospheric Pressure
        ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('ATM PRESSURE', 308 + colW, 178);
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`${weather.pressure} hPa`, 308 + colW, 204);

        // Widget 3: Shaded Trend Graph [32, 238, 736, 105]
        drawCardBorder(ctx, 32, 238, 736, 105, fg, isDark);
        ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('24-HOUR HOURLY TEMPERATURE OUTLOOK', 46, 258);
        drawSplineGraph(ctx, weather.hourly, 46, 268, 708, 65, fg, subtleLine, isDark, degSymbol);

        // Bottom: 4 Days Forecast Cards [32, 355, 736, 105]
        drawDailyForecastCards(
          ctx,
          weather.daily,
          32,
          355,
          736,
          95,
          fg,
          subtleLine,
          isDark,
          degSymbol
        );
      }

      // ==========================================
      // STYLE 3: DUAL-TONE (INVERTED HERO CARD)
      // ==========================================
      else if (style === 'dualtone') {
        // Left Column (Inverted Solid Hero Card): [0, 0, 310, 480]
        ctx.fillStyle = fg;
        ctx.fillRect(0, 0, 310, 480);

        ctx.fillStyle = bg; // Inverted text
        ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(weather.city, 28, 52);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(dateStr, 28, 78);
        ctx.fillText(timeStr, 28, 98);

        ctx.font = `bold ${heroFontPt}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
        ctx.fillText(`${weather.currentTemp}${degSymbol}`, 28, 200);

        ctx.font = 'bold 18px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(weather.condition, 28, 235);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`H: ${weather.highTemp}${degSymbol}  •  L: ${weather.lowTemp}${degSymbol}`, 28, 265);

        ctx.strokeStyle = bg;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(28, 285);
        ctx.lineTo(280, 285);
        ctx.stroke();

        ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(`Humidity: ${weather.humidity}%`, 28, 315);
        ctx.fillText(`Wind: ${weather.windDirection} ${weather.windSpeed} ${speedUnit}`, 28, 340);
        ctx.fillText(`UV Index: ${weather.uvi}`, 28, 365);
        ctx.fillText(`Pressure: ${weather.pressure} hPa`, 28, 390);

        if (weather.kcnoObservation) {
          ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
          ctx.fillText(`Ground: ${weather.kcnoObservation.station}`, 28, 430);
        }

        // Right Column: Clean White Canvas [310, 0, 490, 480]
        ctx.fillStyle = fg;

        // Top Right Header & AQI
        ctx.font = 'bold 16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('HOURLY PROJECTION', 340, 50);
        drawAqiPill(ctx, 676, 32, 88, 24, weather.aqiValue, weather.aqiCategory, isDark);

        // 24h Graph [340, 75, 424, 130]
        drawSplineGraph(ctx, weather.hourly, 340, 75, 424, 130, fg, subtleLine, isDark, degSymbol);

        // Divider
        ctx.strokeStyle = subtleLine;
        ctx.beginPath();
        ctx.moveTo(340, 260);
        ctx.lineTo(764, 260);
        ctx.stroke();

        ctx.font = 'bold 16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText('4-DAY OUTLOOK', 340, 290);

        // Daily rows
        drawDailyForecastColumns(
          ctx,
          weather.daily,
          340,
          310,
          424,
          110,
          fg,
          subtleLine,
          isDark,
          degSymbol
        );
      }

      // ==========================================
      // STYLE 4: MINIMALIST (NORDIC CHICLET)
      // ==========================================
      else {
        // Corner Registration Marks (Nordic layout accent)
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = fg;
        drawCornerMark(ctx, 24, 24);
        drawCornerMark(ctx, 776, 24);
        drawCornerMark(ctx, 24, 456);
        drawCornerMark(ctx, 776, 456);

        // Minimalist Header
        ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(weather.city, 40, 52);

        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
        ctx.fillText(`${dateStr.toUpperCase()} / ${timeStr}`, 40, 75);

        // AQI badge
        drawAqiPill(ctx, 676, 36, 88, 24, weather.aqiValue, weather.aqiCategory, isDark);

        // Center Hero
        ctx.font = `bold ${heroFontPt}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
        ctx.fillText(`${weather.currentTemp}${degSymbol}`, 40, 175);

        ctx.font = 'bold 17px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.fillText(weather.condition.toUpperCase(), 40, 206);

        ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
        ctx.fillText(
          `MAX ${weather.highTemp}${degSymbol} / MIN ${weather.lowTemp}${degSymbol} / RH ${weather.humidity}% / ${weather.windDirection} ${weather.windSpeed}${speedUnit}`,
          40,
          232
        );

        // Clean Spline Graph
        drawSplineGraph(
          ctx,
          weather.hourly,
          40,
          255,
          720,
          85,
          fg,
          subtleLine,
          isDark,
          degSymbol
        );

        // Chiclet Keycap Forecast at bottom
        drawDailyChiclets(
          ctx,
          weather.daily,
          40,
          365,
          720,
          75,
          fg,
          isDark,
          degSymbol
        );
      }

      // ==========================================
      // SEVERE WEATHER ALERT BANNER (Bottom bar)
      // Geometry: [320, 436, 764, 460] (or full width if minimalist/widgets)
      // ==========================================
      if (weather.alertBanner && weather.alertBanner.active) {
        const bx = style === 'classic' || style === 'dualtone' ? 320 : 180;
        const by = 436;
        const bw = 764 - bx;
        const bh = 24;

        // Inverted banner
        ctx.fillStyle = fg;
        drawRoundedRect(ctx, bx, by, bw, bh, 5, true, false);

        ctx.fillStyle = bg;
        ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`⚠ ALERT: ${weather.alertBanner.title.toUpperCase()}`, bx + 12, by + 16);
      }

      ctx.restore();
    }, [settings, weather, isDarkEffective, cleanPhase]);

    return (
      <div className="relative w-full aspect-[800/480] bg-white rounded-[6px] overflow-hidden border border-[#30363d] shadow-lg flex items-center justify-center">
        <canvas
          ref={canvasRef}
          width={800}
          height={480}
          className="w-full h-full object-contain block"
        />
        {isRefreshing && (
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[1px] flex items-center justify-center pointer-events-none">
            <div className="bg-[#161b22] border border-[#58a6ff] text-[#f0f6fc] text-xs font-semibold px-4 py-2 rounded shadow-lg flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#3fb950] animate-ping" />
              E-Paper Electrophoretic Waveform Refresh...
            </div>
          </div>
        )}
      </div>
    );
  }
);

EPaperRenderer.displayName = 'EPaperRenderer';

// Helper drawing utilities
function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
  fill: boolean = true,
  stroke: boolean = true
) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.arcTo(x + width, y, x + width, y + radius, radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
  ctx.lineTo(x + radius, y + height);
  ctx.arcTo(x, y + height, x, y + height - radius, radius);
  ctx.lineTo(x, y + radius);
  ctx.arcTo(x, y, x + radius, y, radius);
  ctx.closePath();
  if (fill) ctx.fill();
  if (stroke) ctx.stroke();
}

function drawAqiPill(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  aqiValue: number,
  category: string,
  isDark: boolean
) {
  const fg = isDark ? '#ffffff' : '#000000';
  const bg = isDark ? '#000000' : '#ffffff';

  ctx.strokeStyle = fg;
  ctx.lineWidth = 1.5;
  ctx.fillStyle = bg;
  drawRoundedRect(ctx, x, y, w, h, 11, true, true);

  ctx.fillStyle = fg;
  ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`AQI ${aqiValue} • ${category}`, x + w / 2, y + 16);
}

function drawCardBorder(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  fg: string,
  isDark: boolean
) {
  ctx.strokeStyle = isDark ? '#333333' : '#000000';
  ctx.lineWidth = 1.5;
  drawRoundedRect(ctx, x, y, w, h, 6, false, true);
}

function drawCornerMark(ctx: CanvasRenderingContext2D, cx: number, cy: number) {
  const size = 8;
  ctx.beginPath();
  ctx.moveTo(cx - size, cy);
  ctx.lineTo(cx + size, cy);
  ctx.moveTo(cx, cy - size);
  ctx.lineTo(cx, cy + size);
  ctx.stroke();
}

function drawSplineGraph(
  ctx: CanvasRenderingContext2D,
  hourly: WeatherData['hourly'],
  x: number,
  y: number,
  w: number,
  h: number,
  fg: string,
  subtleLine: string,
  isDark: boolean,
  deg: string
) {
  if (!hourly || hourly.length === 0) return;

  const temps = hourly.map((h) => h.temp);
  const minTemp = Math.min(...temps) - 2;
  const maxTemp = Math.max(...temps) + 2;
  const range = Math.max(1, maxTemp - minTemp);

  const points = hourly.map((item, idx) => {
    const px = x + (idx / (hourly.length - 1)) * w;
    const py = y + h - ((item.temp - minTemp) / range) * (h - 24) - 12;
    return { x: px, y: py, temp: item.temp, time: item.time };
  });

  // Background guide lines
  ctx.strokeStyle = subtleLine;
  ctx.lineWidth = 0.8;
  for (let i = 0; i < points.length; i += 2) {
    ctx.beginPath();
    ctx.setLineDash([2, 3]);
    ctx.moveTo(points[i].x, y);
    ctx.lineTo(points[i].x, y + h);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  // Draw smooth spline curve
  ctx.strokeStyle = fg;
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2 < points.length ? i + 2 : i + 1];

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
  }
  ctx.stroke();

  // Draw point dots, temperature numbers, and time labels
  points.forEach((p, i) => {
    // Circle dot
    ctx.fillStyle = fg;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
    ctx.fill();

    // Temp label above
    ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${p.temp}${deg}`, p.x, p.y - 8);

    // Time label below
    ctx.font = '10.5px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(p.time, p.x, y + h + 14);
  });
}

function drawDailyForecastColumns(
  ctx: CanvasRenderingContext2D,
  daily: WeatherData['daily'],
  x: number,
  y: number,
  w: number,
  h: number,
  fg: string,
  subtleLine: string,
  isDark: boolean,
  deg: string
) {
  if (!daily || daily.length === 0) return;
  const colW = w / daily.length;

  daily.forEach((d, i) => {
    const cx = x + i * colW + colW / 2;

    // Day name
    ctx.font = 'bold 15px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(d.dayName, cx, y + 20);

    // Condition
    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(d.condition, cx, y + 42);

    // High / Low
    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(`${d.maxTemp}${deg} / ${d.minTemp}${deg}`, cx, y + 66);

    // PoP Rain Chance
    if (d.pop > 0) {
      ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      ctx.fillText(`☂ ${d.pop}%`, cx, y + 84);
    }

    // Column separator
    if (i < daily.length - 1) {
      ctx.strokeStyle = subtleLine;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + (i + 1) * colW, y + 8);
      ctx.lineTo(x + (i + 1) * colW, y + h - 8);
      ctx.stroke();
    }
  });
}

function drawDailyForecastCards(
  ctx: CanvasRenderingContext2D,
  daily: WeatherData['daily'],
  x: number,
  y: number,
  w: number,
  h: number,
  fg: string,
  subtleLine: string,
  isDark: boolean,
  deg: string
) {
  const gap = 12;
  const cardW = (w - gap * (daily.length - 1)) / daily.length;

  daily.forEach((d, i) => {
    const cx = x + i * (cardW + gap);
    drawCardBorder(ctx, cx, y, cardW, h, fg, isDark);

    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(d.dayName, cx + cardW / 2, y + 26);

    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(d.condition, cx + cardW / 2, y + 48);

    ctx.font = 'bold 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(`${d.maxTemp}${deg} / ${d.minTemp}${deg}`, cx + cardW / 2, y + 74);
  });
}

function drawDailyChiclets(
  ctx: CanvasRenderingContext2D,
  daily: WeatherData['daily'],
  x: number,
  y: number,
  w: number,
  h: number,
  fg: string,
  isDark: boolean,
  deg: string
) {
  const gap = 14;
  const cardW = (w - gap * (daily.length - 1)) / daily.length;

  daily.forEach((d, i) => {
    const cx = x + i * (cardW + gap);
    // Tactile chiclet box
    ctx.strokeStyle = fg;
    ctx.lineWidth = 1.2;
    drawRoundedRect(ctx, cx, y, cardW, h, 6, false, true);

    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(d.dayName.toUpperCase(), cx + cardW / 2, y + 24);

    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
    ctx.fillText(`${d.maxTemp}${deg} | ${d.minTemp}${deg}`, cx + cardW / 2, y + 48);

    if (d.pop > 0) {
      ctx.font = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';
      ctx.fillText(`${d.pop}% POP`, cx + cardW / 2, y + 64);
    }
  });
}
