/** Typed local API helpers plus strict display formatting.
 *
 * 缺失值统一渲染为“暂无数据”，禁止 undefined/null/NaN/Invalid Date 出现在界面。
 */

export type QueryParams = Record<string, string | number | undefined>;

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

export async function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
  }
  const response = await fetch(url.toString());
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
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

export function formatTime(value?: string | null): string {
  if (!value) return "暂无数据";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无数据";
  return date.toLocaleString("zh-CN", { hour12: false });
}
