<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import CompanyDetailPanel from "../components/CompanyDetailPanel.vue";
import { formatMoney, type CompanyDetail, type CompanyPage, type CompanySummary } from "../domain/company";
import { apiGet, formatTime } from "../domain/api";

const route = useRoute();
const router = useRouter();
const search = ref("");
const market = ref("");
const loading = ref(false);
const error = ref("");
const page = ref<CompanyPage>({ items: [], total: 0, page: 1, pageSize: 50 });
const detail = ref<CompanyDetail | null>(null);
const detailLoading = ref(false);

const selectedKey = computed(() => String(route.params.instrumentKey || ""));

async function retryDetail(key: string): Promise<CompanyDetail> {
  try {
    return await apiGet<CompanyDetail>(`/api/f10/companies/${encodeURIComponent(key)}`, undefined, { ttlMs: 5 * 60_000, persist: true });
  } catch {
    // 本地服务在并行页面巡检时可能短暂重启连接；只对安全的只读详情重试一次。
    await new Promise((resolve) => window.setTimeout(resolve, 180));
    return apiGet<CompanyDetail>(`/api/f10/companies/${encodeURIComponent(key)}`, undefined, { ttlMs: 5 * 60_000, persist: true, force: true });
  }
}

async function loadCompanies() {
  loading.value = true;
  error.value = "";
  try {
    page.value = await apiGet<CompanyPage>("/api/f10/companies", { page: 1, page_size: 50, sort: "name", q: search.value.trim() || undefined, market: market.value || undefined }, { ttlMs: 60_000, persist: true });
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "企业列表加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadDetail(key = selectedKey.value) {
  if (!key) {
    detail.value = null;
    return;
  }
  detailLoading.value = true;
  try {
    detail.value = await retryDetail(key);
  } catch (reason) {
    detail.value = null;
    error.value = reason instanceof Error ? reason.message : "企业详情加载失败";
  } finally {
    detailLoading.value = false;
  }
}

function selectCompany(company: CompanySummary) {
  router.push(`/f10/company/${encodeURIComponent(company.instrumentKey)}`);
}

watch(selectedKey, () => void loadDetail());
onMounted(() => {
  void loadCompanies();
  void loadDetail();
});
</script>

<template>
  <section>
    <h1 class="page-title">F10 企业资料库</h1>
    <p class="page-note">仅浏览本机统一 CompanySummary / CompanyDetail 主数据；市值、日期与来源保持绑定。</p>
    <el-alert v-if="error" :title="error" type="warning" show-icon :closable="false" class="page-alert" />
    <div class="f10-layout">
      <section class="panel company-list-panel">
        <form class="company-search" @submit.prevent="loadCompanies">
          <el-input v-model="search" placeholder="公司名称、证券代码或 instrument_key" clearable />
          <el-select v-model="market" placeholder="全部市场" clearable>
            <el-option label="A 股" value="CN" />
            <el-option label="港股" value="HK" />
          </el-select>
          <el-button native-type="submit" type="primary" :loading="loading">搜索</el-button>
        </form>
        <p class="muted">{{ page.total }} 家本地企业，服务端筛选、排序和分页。</p>
        <el-table :data="page.items" v-loading="loading" height="590" @row-click="selectCompany">
          <el-table-column prop="name" label="企业" min-width="138"><template #default="scope"><strong>{{ scope.row.name }}</strong><small>{{ scope.row.code }} · {{ scope.row.market }}</small></template></el-table-column>
          <el-table-column prop="industry" label="行业" min-width="128" />
          <el-table-column label="总市值" min-width="175"><template #default="scope">{{ formatMoney(scope.row.totalMarketCap) }}</template></el-table-column>
          <el-table-column label="更新时间" min-width="170"><template #default="scope">{{ formatTime(scope.row.updatedAt) }}</template></el-table-column>
        </el-table>
      </section>
      <section class="panel detail-panel" v-loading="detailLoading">
        <CompanyDetailPanel v-if="detail" :company="detail" />
        <div v-else class="empty-detail">从左侧选择企业，或通过产业链卡片进入完整 F10。</div>
      </section>
    </div>
  </section>
</template>
