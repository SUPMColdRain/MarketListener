import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { applyTokens, palettes, type EffectiveTheme, type ThemeMode } from "../design/tokens";

const STORAGE_KEY = "marketlistener.theme";

function storedMode(): ThemeMode {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === "light" || raw === "dark" ? raw : "system";
}

export const useThemeStore = defineStore("theme", () => {
  const mode = ref<ThemeMode>(storedMode());
  const systemDark = ref(window.matchMedia("(prefers-color-scheme: dark)").matches);

  const effective = computed<EffectiveTheme>(() =>
    mode.value === "system" ? (systemDark.value ? "dark" : "light") : mode.value,
  );
  const palette = computed(() => palettes[effective.value]);

  function sync(): void {
    applyTokens(effective.value);
  }

  function setMode(next: ThemeMode): void {
    mode.value = next;
    localStorage.setItem(STORAGE_KEY, next);
    sync();
  }

  function toggle(): void {
    setMode(effective.value === "dark" ? "light" : "dark");
  }

  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", (event) => {
    systemDark.value = event.matches;
    sync();
  });

  sync();
  return { mode, effective, palette, setMode, toggle, sync };
});
