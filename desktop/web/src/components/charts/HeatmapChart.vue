<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useThemeStore } from "../../stores/theme";

export interface HeatmapCell {
  x: number;
  y: number;
  value: number;
}

const props = withDefaults(
  defineProps<{
    title?: string;
    x: string[];
    y: string[];
    cells: HeatmapCell[];
    height?: number;
  }>(),
  { title: "", height: 320, x: () => [], y: () => [], cells: () => [] },
);

const theme = useThemeStore();
const element = ref<HTMLElement>();
let chart: echarts.ECharts | undefined;

const hasData = computed(() => props.cells.length > 0 && props.x.length > 0 && props.y.length > 0);

const range = computed(() => {
  const values = props.cells.map((cell) => Number(cell.value)).filter(Number.isFinite);
  if (values.length === 0) return { min: 0, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  return { min, max };
});

function render(): void {
  if (!element.value || !hasData.value) return;
  chart ??= echarts.init(element.value);
  const palette = theme.palette;
  chart.setOption(
    {
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        backgroundColor: palette.chartTooltip,
        borderColor: palette.chartTooltipBorder,
        textStyle: { color: palette.textPrimary, fontSize: 12 },
        formatter: (params: unknown) => {
          const item = params as { value: [number, number, number] };
          const xLabel = props.x[item.value[0]] ?? "?";
          const yLabel = props.y[item.value[1]] ?? "?";
          return `${yLabel} · ${xLabel}<br/><strong>${item.value[2]}</strong>`;
        },
      },
      grid: { left: 96, right: 24, top: 18, bottom: 58 },
      xAxis: {
        type: "category",
        data: props.x,
        splitArea: { show: true, areaStyle: { color: ["rgba(0,0,0,0)"] } },
        axisLine: { lineStyle: { color: palette.chartGrid } },
        axisLabel: { color: palette.chartAxis, fontSize: 11, rotate: props.x.length > 8 ? 28 : 0 },
        axisTick: { show: false },
      },
      yAxis: {
        type: "category",
        data: props.y,
        splitArea: { show: true, areaStyle: { color: ["rgba(0,0,0,0)"] } },
        axisLine: { lineStyle: { color: palette.chartGrid } },
        axisLabel: { color: palette.chartAxis, fontSize: 11 },
        axisTick: { show: false },
      },
      visualMap: {
        min: range.value.min,
        max: range.value.max,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 6,
        itemWidth: 12,
        itemHeight: 96,
        textStyle: { color: palette.chartAxis, fontSize: 10 },
        inRange: {
          color: [palette.surfaceElevated, palette.accentSoft, palette.accent],
        },
      },
      series: [
        {
          name: props.title,
          type: "heatmap",
          data: props.cells.map((cell) => [cell.x, cell.y, Number(cell.value)]),
          label: { show: false },
          emphasis: {
            itemStyle: {
              shadowBlur: 8,
              shadowColor: "rgba(0,0,0,0.35)",
              borderColor: palette.textPrimary,
              borderWidth: 1,
            },
          },
        },
      ],
    },
    true,
  );
}

function resize(): void {
  chart?.resize();
}

watch(
  () => [props.x, props.y, props.cells, theme.palette],
  () => void nextTick(render),
  { deep: true },
);

onMounted(() => {
  void nextTick(render);
  window.addEventListener("resize", resize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chart?.dispose();
  chart = undefined;
});
</script>

<template>
  <div class="heatmap-chart chart-box" :style="{ height: `${height}px` }">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="element" class="chart-root" />
    <div v-if="!hasData" class="chart-empty">暂无该指标数据</div>
  </div>
</template>

<style scoped>
.heatmap-chart { position: relative; width: 100%; }
.chart-title {
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 2;
  font-size: 12px;
  font-weight: 600;
  color: var(--ml-text-secondary);
  pointer-events: none;
}
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
