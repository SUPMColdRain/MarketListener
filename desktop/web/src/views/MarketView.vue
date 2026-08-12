<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { apiDelete, apiGet, apiPost, invalidateQuery, formatAssetType, formatMarket, formatNumber, formatPeriod, formatStatus, formatTime } from "../domain/api";
import KLineChart, { type KLineBar } from "../components/charts/KLineChart.vue";

interface MarketOverview {
  generatedAt?: string;
  instruments?: number;
  rows?: number;
  markets?: Record<string, number>;
  assetTypes?: Record<string, number>;
  periods?: string[];
  latestBarAt?: string;
}

interface InstrumentRow {
  instrumentId: string;
  symbol?: string;
  name?: string;
  market?: string;
  assetType?: string;
  period?: string;
  lastClose?: number;
  lastBarAt?: string;
  source?: string;
  qualityStatus?: string;
  updatedAt?: string;
}

interface BarsResponse {
  instrumentId: string;
  period: string;
  availablePeriods: string[];
  bars: KLineBar[];
  total: number;
  lastBarAt?: string;
}

interface WatchlistItem {
  instrumentId: string;
  addedAt: string;
  note: string;
}

interface MarketGroup {
  categoryKey: string;
  market: string;
  assetType: string;
  period: string;
  instruments: number;
  rows: number;
  latestBarAt?: string;
  lastUpdatedAt?: string;
  sources: string[];
  quality: Record<string, number>;
}

const overview = ref<MarketOverview>({});
const instruments = ref<InstrumentRow[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const market = ref("");
const assetType = ref("");
const query = ref("");
const loading = ref(false);
const error = ref("");
const periods = ref<string[]>([]);
const selected = ref<InstrumentRow | null>(null);
const period = ref("1d");
const bars = ref<KLineBar[]>([]);
const barsLoading = ref(false);
const watchlistIds = ref<Set<string>>(new Set());
const groups = ref<MarketGroup[]>([]);
const expandedGroups = ref<string[]>([]);
const groupsLoaded = ref(false);
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const marketOptions = computed(() => {
  const values = new Set<string>();
  for (const key of Object.keys(overview.value.markets ?? {})) values.add(key);
  for (const row of instruments.value) if (row.market) values.add(row.market);
  return [...values].sort();
});

function qualityType(status?: string): "success" | "danger" | "warning" | "info" {
  const value = (status || "").toUpperCase();
  if (value === "PASS" || value === "OK" || value === "FRESH") return "success";
  if (value === "FAILED" || value === "ERROR" || value === "STALE") return "danger";
  return value ? "warning" : "info";
}

async function loadOverview(): Promise<void> {
  try {
    overview.value = await apiGet<MarketOverview>("/api/market/overview", undefined, { ttlMs: 5 * 60_000, persist: true });
    const available = overview.value.periods ?? [];
    periods.value = available;
    if (available.length > 0 && !available.includes(period.value)) period.value = available[0];
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "行情概览加载失败";
  }
}

async function loadInstruments(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const data = await apiGet<{ items: InstrumentRow[]; total: number }>("/api/market/instruments", {
      market: market.value || "",
      assetType: assetType.value || "",
      q: query.value.trim(),
      page: page.value,
      pageSize,
    }, { ttlMs: 60_000, persist: true });
    instruments.value = data.items;
    total.value = data.total;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "标的列表加载失败";
    instruments.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

async function loadGroups(): Promise<void> {
  try {
    const data = await apiGet<{ items: MarketGroup[] }>("/api/market/groups", undefined, { ttlMs: 10 * 60_000, persist: true });
    groups.value = data.items;
    groupsLoaded.value = true;
    if (!expandedGroups.value.length) expandedGroups.value = data.items.map((item) => item.categoryKey);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "行情分类加载失败";
  }
}

async function loadBars(instrumentId: string, wantedPeriod = period.value): Promise<void> {
  barsLoading.value = true;
  try {
    const data = await apiGet<BarsResponse>(`/api/market/instruments/${encodeURIComponent(instrumentId)}/bars`, {
      period: wantedPeriod,
      limit: 1000,
    }, { ttlMs: 10 * 60_000, persist: true });
    periods.value = data.availablePeriods;
    bars.value = data.bars;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "K线加载失败";
    bars.value = [];
  } finally {
    barsLoading.value = false;
  }
}

function select(row: InstrumentRow): void {
  selected.value = row;
  void loadBars(row.instrumentId);
}

async function loadWatchlist(): Promise<void> {
  try {
    const data = await apiGet<{ items: WatchlistItem[] }>("/api/personal/watchlist");
    watchlistIds.value = new Set(data.items.map((item) => item.instrumentId));
  } catch {
    watchlistIds.value = new Set();
  }
}

async function toggleWatchlist(row: InstrumentRow): Promise<void> {
  const instrumentId = row.instrumentId;
  if (watchlistIds.value.has(instrumentId)) {
    try {
      await apiDelete(`/api/personal/watchlist/${encodeURIComponent(instrumentId)}`);
      watchlistIds.value.delete(instrumentId);
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : "取消自选失败";
    }
  } else {
    try {
      await apiPost("/api/personal/watchlist", { instrumentId, note: "" });
      watchlistIds.value.add(instrumentId);
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : "添加自选失败";
    }
  }
  watchlistIds.value = new Set(watchlistIds.value);
}

function reload(): void {
  error.value = "";
  invalidateQuery("/api/market/overview");
  invalidateQuery("/api/market/instruments", { market: market.value || "", assetType: assetType.value || "", q: query.value.trim(), page: page.value, pageSize });
  void Promise.all([loadOverview(), loadInstruments(), loadWatchlist()]);
  if (groupsLoaded.value) { invalidateQuery("/api/market/groups"); void loadGroups(); }
}

function debounceSearch(): void { if (searchTimer) clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value = 1; void loadInstruments(); }, 300); }

watch(period, (next) => {
  if (selected.value) void loadBars(selected.value.instrumentId, next);
});

onMounted(reload);
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <h1 class="page-title">行情</h1>
        <p class="page-note">本地 Silver 行情终端的标的列表与 K 线主视图；数据只读，自选写入仅限本机。</p>
      </div>
      <el-button :loading="loading" data-test="market-refresh" @click="reload">刷新</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" class="page-alert" />

    <section class="overview-strip">
      <div class="metric compact"><span>标的数</span><strong>{{ overview.instruments ?? "暂无数据" }}</strong></div>
      <div class="metric compact"><span>K线行数</span><strong>{{ overview.rows ?? "暂无数据" }}</strong></div>
      <div class="metric compact"><span>周期</span><strong>{{ periods.length ? periods.join(" / ") : "暂无数据" }}</strong></div>
      <div class="metric compact"><span>最新K线</span><strong class="small">{{ formatTime(overview.latestBarAt) }}</strong></div>
      <div class="metric compact wide"><span>市场分布</span><strong class="small">{{ marketOptions.length ? marketOptions.map(formatMarket).join(" · ") : "暂无数据" }}</strong></div>
    </section>

    <section class="panel market-groups" data-test="market-groups">
      <div class="panel-heading"><div><h2>按市场与资产类别</h2><p class="muted">仅展示本地 Silver 中实际覆盖的数据；来源、质量与更新时间均来自已落库记录。</p></div></div>
      <el-button v-if="!groupsLoaded" text type="primary" @click="void loadGroups()">加载分类覆盖</el-button>
      <el-collapse v-else v-model="expandedGroups">
        <el-collapse-item v-for="item in groups" :key="item.categoryKey" :name="item.categoryKey">
          <template #title><span class="group-title"><strong>{{ formatMarket(item.market) }} · {{ formatAssetType(item.assetType) }}</strong><span>{{ formatPeriod(item.period) }} · {{ item.instruments }} 标的 · {{ formatNumber(item.rows) }} 行</span></span></template>
          <div class="group-details"><span>来源：{{ item.sources.join(" / ") || "暂无数据" }}</span><span>质量：{{ Object.entries(item.quality).map(([key, value]) => `${key} ${value}`).join(" · ") || "暂无数据" }}</span><span>最新K线：{{ formatTime(item.latestBarAt) }}</span><span>最后更新：{{ formatTime(item.lastUpdatedAt) }}</span></div>
        </el-collapse-item>
      </el-collapse>
    </section>

    <section class="panel market-controls">
      <el-select v-model="market" clearable placeholder="全部市场" data-test="market-filter" @change="page = 1; void loadInstruments()">
        <el-option v-for="option in marketOptions" :key="option" :label="formatMarket(option)" :value="option" />
      </el-select>
      <el-select v-model="assetType" clearable placeholder="全部类别" @change="page = 1; void loadInstruments()">
        <el-option label="A股个股 / 港股个股" value="STOCK" />
        <el-option label="A股 ETF" value="ETF" />
        <el-option label="A股 / 港股 / 全球指数" value="INDEX" />
        <el-option label="国内期货主力 / 连续" value="FUTURE" />
      </el-select>
      <el-input v-model="query" placeholder="名称 / 代码 / instrumentId" clearable data-test="market-search" @input="debounceSearch" @keyup.enter="page = 1; void loadInstruments()" />
      <el-button type="primary" :loading="loading" @click="page = 1; void loadInstruments()">查询</el-button>
      <span class="muted">{{ total }} 个标的 · 服务端筛选分页</span>
    </section>

    <div class="market-layout">
      <section class="panel market-table-panel">
        <el-table
          :data="instruments"
          v-loading="loading"
          height="540"
          highlight-current-row
          empty-text="暂无标的"
          data-test="instrument-table"
          @row-click="select"
        >
          <el-table-column label="标的" min-width="180">
            <template #default="scope">
              <strong>{{ scope.row.name || scope.row.instrumentId }}</strong>
              <small>{{ scope.row.instrumentId }} · {{ scope.row.symbol || "暂无数据" }}</small>
            </template>
          </el-table-column>
          <el-table-column label="市场" width="120"><template #default="scope">{{ formatMarket(scope.row.market) }}</template></el-table-column>
          <el-table-column label="类型" width="150"><template #default="scope">{{ formatAssetType(scope.row.assetType) }}</template></el-table-column>
          <el-table-column label="最新收盘" width="112" align="right">
            <template #default="scope">{{ formatNumber(scope.row.lastClose, 4) }}</template>
          </el-table-column>
          <el-table-column label="数据时间" width="152">
            <template #default="scope">{{ formatTime(scope.row.lastBarAt) }}</template>
          </el-table-column>
          <el-table-column label="质量" width="92">
            <template #default="scope">
              <el-tag size="small" :type="qualityType(scope.row.qualityStatus)">{{ formatStatus(scope.row.qualityStatus) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="" width="78" fixed="right">
            <template #default="scope">
              <el-button
                text
                size="small"
                :type="watchlistIds.has(scope.row.instrumentId) ? 'warning' : 'primary'"
                data-test="watchlist-toggle"
                @click.stop="void toggleWatchlist(scope.row)"
              >{{ watchlistIds.has(scope.row.instrumentId) ? "已自选" : "自选" }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          class="table-pagination"
          layout="prev, pager, next, total"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="page = $event; void loadInstruments()"
        />
      </section>

      <section class="panel chart-panel">
        <div class="chart-heading">
          <div>
            <h2>{{ selected?.name || selected?.instrumentId || "选择标的" }}</h2>
            <p class="muted">{{ selected ? `${selected.instrumentId} · ${formatMarket(selected.market)} · ${formatAssetType(selected.assetType)}` : "从左侧列表选择标的后展示 K 线" }}</p>
          </div>
          <el-radio-group v-if="periods.length" v-model="period" size="small" data-test="period-switch">
            <el-radio-button v-for="item in periods" :key="item" :value="item">{{ formatPeriod(item) }}</el-radio-button>
          </el-radio-group>
        </div>
        <div v-loading="barsLoading" class="kline-wrap">
          <KLineChart :bars="bars" :height="480" />
        </div>
      </section>
    </div>
  </section>
</template>
