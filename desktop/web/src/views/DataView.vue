<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { apiGet, apiPut, invalidateQuery } from "../domain/api";
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
const expandedPanels = ref<Set<string>>(new Set());
interface PersonalPanel {
  id: string;
  title: string;
  metricId: string;
  chartType: "line" | "bar";
  color: string;
  opacity: number;
  rangeDays: number;
  width: "half" | "full";
  hidden: boolean;
}
const personalPanels = ref<PersonalPanel[]>([]);
const newPanelMetric = ref("market-breadth");
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

async function loadLayout(): Promise<void> {
  try {
    const payload = await apiGet<{ panels: Partial<PersonalPanel>[] }>("/api/personal/dashboard", undefined, { ttlMs: 5 * 60_000, persist: true });
    personalPanels.value = payload.panels
      .filter((panel): panel is PersonalPanel & { id: string; title: string; metricId: string } => Boolean(panel.id && panel.title && panel.metricId))
      .map((panel) => ({
        id: panel.id,
        title: panel.title,
        metricId: panel.metricId,
        chartType: panel.chartType === "bar" ? "bar" : "line",
        color: /^#[0-9a-fA-F]{6}$/.test(panel.color ?? "") ? panel.color! : "#d64b4b",
        opacity: typeof panel.opacity === "number" ? Math.min(1, Math.max(0, panel.opacity)) : 0.16,
        rangeDays: typeof panel.rangeDays === "number" ? Math.max(0, panel.rangeDays) : 0,
        width: panel.width === "full" ? "full" : "half",
        hidden: Boolean(panel.hidden),
      }));
  } catch { personalPanels.value = []; }
}
async function saveLayout(): Promise<void> { await apiPut("/api/personal/dashboard", { panels: personalPanels.value }); invalidateQuery("/api/personal/dashboard"); }
async function addPanel(): Promise<void> {
  const definition = definitions.value.find(item => item.id === newPanelMetric.value); if (!definition) return;
  personalPanels.value.push({ id: `panel-${Date.now()}`, title: definition.title, metricId: definition.id, chartType: "line", color: "#d64b4b", opacity: 0.16, rangeDays: 0, width: "half", hidden: false }); await saveLayout();
}
async function removePanel(id: string): Promise<void> { personalPanels.value = personalPanels.value.filter(panel => panel.id !== id); await saveLayout(); }
async function togglePanelHidden(panel: PersonalPanel): Promise<void> { panel.hidden = !panel.hidden; await saveLayout(); }
async function movePanel(id: string, offset: number): Promise<void> {
  const index = personalPanels.value.findIndex(panel => panel.id === id);
  const target = index + offset;
  if (index < 0 || target < 0 || target >= personalPanels.value.length) return;
  const [panel] = personalPanels.value.splice(index, 1);
  personalPanels.value.splice(target, 0, panel);
  await saveLayout();
}

async function loadDefinitions(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const data = await apiGet<{ items: DashboardDefinition[] }>("/api/dashboard/definitions", undefined, { ttlMs: 5 * 60_000, persist: true });
    definitions.value = data.items;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "数据面板加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadPanel(id: string): Promise<void> {
  expandedPanels.value.add(id); expandedPanels.value = new Set(expandedPanels.value);
  if (payloads.value[id]) return;
  try { payloads.value[id] = await apiGet<DashboardPayload>(`/api/dashboard/${encodeURIComponent(id)}`, undefined, { ttlMs: 10 * 60_000, persist: true }); }
  catch { payloads.value[id] = { available: false }; }
}

async function loadRanking(): Promise<void> {
  try {
    ranking.value = await apiGet<RankingPayload>("/api/metrics/ranking", { category: rankingCategory.value, limit: 20 }, { ttlMs: 5 * 60_000, persist: true });
  } catch {
    ranking.value = { category: rankingCategory.value, available: false, frames: [] };
  }
}

async function loadHeatmap(): Promise<void> {
  try {
    heatmap.value = await apiGet<HeatmapPayload>("/api/metrics/heatmap", { category: heatmapCategory.value, limit: 20 }, { ttlMs: 5 * 60_000, persist: true });
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
    const data = await apiGet<{ items: Record<string, unknown>[]; total: number }>(`/api/data/${encodeURIComponent(view.value)}`, { page_size: 500, q: query.value.trim() || undefined }, { ttlMs: 60_000, persist: true });
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
  invalidateQuery("/api/dashboard/definitions");
  for (const id of expandedPanels.value) { invalidateQuery(`/api/dashboard/${id}`); delete payloads.value[id]; }
  void loadDefinitions();
}

watch(view, () => void loadBrowser());
watch(rankingCategory, () => void loadRanking());
watch(heatmapCategory, () => void loadHeatmap());

onMounted(() => {
  void Promise.all([loadDefinitions(), loadLayout()]);
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

    <section class="panel">
      <div class="panel-title"><h2>我的仪表盘</h2><div><el-select v-model="newPanelMetric" size="small"><el-option v-for="item in definitions" :key="item.id" :label="item.title" :value="item.id" /></el-select><el-button size="small" type="primary" @click="void addPanel()">添加面板</el-button></div></div>
      <p v-if="!personalPanels.length" class="muted">尚未添加自定义面板。布局仅保存到本机个人配置，不会改变业务指标定义。</p>
      <div v-else class="dashboard-grid">
        <div v-for="panel in personalPanels.filter(item => !item.hidden)" :key="panel.id" class="panel dashboard-panel" :class="{ 'dashboard-panel-full': panel.width === 'full' }">
          <div class="panel-title"><h3>{{ panel.title }}</h3><div><el-button text size="small" @click="void movePanel(panel.id, -1)">上移</el-button><el-button text size="small" @click="void movePanel(panel.id, 1)">下移</el-button><el-button text size="small" @click="void togglePanelHidden(panel)">隐藏</el-button><el-button text size="small" @click="void loadPanel(panel.metricId)">加载</el-button><el-button text type="danger" size="small" @click="void removePanel(panel.id)">删除</el-button></div></div>
          <div class="data-controls personal-panel-settings"><el-input v-model="panel.title" size="small" aria-label="面板标题" @change="void saveLayout()" /><el-select v-model="panel.width" size="small" aria-label="面板宽度" @change="void saveLayout()"><el-option label="半宽" value="half" /><el-option label="整行" value="full" /></el-select><el-select v-model="panel.chartType" size="small" aria-label="图表类型" @change="void saveLayout()"><el-option label="折线图" value="line" /><el-option label="柱状图" value="bar" /></el-select><el-select v-model="panel.rangeDays" size="small" aria-label="时间范围" @change="void saveLayout()"><el-option label="全部时间" :value="0" /><el-option label="近30天" :value="30" /><el-option label="近90天" :value="90" /><el-option label="近1年" :value="365" /></el-select><input v-model="panel.color" type="color" aria-label="图表颜色" @change="void saveLayout()" /><el-slider v-model="panel.opacity" :min="0" :max="1" :step="0.05" aria-label="面积透明度" @change="void saveLayout()" /></div>
          <SeriesChart v-if="payloads[panel.metricId]?.series?.length" :title="panel.title" :series="payloads[panel.metricId]?.series ?? []" :height="240" :color="panel.color" :chart-type="panel.chartType" :opacity="panel.opacity" :range-days="panel.rangeDays" /><div v-else class="chart-empty-panel">点击“加载”读取指标</div>
        </div>
      </div>
      <div v-if="personalPanels.some(item => item.hidden)" class="hidden-panels"><span class="muted">已隐藏面板：</span><el-button v-for="panel in personalPanels.filter(item => item.hidden)" :key="panel.id" text size="small" @click="void togglePanelHidden(panel)">恢复 {{ panel.title }}</el-button></div>
    </section>

    <section v-if="availablePanels.length" class="dashboard-grid">
      <div v-for="panel in availablePanels" :key="panel.id" class="panel dashboard-panel" :data-test="`dashboard-${panel.id}`">
        <div class="panel-title">
          <h2>{{ panel.title }}</h2>
          <div><el-tag size="small">{{ panel.category }}</el-tag><el-button text size="small" @click="void loadPanel(panel.id)">{{ expandedPanels.has(panel.id) ? "已加载" : "加载面板" }}</el-button></div>
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
        <el-button v-if="!ranking.frames.length" text @click="void loadRanking()">加载排行</el-button><RankingChart v-else :frames="ranking.frames" :height="300" data-test="ranking-chart" />
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
        <el-button v-if="!heatmap.cells.length" text @click="void loadHeatmap()">加载热力图</el-button><HeatmapChart v-else :x="heatmap.x" :y="heatmap.y" :cells="heatmap.cells" :height="300" data-test="heatmap-chart" />
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
      <el-button v-if="!rows.length && !browserLoading" text @click="void loadBrowser()">加载数据浏览器</el-button><div v-if="rows.length || browserLoading" ref="chartElement" class="data-chart" />
      <el-table :data="rows" v-loading="browserLoading" max-height="520" empty-text="暂无数据">
        <el-table-column v-for="column in columns" :key="column" :prop="column" :label="column" min-width="150" show-overflow-tooltip />
      </el-table>
    </section>
  </section>
</template>
