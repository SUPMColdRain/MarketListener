<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { apiGet, apiPut, formatAssetType, formatField, formatMarket, formatNumber, formatPeriod, formatStatus, formatTime } from "../domain/api";

interface Provider {
  providerId: string;
  name: string;
  type: string;
  access: string;
  endpoint: string;
  authentication: string;
  implemented: boolean;
  configured: boolean;
  priority: number;
  enabled: boolean;
  markets: string[];
  assetTypes: string[];
  periods: string[];
  fields: string[];
  status: string;
}
interface InventoryItem {
  categoryKey: string;
  market: string;
  assetType: string;
  period: string;
  instruments: number;
  rows: number;
  earliestBarAt?: string;
  latestBarAt?: string;
  lastUpdatedAt?: string;
  sources: string[];
  sourceDetails: Array<{ providerId: string; name: string; endpoint?: string | null; status: string; periods: string[]; fields: string[] }>;
  quality: Record<string, number>;
  fieldCompleteness: Record<string, number>;
}
interface Preference { primary?: string | null; fallback1?: string | null; fallback2?: string | null }
interface Payload { providers: Provider[]; inventory: InventoryItem[]; preferences: Record<string, Preference>; summary: { categories: number; rows: number; instruments: number } }

const payload = ref<Payload>({ providers: [], inventory: [], preferences: {}, summary: { categories: 0, rows: 0, instruments: 0 } });
const preferences = ref<Record<string, Preference>>({});
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const custom = ref<Record<string, string>>({});
const providerOptions = computed(() => payload.value.providers.map((item) => ({ value: item.providerId, label: `${item.name} · P${item.priority} · ${formatStatus(item.status)}` })));

function preferenceFor(key: string): Preference {
  return preferences.value[key] ?? (preferences.value[key] = { primary: null, fallback1: null, fallback2: null });
}
function completeness(item: InventoryItem): string {
  const fields = Object.entries(item.fieldCompleteness);
  if (!fields.length) return "暂无字段";
  return fields.map(([field, value]) => `${formatField(field)} ${Math.round(value * 100)}%`).join(" · ");
}
function quality(item: InventoryItem): string { return Object.entries(item.quality).map(([key, value]) => `${formatStatus(key)} ${value}`).join(" · "); }
function addCustom(key: string): void {
  const value = custom.value[key]?.trim();
  if (!value) return;
  preferenceFor(key).primary = value;
  custom.value[key] = "";
}
async function load(): Promise<void> {
  loading.value = true; error.value = "";
  try { const data = await apiGet<Payload>("/api/data-sources"); payload.value = data; preferences.value = JSON.parse(JSON.stringify(data.preferences ?? {})) as Record<string, Preference>; }
  catch (reason) { error.value = reason instanceof Error ? reason.message : "数据源盘点加载失败"; }
  finally { loading.value = false; }
}
async function save(): Promise<void> {
  saving.value = true; error.value = "";
  try { const data = await apiPut<{ preferences: Record<string, Preference> }>("/api/data-sources", { preferences: preferences.value }); preferences.value = data.preferences; }
  catch (reason) { error.value = reason instanceof Error ? reason.message : "数据源配置保存失败"; }
  finally { saving.value = false; }
}
onMounted(() => void load());
</script>

<template>
  <section>
    <div class="page-heading">
      <div><h1 class="page-title">数据源</h1><p class="page-note">只展示本机 Silver 存储和当前代码中真实实现的 Provider；未配置的付费/授权来源不会被标记为可用。</p></div>
      <div><el-button :loading="loading" @click="load">刷新盘点</el-button><el-button type="primary" :loading="saving" data-test="data-sources-save" @click="save">保存路由配置</el-button></div>
    </div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" class="page-alert" />
    <section class="overview-strip"><div class="metric compact"><span>数据类别</span><strong>{{ payload.summary.categories }}</strong></div><div class="metric compact"><span>本地记录</span><strong>{{ formatNumber(payload.summary.rows) }}</strong></div><div class="metric compact"><span>已入库行情标的（非全市场）</span><strong>{{ formatNumber(payload.summary.instruments) }}</strong></div></section>
    <section class="panel data-source-panel"><h2>本地数据类别与路由</h2><el-table :data="payload.inventory" v-loading="loading" data-test="data-source-inventory"><el-table-column label="类别" min-width="190"><template #default="scope"><strong>{{ formatMarket(scope.row.market) }} · {{ formatAssetType(scope.row.assetType) }}</strong><small>{{ formatPeriod(scope.row.period) }} · 本地路由</small></template></el-table-column><el-table-column label="实际覆盖" min-width="136"><template #default="scope">{{ scope.row.instruments }} 标的 · {{ formatNumber(scope.row.rows) }} 行<small>{{ formatTime(scope.row.earliestBarAt) }} 至 {{ formatTime(scope.row.latestBarAt) }}</small></template></el-table-column><el-table-column label="实际来源 / 接口 / 质量" min-width="300"><template #default="scope">{{ scope.row.sources.join(" / ") || "未知" }}<small v-for="detail in scope.row.sourceDetails" :key="detail.providerId">{{ detail.name }}（{{ detail.providerId }}）· {{ detail.endpoint || "未注册接口" }} · {{ formatStatus(detail.status) }}</small><small>{{ quality(scope.row) }} · {{ formatTime(scope.row.lastUpdatedAt) }}</small></template></el-table-column><el-table-column label="字段完整度" min-width="220"><template #default="scope">{{ completeness(scope.row) }}</template></el-table-column><el-table-column label="主 / 备数据源" min-width="330"><template #default="scope"><div class="source-routing"><el-select v-model="preferenceFor(scope.row.categoryKey).primary" clearable placeholder="主要数据源"><el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><el-select v-model="preferenceFor(scope.row.categoryKey).fallback1" clearable placeholder="备用数据源 1"><el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><el-select v-model="preferenceFor(scope.row.categoryKey).fallback2" clearable placeholder="备用数据源 2"><el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select><div class="custom-source"><el-input v-model="custom[scope.row.categoryKey]" placeholder="自定义数据源代号" /><el-button @click="addCustom(scope.row.categoryKey)">设为主源</el-button></div></div></template></el-table-column></el-table></section>
    <section class="panel data-source-panel"><h2>已实现 Provider 注册表</h2><el-table :data="payload.providers" v-loading="loading" data-test="provider-registry"><el-table-column prop="name" label="Provider" min-width="130"><template #default="scope"><strong>{{ scope.row.name }}</strong><small>{{ scope.row.providerId }} · {{ formatStatus(scope.row.status) }}</small></template></el-table-column><el-table-column label="访问方式 / 实际接口" min-width="300"><template #default="scope">{{ scope.row.access }}<small>{{ scope.row.endpoint }}</small></template></el-table-column><el-table-column label="能力边界" min-width="190"><template #default="scope">{{ scope.row.markets.map(formatMarket).join("/") }} · {{ scope.row.assetTypes.map(formatAssetType).join("/") }}<small>{{ scope.row.periods.map(formatPeriod).join("/") }} · {{ scope.row.fields.map(formatField).join("、") }}</small></template></el-table-column><el-table-column label="认证 / 配置" min-width="160"><template #default="scope">{{ scope.row.authentication }}<small>{{ scope.row.configured ? "当前可配置" : "未配置，不能作为可用来源" }}</small></template></el-table-column></el-table></section>
  </section>
</template>
