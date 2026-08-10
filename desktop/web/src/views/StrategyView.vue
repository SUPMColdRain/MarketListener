<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { apiGet, apiPost, formatNumber, formatTime } from "../domain/api";

interface StrategyDefinition {
  strategyId: string;
  strategyVersion: string;
  inputs: string[];
  parameters: Record<string, number | boolean | string>;
  description: string;
  updatedAt: string;
}

interface StrategyHistoryItem {
  runId: string;
  strategyId: string;
  strategyVersion: string;
  dataVersion: string;
  parameterVersion: string;
  startedAt: string;
  finishedAt: string;
  status: string;
  error?: unknown;
  instrumentCount: number;
  signalCount: number;
}

interface StrategySignalRow {
  instrumentId: string;
  barCount: number;
  signalCount: number;
  signals: unknown[];
}

interface StrategyRunResponse {
  report?: {
    runId?: string;
    strategyId?: string;
    status?: string;
    startedAt?: string;
    finishedAt?: string;
    instrumentCount?: number;
    totalSignals?: number;
  };
  signals?: StrategySignalRow[];
}

const definitions = ref<StrategyDefinition[]>([]);
const history = ref<StrategyHistoryItem[]>([]);
const selected = ref<StrategyDefinition | null>(null);
const parameterValues = ref<Record<string, number | boolean | string>>({});
const loading = ref(false);
const running = ref(false);
const error = ref("");
const runResult = ref<StrategyRunResponse | null>(null);

const selectedInputs = computed(() => selected.value?.inputs ?? []);
const parameterKeys = computed(() => Object.keys(parameterValues.value));

function pick(definition: StrategyDefinition): void {
  selected.value = definition;
  parameterValues.value = { ...definition.parameters };
  runResult.value = null;
  error.value = "";
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [definitionData, historyData] = await Promise.all([
      apiGet<{ items: StrategyDefinition[]; total: number }>("/api/strategy/definitions"),
      apiGet<{ items: StrategyHistoryItem[]; total: number; limit: number }>("/api/strategy/history", { limit: 100 }),
    ]);
    definitions.value = definitionData.items;
    history.value = historyData.items;
    if (definitions.value.length > 0 && !selected.value) pick(definitions.value[0]);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "策略数据加载失败";
  } finally {
    loading.value = false;
  }
}

async function runSelected(): Promise<void> {
  if (!selected.value) return;
  running.value = true;
  error.value = "";
  runResult.value = null;
  try {
    runResult.value = await apiPost<StrategyRunResponse>("/api/strategy/run", {
      strategyId: selected.value.strategyId,
      parameters: parameterValues.value,
    });
    const refreshed = await apiGet<{ items: StrategyHistoryItem[] }>("/api/strategy/history", { limit: 100 });
    history.value = refreshed.items;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "策略运行失败";
  } finally {
    running.value = false;
  }
}

function statusType(status: string): "success" | "danger" | "warning" | "info" {
  const value = (status || "").toUpperCase();
  if (value === "PASS" || value === "DONE" || value === "SUCCESS") return "success";
  if (value === "FAILED" || value === "ERROR") return "danger";
  return value ? "warning" : "info";
}

onMounted(() => void load());
</script>

<template>
  <section>
    <div class="page-heading">
      <div>
        <h1 class="page-title">策略</h1>
        <p class="page-note">本地 Strategy DSL 定义、扫描运行与历史记录；只执行仓库内持久化的策略定义，不接受任意代码。</p>
      </div>
      <el-button :loading="loading" data-test="strategy-refresh" @click="void load()">刷新</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" class="page-alert" />

    <section v-if="definitions.length === 0 && !loading" class="panel empty-state" data-test="strategy-empty">
      <h2>暂无策略定义</h2>
      <p class="muted">本地 <code>data_control/strategies/definitions/*.json</code> 为空时，工作台显示空态而不是伪造策略。</p>
    </section>

    <div v-else class="strategy-layout">
      <section class="panel strategy-list-panel">
        <h2>策略定义</h2>
        <el-table :data="definitions" v-loading="loading" height="380" highlight-current-row empty-text="暂无策略定义" data-test="strategy-table" @row-click="pick">
          <el-table-column prop="strategyId" label="ID" min-width="150" />
          <el-table-column prop="strategyVersion" label="版本" width="90" />
          <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
        </el-table>
      </section>

      <section v-if="selected" class="panel strategy-detail-panel">
        <div class="panel-title">
          <h2>{{ selected.strategyId }}</h2>
          <el-tag size="small">v{{ selected.strategyVersion || "暂无数据" }}</el-tag>
        </div>
        <p class="muted">{{ selected.description || "暂无数据" }}</p>
        <p class="muted">更新于 {{ formatTime(selected.updatedAt) }}</p>

        <div v-if="selectedInputs.length" class="strategy-section">
          <h3>输入</h3>
          <el-tag v-for="input in selectedInputs" :key="input" size="small" class="product-tag">{{ input }}</el-tag>
        </div>

        <div v-if="parameterKeys.length" class="strategy-section">
          <h3>参数</h3>
          <div class="parameter-grid">
            <div v-for="key in parameterKeys" :key="key" class="parameter-row">
              <label :for="`param-${key}`">{{ key }}</label>
              <el-input-number
                v-if="typeof parameterValues[key] === 'number'"
                :id="`param-${key}`"
                v-model="parameterValues[key] as number"
                :controls="false"
                size="small"
                data-test="strategy-parameter"
              />
              <el-switch
                v-else-if="typeof parameterValues[key] === 'boolean'"
                :id="`param-${key}`"
                v-model="parameterValues[key] as boolean"
                size="small"
                data-test="strategy-parameter"
              />
              <el-input
                v-else
                :id="`param-${key}`"
                v-model="parameterValues[key] as string"
                size="small"
                data-test="strategy-parameter"
              />
            </div>
          </div>
        </div>

        <el-button type="primary" :loading="running" data-test="strategy-run" @click="void runSelected()">运行策略</el-button>

        <div v-if="runResult" class="strategy-section run-result" data-test="strategy-result">
          <h3>运行结果</h3>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="Run ID">{{ runResult.report?.runId || "暂无数据" }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ runResult.report?.status || "暂无数据" }}</el-descriptions-item>
            <el-descriptions-item label="标的数">{{ formatNumber(runResult.report?.instrumentCount, 0) }}</el-descriptions-item>
            <el-descriptions-item label="信号数">{{ formatNumber(runResult.report?.totalSignals, 0) }}</el-descriptions-item>
          </el-descriptions>
          <el-table v-if="runResult.signals?.length" :data="runResult.signals" size="small" max-height="240">
            <el-table-column prop="instrumentId" label="标的" min-width="150" />
            <el-table-column prop="barCount" label="K线数" width="90" align="right" />
            <el-table-column prop="signalCount" label="信号数" width="90" align="right" />
          </el-table>
        </div>
      </section>
    </div>

    <section class="panel">
      <div class="panel-title">
        <h2>运行历史</h2>
        <span class="muted">{{ history.length }} 条</span>
      </div>
      <el-table :data="history" empty-text="暂无运行记录" max-height="420" data-test="strategy-history">
        <el-table-column prop="runId" label="Run ID" min-width="150" />
        <el-table-column prop="strategyId" label="策略" min-width="140" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="scope"><el-tag size="small" :type="statusType(scope.row.status)">{{ scope.row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="instrumentCount" label="标的数" width="90" align="right" />
        <el-table-column prop="signalCount" label="信号数" width="90" align="right" />
        <el-table-column label="开始时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.startedAt) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" min-width="170">
          <template #default="scope">{{ formatTime(scope.row.finishedAt) }}</template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>
