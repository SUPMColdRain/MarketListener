<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { apiGet } from "../domain/api";
import SeriesChart, { type NamedSeries } from "../components/charts/SeriesChart.vue";
import HeatmapChart, { type HeatmapCell } from "../components/charts/HeatmapChart.vue";
import RankingChart, { type RankingFrame } from "../components/charts/RankingChart.vue";

interface DashboardDefinition {
  id: string;
  title: string;
  category: string;
  available: boolean;
  description: string;
}

interface DashboardPayload {
  available: boolean;
  id?: string;
  title?: string;
  unit?: string;
  series?: NamedSeries[];
  generatedAt?: string;
  source?: string;
}

interface RankingPayload {
  category: string;
  available: boolean;
  frames: RankingFrame[];
}

interface HeatmapPayload {
  category: string;
  available: boolean;
  x: string[];
  y: string[];
  cells: HeatmapCell[];
}

const browserViews = [
  ["market", "Market"],
  ["silver", "Silver"],
  ["gold", "Gold"],
  ["f10", "F10"],
  ["industry", "Industry"],
  ["runs", "Runs"],
  ["partitions", "Partitions"],
  ["quarantine", "Quarantine"],
  ["package", "Package"],
  ["storage", "Storage"],
  ["quality", "Quality"],
  ["freshness", "Freshness"],
] as const;

const definitions = ref<DashboardDefinition[]>([]);
const payloads = ref<Record<string, DashboardPayload>>({});
const loading = ref(false);
const error = ref("");
const categoryFilter = ref("");

const rankingCategory = ref("futures");
const ranking = ref<RankingPayload>({ category: "futures", available: false, frames: [] });
const heatmapCategory = ref("breadth");
const heatmap = ref<HeatmapPayload>({ category: "breadth", available: false, x: [], y: [], cells: [] });

const categories = computed(() => [...new Set(definitions.value.map((item) => item.category))].sort());
const availablePanels = computed(() =>
  definitions.value.filter(
    (item) => item.available && (!categoryFilter.value || item.category === categoryFilter.value),
  ),
);

async function loadDefinitions(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const data = await apiGet<{ items: DashboardDefinition[] }>("/api/dashboard/definitions");
    definitions.value = data.items;
    const available = data.items.filter((item) => item.available);
    await Promise.all(
      available.map(async (item) => {
        try {
          payloads.value[item.id] = await apiGet<DashboardPayload>(`/api/dashboard/${encodeURIComponent(item.id)}`);
        } catch {
          payloads.value[item.id] = { available: false };
        }
      }),
    );
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "数据面板加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadRanking(): Promise<void> {
  try {
    ranking.value = await apiGet<RankingPayload>("/api/metrics/ranking", { category: rankingCategory.value, limit: 20 });
  } catch {
    ranking.value = { category: rankingCategory.value, available: false, frames: [] };
  }
}

async function loadHeatmap(): Promise<void> {
  try {
    heatmap.value = await apiGet<HeatmapPayload>("/api/metrics/heatmap", { category: heatmapCategory.value, limit: 20 });
  } catch {
    heatmap.value = { category: heatmapCategory.value, available: false, x: [], y: [], cells: [] };
  }
}

// ---- 数据浏览器（受控只读预览 ≤500 行） ----
const view = ref("market");
const query = ref("");
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const browserLoading = ref(false);
const browserError = ref("");
const chartElement = ref<HTMLElement>();
let chart: echarts.ECharts | undefined;

const columns = computed(() => Object.keys(rows.value[0] || {}).slice(0, 8));

async function loadBrowser(): Promise<void> {
  browserLoading.value = true;
  browserError.value = "";
  try {
    const params = new URLSearchParams({ page_size: "500", q: query.value.trim() });
    const response = await fetch(`/api/data/${encodeURIComponent(view.value)}?${params}`);
    if (!response.ok) throw new Error("数据浏览器加载失败");
    const data = (await response.json()) as { items: Record<string, unknown>[]; total: number };
    rows.value = data.items;
    total.value = data.total;
    await nextTick();
    renderChart();
  } catch (reason) {
    browserError.value = reason instanceof Error ? reason.message : "数据浏览器加载失败";
    rows.value = [];
    total.value = 0;
  } finally {
    browserLoading.value = false;
  }
}

function renderChart(): void {
  if (!chartElement.value) return;
  chart ??= echarts.init(chartElement.value);
  const labels = rows.value.slice(0, 20).map((row, index) =>
    String(row.partition_id || row.provider || row.chain || row.instrumentKey || row.area || index + 1),
  );
  const values = rows.value
    .slice(0, 20)
    .map((row) => Number(row.row_count || row.rows || row.bytes || row.issue_count || row.value || 1));
  chart.setOption({
    backgroundColor: "transparent",
    grid: { top: 22, left: 55, right: 16, bottom: 58 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { color: "var(--ml-chart-axis)", rotate: 28 },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "var(--ml-chart-axis)" },
      splitLine: { lineStyle: { color: "var(--ml-chart-grid)" } },
    },
    series: [{ type: "bar", data: values, itemStyle: { color: "var(--ml-accent)" } }],
  });
}

function refreshAll(): void {
  void Promise.all([loadDefinitions(), loadRanking(), loadHeatmap(), loadBrowser()]);
}

watch(view, () => void loadBrowser());
watch(rankingCategory, () => void loadRanking());
watch(heatmapCategory, () => void loadHeatmap());

onMounted(() => {
  void Promise.all([loadDefinitions(), loadRanking(), loadHeatmap(), loadBrowser()]);
  window.addEventListener("resize", renderChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", renderChart);
  chart?.dispose();
});
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <h1 class="page-title">数据</h1>
        <p class="page-note">Grafana 风格本地只读监查：只展示真实可用的面板、排行与热力图；数据浏览器不暴露任意 SQL。</p>
      </div>
      <el-button :loading="loading" data-test="data-refresh" @click="refreshAll">刷新</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" class="page-alert" />

    <section class="panel category-filter" data-test="dashboard-categories">
      <el-radio-group v-model="categoryFilter">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="category in categories" :key="category" :value="category">{{ category }}</el-radio-button>
      </el-radio-group>
      <span class="muted">{{ availablePanels.length }} 个可用面板（无数据的面板自动隐藏）</span>
    </section>

    <section v-if="availablePanels.length" class="dashboard-grid">
      <div v-for="panel in availablePanels" :key="panel.id" class="panel dashboard-panel" :data-test="`dashboard-${panel.id}`">
        <div class="panel-title">
          <h2>{{ panel.title }}</h2>
          <el-tag size="small">{{ panel.category }}</el-tag>
        </div>
        <SeriesChart
          v-if="payloads[panel.id]?.series?.length"
          :title="panel.title"
          :series="payloads[panel.id]?.series ?? []"
          :unit="payloads[panel.id]?.unit"
          :height="260"
        />
        <div v-else class="chart-empty-panel">暂无该指标数据</div>
      </div>
    </section>
    <section v-else-if="!loading" class="panel empty-state" data-test="dashboard-empty">
      <h2>暂无可用数据面板</h2>
      <p class="muted">本地数据库尚无对应数据；只读页面不会生成假序列。</p>
    </section>

    <div class="metrics-layout">
      <section class="panel">
        <div class="panel-title">
          <h2>动态排行</h2>
          <el-select v-model="rankingCategory" size="small" data-test="ranking-category">
            <el-option label="期货净持仓" value="futures" />
            <el-option label="Gold 指标" value="gold" />
            <el-option label="市场广度" value="breadth" />
          </el-select>
        </div>
        <RankingChart :frames="ranking.frames" :height="300" data-test="ranking-chart" />
      </section>
      <section class="panel">
        <div class="panel-title">
          <h2>热力图</h2>
          <el-select v-model="heatmapCategory" size="small" data-test="heatmap-category">
            <el-option label="市场广度" value="breadth" />
            <el-option label="Gold 指标" value="gold" />
            <el-option label="存储占用" value="storage" />
          </el-select>
        </div>
        <HeatmapChart :x="heatmap.x" :y="heatmap.y" :cells="heatmap.cells" :height="300" data-test="heatmap-chart" />
      </section>
    </div>

    <section class="panel data-browser">
      <div class="panel-title">
        <h2>数据浏览器</h2>
        <span class="muted">预览最多 500 行；服务端筛选、排序、分页</span>
      </div>
      <div class="data-controls">
        <el-select v-model="view" data-test="browser-view">
          <el-option v-for="[key, label] in browserViews" :key="key" :label="label" :value="key" />
        </el-select>
        <el-input v-model="query" placeholder="服务端筛选" clearable @keyup.enter="void loadBrowser()" />
        <el-button type="primary" :loading="browserLoading" data-test="browser-query" @click="void loadBrowser()">查询</el-button>
        <span class="muted">{{ total }} 条</span>
      </div>
      <el-alert v-if="browserError" :title="browserError" type="warning" :closable="false" class="page-alert" />
      <div ref="chartElement" class="data-chart" />
      <el-table :data="rows" v-loading="browserLoading" max-height="520" empty-text="暂无数据">
        <el-table-column v-for="column in columns" :key="column" :prop="column" :label="column" min-width="150" show-overflow-tooltip />
      </el-table>
    </section>
  </section>
</template>
