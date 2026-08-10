<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiGet, formatMoney, formatNumber, formatPct, formatTime } from "../domain/api";
import SeriesChart, { type NamedSeries } from "../components/charts/SeriesChart.vue";

interface NavPoint {
  t: string;
  nav: number;
  cash: number;
  positionValue: number;
  exposurePct: number;
  markedWithFallback?: boolean;
}

interface StatsSummary {
  available: boolean;
  navCurve?: NavPoint[];
  totalReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  winRatePct?: number | null;
  profitFactor?: number | null;
  grossProfit?: number | null;
  grossLoss?: number | null;
  feesTotal?: number | null;
  realizedTotal?: number | null;
  averageExposurePct?: number | null;
  maxExposurePct?: number | null;
  realizedByStrategy?: Record<string, number>;
  realizedByInstrument?: Record<string, number>;
  unrealizedByStrategy?: Record<string, number>;
  unrealizedByInstrument?: Record<string, number>;
  unrealizedTotal?: number | null;
  generatedAt?: string;
}

interface TradeRow {
  instrumentId: string;
  side: string;
  quantity: number;
  price: number;
  executedAt: string;
  fees?: Array<{ kind?: string; amount?: number }>;
  strategyId?: string | null;
  orderGroupId?: string | null;
  note?: string | null;
}

interface PositionRow {
  instrumentId: string;
  quantity: number;
  averageCost: number;
  marketValue: number;
  unrealizedPnl: number;
  updatedAt: string;
}

const summary = ref<StatsSummary>({ available: false });
const trades = ref<TradeRow[]>([]);
const positions = ref<PositionRow[]>([]);
const loading = ref(false);
const error = ref("");

const navSeries = ref<NamedSeries[]>([]);

function buildNavSeries(curve: NavPoint[]): NamedSeries[] {
  const points = (key: "nav" | "cash" | "positionValue") =>
    curve.map((point) => ({ t: point.t, value: Number(point[key]) }));
  return [
    { name: "净值", points: points("nav") },
    { name: "现金", points: points("cash") },
    { name: "持仓市值", points: points("positionValue") },
  ];
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    summary.value = await apiGet<StatsSummary>("/api/stats/summary");
    if (!summary.value.available) {
      trades.value = [];
      positions.value = [];
      navSeries.value = [];
      return;
    }
    navSeries.value = buildNavSeries(summary.value.navCurve ?? []);
    const [tradeData, positionData] = await Promise.all([
      apiGet<{ items: TradeRow[]; total: number }>("/api/stats/trades", { page: 1, pageSize: 200 }),
      apiGet<{ items: PositionRow[]; total: number }>("/api/stats/positions"),
    ]);
    trades.value = tradeData.items;
    positions.value = positionData.items;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "交易统计加载失败";
  } finally {
    loading.value = false;
  }
}

function sideType(side: string): "danger" | "success" {
  return side === "BUY" ? "danger" : "success";
}

onMounted(() => void load());
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <h1 class="page-title">统计</h1>
        <p class="page-note">本地交易台账（ledger.jsonl）的资产曲线、回撤、胜率与盈亏分布；无台账时显示空态。</p>
      </div>
      <el-button :loading="loading" data-test="stats-refresh" @click="void load()">刷新</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" class="page-alert" />

    <section v-if="!summary.available && !loading" class="panel empty-state" data-test="stats-empty">
      <h2>暂无交易统计数据</h2>
      <p class="muted">本机 <code>data_control/personal/ledger.jsonl</code> 暂无有效交易或资金记录；工作台不会用零值伪造收益曲线。</p>
    </section>

    <template v-else-if="summary.available">
      <section class="overview-strip">
        <div class="metric compact"><span>总收益</span><strong>{{ formatPct(summary.totalReturnPct) }}</strong></div>
        <div class="metric compact"><span>最大回撤</span><strong>{{ formatPct(summary.maxDrawdownPct) }}</strong></div>
        <div class="metric compact"><span>胜率</span><strong>{{ formatPct(summary.winRatePct) }}</strong></div>
        <div class="metric compact"><span>盈亏比</span><strong>{{ formatNumber(summary.profitFactor) }}</strong></div>
        <div class="metric compact"><span>已实现</span><strong>{{ formatMoney(summary.realizedTotal) }}</strong></div>
        <div class="metric compact"><span>未实现</span><strong>{{ formatMoney(summary.unrealizedTotal) }}</strong></div>
        <div class="metric compact"><span>总费用</span><strong>{{ formatMoney(summary.feesTotal) }}</strong></div>
        <div class="metric compact"><span>平均/最大敞口</span><strong class="small">{{ formatPct(summary.averageExposurePct) }} / {{ formatPct(summary.maxExposurePct) }}</strong></div>
      </section>

      <section class="panel">
        <div class="panel-title">
          <h2>资产曲线</h2>
          <span class="muted">{{ formatTime(summary.generatedAt) }}</span>
        </div>
        <SeriesChart :series="navSeries" unit="金额" :height="300" data-test="nav-curve" />
      </section>

      <div class="stats-grid">
        <section class="panel">
          <h2>按策略已实现</h2>
          <el-table :data="Object.entries(summary.realizedByStrategy ?? {}).map(([name, value]) => ({ name, value }))" size="small" max-height="260" empty-text="暂无数据">
            <el-table-column prop="name" label="策略" min-width="140" />
            <el-table-column label="已实现" width="140" align="right">
              <template #default="scope">{{ formatMoney(scope.row.value) }}</template>
            </el-table-column>
          </el-table>
        </section>
        <section class="panel">
          <h2>按标的已实现</h2>
          <el-table :data="Object.entries(summary.realizedByInstrument ?? {}).map(([name, value]) => ({ name, value }))" size="small" max-height="260" empty-text="暂无数据">
            <el-table-column prop="name" label="标的" min-width="140" />
            <el-table-column label="已实现" width="140" align="right">
              <template #default="scope">{{ formatMoney(scope.row.value) }}</template>
            </el-table-column>
          </el-table>
        </section>
      </div>

      <section class="panel">
        <div class="panel-title">
          <h2>当前持仓</h2>
          <span class="muted">{{ positions.length }} 个</span>
        </div>
        <el-table :data="positions" size="small" empty-text="暂无持仓" max-height="320">
          <el-table-column prop="instrumentId" label="标的" min-width="150" />
          <el-table-column prop="quantity" label="数量" width="100" align="right" />
          <el-table-column label="平均成本" width="130" align="right">
            <template #default="scope">{{ formatNumber(scope.row.averageCost, 4) }}</template>
          </el-table-column>
          <el-table-column label="市值" width="130" align="right">
            <template #default="scope">{{ formatMoney(scope.row.marketValue) }}</template>
          </el-table-column>
          <el-table-column label="未实现盈亏" width="130" align="right">
            <template #default="scope">{{ formatMoney(scope.row.unrealizedPnl) }}</template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel">
        <div class="panel-title">
          <h2>交易记录</h2>
          <span class="muted">{{ trades.length }} 条（预览 200）</span>
        </div>
        <el-table :data="trades" size="small" empty-text="暂无交易" max-height="420">
          <el-table-column prop="instrumentId" label="标的" min-width="150" />
          <el-table-column prop="side" label="方向" width="80">
            <template #default="scope"><el-tag size="small" :type="sideType(scope.row.side)">{{ scope.row.side }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="100" align="right" />
          <el-table-column label="价格" width="120" align="right">
            <template #default="scope">{{ formatNumber(scope.row.price, 4) }}</template>
          </el-table-column>
          <el-table-column label="费用" width="110" align="right">
            <template #default="scope">{{ formatMoney((scope.row.fees ?? []).reduce((sum: number, fee: { amount?: number }) => sum + Number(fee.amount || 0), 0)) }}</template>
          </el-table-column>
          <el-table-column prop="strategyId" label="策略" min-width="130" />
          <el-table-column label="成交时间" min-width="170">
            <template #default="scope">{{ formatTime(scope.row.executedAt) }}</template>
          </el-table-column>
        </el-table>
      </section>
    </template>
  </section>
</template>
