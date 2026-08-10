/** MarketListener terminal design tokens.
 *
 * 单一定义金融终端语义色：上涨红、下跌绿、平盘灰；深/浅两套完整 Palette。
 * 页面与图表一律从这里取色，禁止在组件里散落硬编码 RGB。
 */

export type ThemeMode = "system" | "light" | "dark";
export type EffectiveTheme = "light" | "dark";

export interface Palette {
  background: string;
  surface: string;
  surfaceElevated: string;
  surfaceSelected: string;
  divider: string;
  textPrimary: string;
  textSecondary: string;
  textDisabled: string;
  accent: string;
  accentSoft: string;
  priceUp: string;
  priceDown: string;
  flat: string;
  warning: string;
  error: string;
  info: string;
  highlight: string;
  chartGrid: string;
  chartAxis: string;
  chartTooltip: string;
  chartTooltipBorder: string;
}

export const palettes: Record<EffectiveTheme, Palette> = {
  dark: {
    background: "#0b0e14",
    surface: "#10151e",
    surfaceElevated: "#151c27",
    surfaceSelected: "#1b2534",
    divider: "#232d3d",
    textPrimary: "#e8edf5",
    textSecondary: "#929eaf",
    textDisabled: "#586273",
    accent: "#2962ff",
    accentSoft: "#1e3a8a",
    priceUp: "#f0414e",
    priceDown: "#22b07d",
    flat: "#929eaf",
    warning: "#f5a623",
    error: "#ff5252",
    info: "#4f8cff",
    highlight: "#ffd166",
    chartGrid: "#232d3d",
    chartAxis: "#7c8899",
    chartTooltip: "#1b2534",
    chartTooltipBorder: "#31415c",
  },
  light: {
    background: "#f5f7fa",
    surface: "#ffffff",
    surfaceElevated: "#f0f3f8",
    surfaceSelected: "#e8eef8",
    divider: "#e1e6ee",
    textPrimary: "#11151c",
    textSecondary: "#687386",
    textDisabled: "#9aa5b4",
    accent: "#2962ff",
    accentSoft: "#dbe6ff",
    priceUp: "#d92d20",
    priceDown: "#0e9f6e",
    flat: "#687386",
    warning: "#b45309",
    error: "#dc2626",
    info: "#2563eb",
    highlight: "#b45309",
    chartGrid: "#e1e6ee",
    chartAxis: "#687386",
    chartTooltip: "#ffffff",
    chartTooltipBorder: "#d7dee9",
  },
};

export function applyTokens(theme: EffectiveTheme): void {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.classList.toggle("dark", theme === "dark");
  const palette = palettes[theme];
  for (const [name, value] of Object.entries(palette)) {
    const variable = name.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`);
    root.style.setProperty(`--ml-${variable}`, value);
  }
}
