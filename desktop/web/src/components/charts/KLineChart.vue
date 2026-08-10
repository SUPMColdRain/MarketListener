<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useThemeStore } from "../../stores/theme";

export interface KLineBar {
  barOpenTime?: string;
  tradingDate?: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
}

const props = withDefaults(defineProps<{ bars: KLineBar[]; height?: number }>(), {
  bars: () => [],
  height: 460,
});

const theme = useThemeStore();
const element = ref<HTMLElement>();
let chart: echarts.ECharts | undefined;

const categories = computed(() =>
  props.bars.map((bar) => String(bar.tradingDate || bar.barOpenTime || "").slice(0, 10)),
);
const candles = computed(() =>
  props.bars.map((bar) => [Number(bar.open), Number(bar.close), Number(bar.low), Number(bar.high)]),
);
const volumes = computed(() =>
  props.bars.map((bar) => ({
    value: Number(bar.volume) || 0,
    itemStyle: {
      color:
        Number(bar.close) >= Number(bar.open) ? theme.palette.priceUp : theme.palette.priceDown,
    },
  })),
);

function render(): void {
  if (!element.value || props.bars.length === 0) return;
  chart ??= echarts.init(element.value);
  const palette = theme.palette;
  chart.setOption(
    {
      backgroundColor: "transparent",
      animation: false,
      axisPointer: {
        link: [{ xAxisIndex: "all" }],
        label: { backgroundColor: palette.surfaceSelected, color: palette.textPrimary },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: palette.chartTooltip,
        borderColor: palette.chartTooltipBorder,
        textStyle: { color: palette.textPrimary, fontSize: 12 },
        confine: true,
      },
      grid: [
        { left: 64, right: 18, top: 24, height: "56%" },
        { left: 64, right: 18, top: "70%", height: "16%" },
      ],
      xAxis: [
        {
          type: "category",
          data: categories.value,
          boundaryGap: true,
          axisLine: { lineStyle: { color: palette.chartGrid } },
          axisLabel: { color: palette.chartAxis },
          axisTick: { show: false },
          min: "dataMin",
          max: "dataMax",
        },
        {
          type: "category",
          gridIndex: 1,
          data: categories.value,
          boundaryGap: true,
          axisLine: { lineStyle: { color: palette.chartGrid } },
          axisLabel: { show: false },
          axisTick: { show: false },
          min: "dataMin",
          max: "dataMax",
        },
      ],
      yAxis: [
        {
          scale: true,
          axisLabel: { color: palette.chartAxis },
          splitLine: { lineStyle: { color: palette.chartGrid } },
        },
        {
          gridIndex: 1,
          axisLabel: { show: false },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1], start: 0, end: 100 },
        {
          type: "slider",
          xAxisIndex: [0, 1],
          bottom: 4,
          height: 16,
          borderColor: palette.divider,
          backgroundColor: palette.surfaceElevated,
          fillerColor: `${palette.accent}26`,
          handleStyle: { color: palette.accent },
          textStyle: { color: palette.chartAxis },
        },
      ],
      series: [
        {
          name: "K线",
          type: "candlestick",
          data: candles.value,
          itemStyle: {
            color: palette.priceUp,
            color0: palette.priceDown,
            borderColor: palette.priceUp,
            borderColor0: palette.priceDown,
          },
        },
        {
          name: "成交量",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes.value,
        },
      ],
    },
    true,
  );
}

function resize(): void {
  chart?.resize();
}

watch(() => [props.bars, theme.palette], () => void nextTick(render), { deep: true });

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
  <div class="kline-chart chart-box" :style="{ height: `${height}px` }">
    <div ref="element" class="chart-root" />
    <div v-if="bars.length === 0" class="chart-empty">暂无K线数据</div>
  </div>
</template>

<style scoped>
.kline-chart { position: relative; width: 100%; }
.chart-root { width: 100%; height: 100%; }
.chart-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--ml-text-secondary);
  font-size: 13px;
}
</style>
