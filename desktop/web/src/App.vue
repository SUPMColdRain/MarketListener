<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useThemeStore } from "./stores/theme";
import type { ThemeMode } from "./design/tokens";

const theme = useThemeStore();
const route = useRoute();

const workbench = [
  ["/market/", "行情"],
  ["/data/", "数据"],
  ["/strategy/", "策略"],
  ["/stats/", "统计"],
  ["/industry/", "产业链"],
] as const;

const management = [
  ["/", "首页"],
  ["/f10/", "F10"],
  ["/logs/", "日志"],
] as const;

const themeLabels: Record<ThemeMode, string> = {
  system: "跟随系统",
  light: "浅色",
  dark: "深色",
};

const activePath = computed(() => route.path);
const isActive = (path: string): boolean =>
  path === "/" ? activePath.value === "/" : activePath.value.startsWith(path);

function chooseTheme(mode: string): void {
  if (mode === "system" || mode === "light" || mode === "dark") theme.setMode(mode);
}
</script>

<template>
  <el-container class="terminal">
    <el-header class="topbar">
      <router-link class="brand" to="/" data-test="brand">MarketListener</router-link>
      <nav class="nav-group workbench-nav" aria-label="研究工作台">
        <span class="nav-label">研究</span>
        <router-link
          v-for="[path, label] in workbench"
          :key="path"
          :to="path"
          :class="{ active: isActive(path) }"
        >{{ label }}</router-link>
      </nav>
      <nav class="nav-group management-nav" aria-label="管理区">
        <span class="nav-label">管理</span>
        <router-link
          v-for="[path, label] in management"
          :key="path"
          :to="path"
          :class="{ active: isActive(path) }"
        >{{ label }}</router-link>
      </nav>
      <el-dropdown trigger="click" class="theme-menu" @command="chooseTheme">
        <button type="button" class="theme-button" data-test="theme-toggle">
          <span class="theme-dot" :class="theme.effective" />
          主题
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="system" data-test="theme-option-system">跟随系统</el-dropdown-item>
            <el-dropdown-item command="light" data-test="theme-option-light">浅色</el-dropdown-item>
            <el-dropdown-item command="dark" data-test="theme-option-dark">深色</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <span class="mode">{{ themeLabels[theme.mode] }} · LOCAL RESEARCH TERMINAL</span>
    </el-header>
    <el-main><router-view /></el-main>
  </el-container>
</template>
