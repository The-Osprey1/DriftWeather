# Implementation Plan: 3 New Artistic & Functional E-Paper Display Layouts

Expand the G4Cast 800×480 E-Paper Weather Station with three new distinctive, artistically engaging, and functional display layouts—**Retro Terminal**, **Cyberpunk Matrix**, and **Japanese Zen Minimalist**—bringing the total dashboard collection to 7 selectable styles.

---

### User Review & Critical Decisions

> [!IMPORTANT]
> The user confirmed the following design directions in Phase 1:
> - **Theme Archetypes**: Retro Terminal, Cyberpunk Matrix, and Japanese Zen Minimalist.
> - **Aesthetic Balance**: Blend artistic 1-bit vector illustrations with rich weather metrics.
> - **Theme Architecture**: Retain all 4 existing styles (Classic, Widgets, Dual-Tone, Minimalist) alongside the 3 new ones for a total of **7 selectable dashboard styles**.

---

### 1. Overview & Core Concept

- **What It Delivers**: 3 completely new, pixel-accurate 800×480 monochrome canvas rendering engines in `EPaperRenderer.tsx`, plus corresponding selection cards in the Web Control Panel Customization tab.
- **Key Value**: Transforms the G4Cast e-paper screen from a purely utilitarian gadget into an artistic interior decor piece that can switch mood on demand—from nostalgic 80s CRT computing, to futuristic cyberpunk telemetry, to tranquil Japanese woodblock minimalism.

---

### 2. User Experience & Visual Design

#### The 3 New Dashboard Layouts

```
+-----------------------------------------------------------------------------+
| RETRO TERMINAL (VT100 / CRT)                                                |
| > G4CAST.EXE // EASTVALE // AIR: GOOD [AQI 34]                              |
| +-[ TELEMETRY ]-----------------------------------------------------------+ |
| |  74°F SUNNY          [BARO: 1014hPa] [HUM: 42%] [WIND: WSW 9mph]        | |
| |  HIGH: 79° LOW: 56°  [24H DISCRETE ASCII QUANTIZED MATRIX PLOT]         | |
| |  # . : * . . -       # = PEAK TEMP   - = OVERNIGHT LOW                  | |
| +-------------------------------------------------------------------------+ |
| > [OUTLOOK] TUE: 81°/57°  |  WED: 83°/59°  |  THU: 78°/55°  |  FRI: 75°/52° |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| CYBERPUNK MATRIX (HUD / SCI-FI TELEMETRY)                                   |
| // LAT 33.963°N LON 117.564°W                  [SYS_OK] [AQI 34 // NOMINAL] |
| /====================================\   ( RADAR COMPASS GAUGE )            |
| | 74°F  CLEAR SKY                    |      N     Wind: 9 mph WSW           |
| | STENCIL JUMBO HERO                 |    W + E   Baro: 1014 hPa            |
| \====================================/      S     UVI: 06 / 10              |
| [24H HIGH-FREQ DUAL ENVELOPE BAND: UPPER MAX / LOWER MIN SPLINE]            |
| [> TUE 81/57] [> WED 83/59] [> THU 78/55] [> FRI 75/52]  (TECH CHIP KEYCAPS)|
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| JAPANESE ZEN MINIMALIST (UKIYO-E / SUMI-E WOODBLOCK)                        |
|                                                                             |
|  晴    EASTVALE          [ Delicate 1-bit Fuji Mountain Silhouette          |
|  天    Mon, Oct 26         with rising solar disc & pine branch line-art ]  |
|                                                                             |
|  74°   Clear Sky                                                            |
|  H 79° / L 56°           [ Organic Zen Rock-Garden Flowing Spline Curve ]   |
|                                                                             |
|  — TUE 81° / 57° — WED 83° / 59° — THU 78° / 55° — FRI 75° / 52° — (BAMBOO)  |
+-----------------------------------------------------------------------------+
```

1. **Retro Terminal (`terminal`)**:
   - Monospace CRT typography with bracketed headers and status prompts (`> G4CAST.EXE`, `[SYS_OK]`).
   - Quantized discrete ASCII matrix temperature trend graph with dotted threshold reference lines.
   - Boxed telemetry chips (`[HUMID: 42%]`, `[WIND: WSW 9mph]`, `[BARO: 1014 hPa]`).
   - Bottom command line outlook strip with bracketed daily steps.

2. **Cyberpunk Matrix (`matrix`)**:
   - 45° chamfered polygon HUD containers and coordinate brackets (`// LAT 33.963°N LON 117.564°W`).
   - 1-Bit Circular Radar Compass: Circular compass rose with 8 cardinal ticks, center crosshair, and dynamic wind vector needle.
   - Dual-envelope 24h spline graph: Draws upper envelope, lower baseline, and filled hatch pattern between extremes.
   - Tech-chip forecast cards with mini progress bars for precipitation probability (PoP).

3. **Japanese Zen Minimalist (`zen`)**:
   - Tranquil 1-bit vector artwork: Mount Fuji silhouette, rising sun/moon orb, and subtle pine branch line-art framing the upper right quadrant.
   - Kanji weather condition accent seal ("晴" Clear, "雨" Rain, "雲" Cloud, "風" Wind) rendered alongside clean English typography.
   - Flowing organic spline curve resembling a dry zen garden sand ripple with stone dot markers.
   - Horizontal bamboo-reed minimalist forecast strip with generous breathing room (Ma / 間).

---

### 3. Technical Architecture & Component Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                         App.tsx                             │
│   - Holds global Settings state (7 Layout Styles)           │
│   - Synchronizes with localStorage & solar daylight engine  │
│   - Coordinates Refresh & Clean electrophoretic animations  │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│      EPaperRenderer.tsx      │ │     ControlPanel.tsx       │
│  800x480 Canvas (2x Retina)  │ │  Tabs: Customization, etc. │
│  ┌────────────────────────┐  │ │  ┌───────────────────────┐ │
│  │ 1. Classic             │  │ │  │ 7 Interactive Style   │ │
│  │ 2. Widgets             │  │ │  │ Cards with Badges:    │ │
│  │ 3. Dual-Tone           │  │ │  │ - Classic (Default)   │ │
│  │ 4. Minimalist          │  │ │  │ - Widgets (Tactile)   │ │
│  │ 5. Retro Terminal NEW  │  │ │  │ - Dual-Tone (Contrast)│ │
│  │ 6. Cyberpunk Matrix NEW│  │ │  │ - Minimalist (Nordic) │ │
│  │ 7. Zen Minimalist   NEW│  │ │  │ - Terminal (Retro) NEW│ │
│  └────────────────────────┘  │ │  │ - Matrix (Sci-Fi)  NEW│ │
│  - 1-Bit Vector Icons        │ │  │ - Zen (Ukiyo-e)    NEW│ │
│  - Alert Banner (y=436)      │ │  └───────────────────────┘ │
│  - Waveform Flash Cycle      │ │  - Instant Live Preview    │
└──────────────────────────────┘ └────────────────────────────┘
```

#### Proposed Changes

1. **`src/types/index.ts`**:
   - Update `LayoutStyle` type union:
     ```typescript
     export type LayoutStyle =
       | 'classic'
       | 'widgets'
       | 'dualtone'
       | 'minimalist'
       | 'terminal'
       | 'matrix'
       | 'zen';
     ```

2. **`src/components/EPaperRenderer.tsx`**:
   - Add rendering routines for:
     - `style === 'terminal'`: ASCII borders, monospace prompt headers, stepped matrix histogram curve, bracketed telemetry boxes.
     - `style === 'matrix'`: Chamfered HUD polygon frames, 1-bit radial radar compass for wind velocity, dual envelope spline graph, tech chip keycaps.
     - `style === 'zen'`: Vector Mount Fuji landscape silhouette, rising solar disc, kanji weather mark, flowing stone-garden spline, minimalist daily forecast strip.
   - Maintain full compatibility with:
     - Light Mode & Dark Mode (invert)
     - Auto Solar Engine (switches between day and night seamlessly)
     - Hero font sizing (Compact 54pt, Standard 68pt, Large 82pt)
     - Severe Weather Alert Banner at bottom with PoP collision suppression

3. **`src/components/ControlPanel.tsx`**:
   - Add 3 new styled cards to the Customization tab grid with thumbnail previews, badges (`Retro`, `Sci-Fi`, `Ukiyo-e`), and descriptive copy.
   - Ensure clicking any card immediately updates the live canvas preview above.

4. **Static Thumbnail Generation**:
   - Create crisp canvas SVG / PNG preview thumbnails for the 3 new styles so the customization cards display clean visual cards matching the existing 4.

---

### 4. Verification & Testing Plan

1. **Compilation & Linting**:
   - `npm run lint` (`tsc --noEmit`) to verify strict TypeScript type safety.
   - `compile_applet` (`tsc && vite build`) to confirm production compilation.
2. **Visual & Interactive Verification**:
   - Test each of the 7 styles in:
     - Light Mode (paper white background)
     - Dark Mode (inverted black background)
     - Auto Solar Day/Night mode
     - Compact, Standard, and Large temperature glanceability sizing
   - Trigger alert simulations (Wind Warning, Flood Watch) to verify banner positioning and collision suppression on all 3 new styles.
   - Verify waveform clean animation and refresh cycles.
