<script setup lang="ts">
import { onMounted, ref } from "vue";
import { formatOperation, formatStatus, formatTime } from "../domain/api";

type OperationStatus = "QUEUED" | "RUNNING" | "PASS" | "PARTIAL_FAILURE" | "FAILED" | "CANCELLED";
interface Operation { operation_id: string; kind: string; status: OperationStatus; created_at: string; detail?: string }
interface Health { stats?: { run_count?: number; partition_count?: number; quarantine_count?: number; storage_bytes?: number } }

const operations = ref<Operation[]>([]);
const health = ref<Health>({});
const busy = ref<string | null>(null);
const error = ref("");
const operationButtons = [
  ["MARKET_UPDATE", "更新行情"], ["F10_UPDATE_CN", "更新 A 股 F10"], ["F10_UPDATE_HK", "更新港股 F10"],
  ["REVENUE_UPDATE", "更新收入构成"], ["REPORT_PROCESS", "处理研报"], ["REPORT_VERIFY", "校验研报"],
  ["CHAIN_REBUILD", "重建产业链"], ["ATLAS_BUILD", "构建 Atlas"], ["ANDROID_PACKAGE_BUILD", "构建 Android 同步包"],
  ["STATUS_REFRESH", "刷新状态"],
] as const;

async function refresh() {
  const [healthResponse, operationResponse] = await Promise.all([fetch("/api/health"), fetch("/api/operations")]);
  if (healthResponse.ok) health.value = await healthResponse.json() as Health;
  if (operationResponse.ok) operations.value = (await operationResponse.json() as { items: Operation[] }).items;
}

async function submit(kind: string) {
  busy.value = kind;
  error.value = "";
  try {
    const response = await fetch("/api/operations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind }) });
    if (!response.ok) throw new Error("操作创建被拒绝");
    await refresh();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "操作创建失败";
  } finally {
    busy.value = null;
  }
}

async function cancel(operation: Operation) {
  await fetch(`/api/operations/${encodeURIComponent(operation.operation_id)}/cancel`, { method: "POST" });
  await refresh();
}

onMounted(() => { void refresh(); });
</script>

<template>
  <section>
    <h1 class="page-title">首页</h1>
    <p class="page-note">所有写入操作都由本机受控 OperationManager 串行执行；不接受任意命令、Python 或 SQL。</p>
    <el-alert v-if="error" type="error" :title="error" :closable="false" class="page-alert" />
    <section class="home-stats">
      <div class="metric"><span>运行记录</span><strong>{{ health.stats?.run_count ?? "—" }}</strong></div>
      <div class="metric"><span>数据分区</span><strong>{{ health.stats?.partition_count ?? "—" }}</strong></div>
      <div class="metric"><span>隔离问题</span><strong>{{ health.stats?.quarantine_count ?? "—" }}</strong></div>
      <div class="metric"><span>存储字节</span><strong>{{ health.stats?.storage_bytes?.toLocaleString() ?? "—" }}</strong></div>
    </section>
    <section class="panel"><h2>受控操作</h2><div class="operation-buttons"><el-button v-for="[kind,label] in operationButtons" :key="kind" :loading="busy === kind" @click="submit(kind)">{{ label }}</el-button></div></section>
    <section class="panel"><div class="panel-title"><h2>任务队列</h2><el-button text @click="refresh">刷新</el-button></div><el-table :data="operations" empty-text="暂无操作记录"><el-table-column label="操作" min-width="170"><template #default="scope">{{ formatOperation(scope.row.kind) }}</template></el-table-column><el-table-column label="状态" width="150"><template #default="scope"><el-tag :type="scope.row.status === 'FAILED' ? 'danger' : scope.row.status === 'PASS' ? 'success' : 'warning'">{{ formatStatus(scope.row.status) }}</el-tag></template></el-table-column><el-table-column label="创建时间" min-width="180"><template #default="scope">{{ formatTime(scope.row.created_at) }}</template></el-table-column><el-table-column prop="detail" label="结果" min-width="240" /><el-table-column label="" width="80"><template #default="scope"><el-button v-if="scope.row.status === 'QUEUED'" text type="danger" @click="cancel(scope.row)">取消</el-button></template></el-table-column></el-table></section>
  </section>
</template>
