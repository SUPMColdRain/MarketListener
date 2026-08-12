/** Typed local API helpers plus strict display formatting.
 *
 * 缺失值统一渲染为“暂无数据”，禁止 undefined/null/NaN/Invalid Date 出现在界面。
 */

export type QueryParams = Record<string, string | number | undefined>;

type CacheOptions = { ttlMs?: number; persist?: boolean; force?: boolean; signal?: AbortSignal };
type CachedValue<T> = { value: T; savedAt: number };
const memoryCache = new Map<string, CachedValue<unknown>>();
const inFlight = new Map<string, Promise<unknown>>();
const CACHE_PREFIX = "marketlistener.query.v1:";

function queryKey(path: string, params?: QueryParams): string {
  const pairs = Object.entries(params ?? {}).filter(([, value]) => value !== undefined && value !== "").sort(([a], [b]) => a.localeCompare(b));
  return `${path}?${new URLSearchParams(pairs.map(([key, value]) => [key, String(value)])).toString()}`;
}

function readPersistent<T>(key: string): CachedValue<T> | undefined {
  try { const raw = localStorage.getItem(CACHE_PREFIX + key); return raw ? JSON.parse(raw) as CachedValue<T> : undefined; } catch { return undefined; }
}
function writePersistent<T>(key: string, entry: CachedValue<T>): void {
  try { localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry)); } catch { /* storage may be unavailable/full */ }
}
export function invalidateQuery(path: string, params?: QueryParams): void {
  const key = queryKey(path, params); memoryCache.delete(key); try { localStorage.removeItem(CACHE_PREFIX + key); } catch { /* ignore */ }
}

function fetchQuery<T>(url: URL, key: string, options: CacheOptions): Promise<T> {
  const request = fetch(url.toString(), { signal: options.signal }).then(async response => {
    if (!response.ok) throw new Error(await errorMessage(response));
    const value = await response.json() as T; const entry = { value, savedAt: Date.now() }; memoryCache.set(key, entry);
    if (options.persist) writePersistent(key, entry); return value;
  }).finally(() => inFlight.delete(key));
  inFlight.set(key, request); return request;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string") return message;
    }
  } catch {
    // non-JSON error body; fall through to status text
  }
  return `请求失败 (${response.status})`;
}

export async function apiGet<T>(path: string, params?: QueryParams, options: CacheOptions = {}): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
  }
  const key = queryKey(path, params); const ttlMs = options.ttlMs ?? 30_000;
  const cached = (memoryCache.get(key) as CachedValue<T> | undefined) ?? (options.persist ? readPersistent<T>(key) : undefined);
  if (!options.force && cached) {
    memoryCache.set(key, cached);
    if (Date.now() - cached.savedAt < ttlMs) return cached.value;
    // Stale-while-revalidate: retain visible cached data, refresh silently.
    if (!inFlight.has(key)) void fetchQuery<T>(url, key, { ...options, signal: undefined }).catch(() => undefined);
    return cached.value;
  }
  if (!options.force && inFlight.has(key)) return inFlight.get(key) as Promise<T>;
  return fetchQuery<T>(url, key, options);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(path, { method: "DELETE" });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
}

export function formatNumber(value?: number | null, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("zh-CN", { maximumFractionDigits: digits })
    : "暂无数据";
}

export function formatPct(value?: number | null, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(digits)}%` : "暂无数据";
}

export function formatMoney(value?: number | null, currency = "¥"): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${currency}${value.toLocaleString("zh-CN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`
    : "暂无数据";
}

export function formatBytes(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "暂无数据";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

const TIME_ZONE = "Asia/Shanghai";
const STATUS_LABELS: Record<string, string> = {
  QUEUED: "排队中",
  RUNNING: "执行中",
  PASS: "通过",
  PASSED: "通过",
  SUCCESS: "成功",
  OK: "正常",
  FRESH: "新鲜",
  PARTIAL_FAILURE: "部分失败",
  FAILED: "失败",
  ERROR: "错误",
  CANCELLED: "已取消",
  BLOCKED: "受阻",
  STALE: "已过期",
  IMPLEMENTED_UNVERIFIED: "已实现，未实测",
  BLOCKED_CONFIGURATION: "配置/授权受阻",
  UNREGISTERED_SOURCE: "未注册来源",
  UNKNOWN: "未知",
};
const CATEGORY_LABELS: Record<string, string> = {
  Operation: "任务操作",
  Market: "行情",
  F10: "F10 资料",
  Report: "研报",
  Industry: "产业链",
  Android: "Android",
  Provider: "数据源",
  Quality: "数据质量",
};
const OPERATION_LABELS: Record<string, string> = {
  MARKET_UPDATE: "更新行情",
  F10_UPDATE_CN: "更新 A 股 F10",
  F10_UPDATE_HK: "更新港股 F10",
  REVENUE_UPDATE: "更新收入构成",
  REPORT_PROCESS: "处理研报",
  REPORT_VERIFY: "校验研报",
  CHAIN_REBUILD: "重建产业链",
  ATLAS_BUILD: "构建产业链图谱",
  ANDROID_PACKAGE_BUILD: "构建 Android 同步包",
  STATUS_REFRESH: "刷新状态",
};

export function formatStatus(value?: string | null): string {
  if (!value) return "暂无数据";
  return STATUS_LABELS[value.toUpperCase()] ?? value;
}

export function formatCategory(value?: string | null): string {
  if (!value) return "暂无数据";
  return CATEGORY_LABELS[value] ?? value;
}

export function formatOperation(value?: string | null): string {
  if (!value) return "暂无数据";
  return OPERATION_LABELS[value.toUpperCase()] ?? value;
}

const MARKET_LABELS: Record<string, string> = {
  CN: "中国大陆（A股）",
  HK: "香港（港股）",
  GLOBAL: "全球市场",
};
const ASSET_TYPE_LABELS: Record<string, string> = {
  STOCK: "个股",
  ETF: "交易型开放式指数基金（ETF）",
  INDEX: "指数",
  FUTURE: "期货",
  CRYPTO: "加密资产",
  MACRO: "宏观指标",
};
const PERIOD_LABELS: Record<string, string> = {
  "1m": "1分钟",
  "5m": "5分钟",
  "15m": "15分钟",
  "30m": "30分钟",
  "1h": "1小时",
  "2h": "2小时",
  "4h": "4小时",
  "1d": "日线",
  "1w": "周线",
  "1mo": "月线",
};
const FIELD_LABELS: Record<string, string> = {
  open: "开盘价",
  high: "最高价",
  low: "最低价",
  close: "收盘价",
  volume: "成交量",
  amount: "成交额",
  open_interest: "持仓量",
  pct_change: "涨跌幅",
  amplitude: "振幅",
  code: "证券代码",
  market: "市场",
  date: "日期",
};

export function formatMarket(value?: string | null): string {
  if (!value) return "暂无数据";
  return MARKET_LABELS[value.toUpperCase()] ?? value;
}

export function formatAssetType(value?: string | null): string {
  if (!value) return "暂无数据";
  return ASSET_TYPE_LABELS[value.toUpperCase()] ?? value;
}

export function formatPeriod(value?: string | null): string {
  if (!value) return "暂无数据";
  return PERIOD_LABELS[value] ?? value;
}

export function formatField(value?: string | null): string {
  if (!value) return "暂无数据";
  return FIELD_LABELS[value.toLowerCase()] ?? value;
}

export function formatTime(value?: string | null): string {
  if (!value) return "暂无数据";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无数据";
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const fields = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${fields.year}-${fields.month}-${fields.day} ${fields.hour}:${fields.minute}:${fields.second}`;
}
