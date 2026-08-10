<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useThemeStore } from "../../stores/theme";

export interface RankingItem {
  name: string;
  value: number;
}

export interface RankingFrame {
  t: string;
  items: RankingItem[];
}

const props = withDefaults(
  defineProps<{ title?: string; frames: RankingFrame[]; height?: number }>(),
  { title: "", height: 320, frames: () => [] },
);

const theme = useThemeStore();
const element = ref<HTMLElement>();
let chart: echarts.ECharts | undefined;
let timer: ReturnType<typeof setInterval> | undefined;

const currentIndex = ref(0);
const playing = ref(false);
const currentFrame = computed(() => props.frames[currentIndex.value] ?? null);
const hasData = computed(() => props.frames.length > 0);

function render(): void {
  if (!element.value || !currentFrame.value) return;
  chart ??= echarts.init(element.value);
  const palette = theme.palette;
  const items = [...currentFrame.value.items].sort((a, b) => b.value - a.value);
  chart.setOption(
    {
      backgroundColor: "transparent",
      animationDurationUpdate: 600,
      animationEasingUpdate: "cubicOut",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: palette.chartTooltip,
        borderColor: palette.chartTooltipBorder,
        textStyle: { color: palette.textPrimary, fontSize: 12 },
        confine: true,
      },
      grid: { left: 118, right: 56, top: 16, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { color: palette.chartAxis, fontSize: 11 },
        splitLine: { lineStyle: { color: palette.chartGrid } },
      },
      yAxis: {
        type: "category",
        data: items.map((item) => item.name),
        inverse: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: palette.textPrimary, fontSize: 12, width: 104, overflow: "truncate" },
      },
      series: [
        {
          name: props.title || "排名",
          type: "bar",
          data: items.map((item, index) => ({
            value: item.value,
            itemStyle: {
              color: index === 0 ? palette.highlight : palette.accent,
              borderRadius: [0, 3, 3, 0],
            },
          })),
          barMaxWidth: 18,
          label: {
            show: true,
            position: "right",
            color: palette.textSecondary,
            fontSize: 11,
            formatter: (params: unknown) => {
              const item = params as { value: number };
              return Number.isFinite(item.value) ? item.value.toLocaleString("zh-CN") : "";
            },
          },
        },
      ],
    },
    true,
  );
}

function step(direction: 1 | -1): void {
  if (props.frames.length === 0) return;
  currentIndex.value = (currentIndex.value + direction + props.frames.length) % props.frames.length;
  void nextTick(render);
}

function togglePlay(): void {
  if (props.frames.length <= 1) return;
  playing.value = !playing.value;
}

function resize(): void {
  chart?.resize();
}

watch(
  () => [currentFrame.value, theme.palette],
  () => void nextTick(render),
  { deep: true },
);

watch(
  () => props.frames,
  () => {
    currentIndex.value = 0;
    playing.value = false;
    void nextTick(render);
  },
);

watch(playing, (value) => {
  if (timer !== undefined) {
    clearInterval(timer);
    timer = undefined;
  }
  if (!value) return;
  timer = setInterval(() => {
    if (currentIndex.value >= props.frames.length - 1) {
      playing.value = false;
      return;
    }
    step(1);
  }, 1200);
});

onMounted(() => {
  void nextTick(render);
  window.addEventListener("resize", resize);
});

onBeforeUnmount(() => {
  if (timer !== undefined) clearInterval(timer);
  window.removeEventListener("resize", resize);
  chart?.dispose();
  chart = undefined;
});
</script>

<template>
  <div class="ranking-chart chart-box" :style="{ height: `${height}px` }">
    <div class="ranking-head">
      <span v-if="title" class="chart-title">{{ title }}</span>
      <span v-if="currentFrame" class="ranking-time" data-test="ranking-time">{{ currentFrame.t }}</span>
      <span v-if="frames.length > 1" class="ranking-controls">
        <button type="button" data-test="ranking-prev" @click="step(-1)">‹</button>
        <button type="button" data-test="ranking-play" @click="togglePlay">{{ playing ? "暂停" : "播放" }}</button>
        <button type="button" data-test="ranking-next" @click="step(1)">›</button>
      </span>
    </div>
    <div ref="element" class="chart-root" />
    <div v-if="!hasData" class="chart-empty">暂无该指标数据</div>
  </div>
</template>

<style scoped>
.ranking-chart { position: relative; width: 100%; }
.ranking-head {
  position: absolute;
  top: 4px;
  left: 4px;
  right: 4px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 10px;
  pointer-events: none;
}
.chart-title { font-size: 12px; font-weight: 600; color: var(--ml-text-secondary); }
.ranking-time { font-size: 11px; color: var(--ml-text-disabled); font-family: ui-monospace, Consolas, monospace; }
.ranking-controls { margin-left: auto; display: flex; gap: 4px; pointer-events: auto; }
.ranking-controls button {
  border: 1px solid var(--ml-divider);
  background: var(--ml-surface-elevated);
  color: var(--ml-text-secondary);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
}
.ranking-controls button:hover { color: var(--ml-text-primary); border-color: var(--ml-accent); }
.chart-root { width: 100%; height: 100%; }
.chart-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--ml-text-secondary);
  font-size: 13px;
  background: var(--ml-surface);
}
</style>
