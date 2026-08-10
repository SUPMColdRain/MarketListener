export interface MoneySnapshot {
  value: number;
  currency: string;
  asOf: string;
  source: string;
}

export interface RevenueSegment {
  name: string;
  amount?: MoneySnapshot;
  ratio?: number;
  segmentType?: string;
}

export interface CompanySummary {
  instrumentKey: string;
  name: string;
  code: string;
  market: "CN" | "HK";
  companyHighlight?: string;
  totalMarketCap?: MoneySnapshot;
  floatMarketCap?: MoneySnapshot;
  companyIntro?: string;
  industry?: string;
  csrcIndustry?: string;
  mainBusiness?: string;
  topRevenueSegment?: RevenueSegment;
  products?: string[];
  source?: string;
  updatedAt?: string;
}

export interface CompanyDetail extends CompanySummary {
  businessScope?: string;
  revenueSegments?: RevenueSegment[];
  chainLocations?: Array<Record<string, string>>;
  sources?: string[];
  status?: string;
}

export interface CompanyPage {
  items: CompanySummary[];
  total: number;
  page: number;
  pageSize: number;
}

export function textOrNone(value?: string | null): string {
  return value?.trim() || "暂无数据";
}

export function formatMoney(snapshot?: MoneySnapshot): string {
  if (!snapshot || !Number.isFinite(snapshot.value) || snapshot.value <= 0 || !snapshot.currency || !snapshot.asOf) {
    return "暂无数据";
  }
  const scale = snapshot.value >= 100_000_000 ? 100_000_000 : 1;
  const amount = snapshot.value / scale;
  const unit = scale === 100_000_000 ? "亿" : "";
  return `${amount.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}${unit} ${snapshot.currency} · ${snapshot.asOf}`;
}

export function formatRevenue(segment?: RevenueSegment): string {
  if (!segment?.name) return "暂无数据";
  const ratio = typeof segment.ratio === "number" && Number.isFinite(segment.ratio) ? ` · ${(segment.ratio * 100).toFixed(1)}%` : "";
  return `${segment.name}${ratio}`;
}
