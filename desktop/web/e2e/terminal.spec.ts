import { expect, test, type Page } from "@playwright/test";

const ROUTES = [
  ["/", "首页"],
  ["/market/", "行情"],
  ["/data/", "数据"],
  ["/data-sources/", "数据源"],
  ["/strategy/", "策略"],
  ["/stats/", "统计"],
  ["/f10/", "F10 企业资料库"],
  ["/industry/", "产业链图谱"],
  ["/logs/", "日志"],
] as const;

async function expectCleanTerminal(page: Page): Promise<void> {
  const text = await page.locator("body").innerText();
  // Raw log/dashboard JSON is allowed to contain "null"; company cards have
  // their own stricter assertions in the industry and F10 specs.
  for (const forbidden of ["undefined", "NaN", "Invalid Date"]) {
    expect(text).not.toContain(forbidden);
  }
}

test("all terminal routes are reachable and render clean text", async ({ page }) => {
  for (const [route, title] of ROUTES) {
    await page.goto(route);
    await expect(page.locator("h1.page-title")).toContainText(title, { timeout: 15_000 });
    await expectCleanTerminal(page);
  }

  await page.goto("/industry-v2/");
  await expect(page).toHaveURL(/\/industry\/$/);
  await expect(page.locator("h1.page-title")).toContainText("产业链图谱");

  await page.goto("/f10/company/CN.SZSE.STOCK.000001");
  await expect(page.locator(".company-detail")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".company-detail")).toContainText("平安银行");
  await expectCleanTerminal(page);
});

test("theme switching persists and follows the system scheme", async ({ page }) => {
  await page.goto("/");
  await page.click('[data-test="theme-toggle"]');
  await page.click('[data-test="theme-option-dark"]');
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.evaluate(() => localStorage.getItem("marketlistener.theme"))).resolves.toBe("dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.click('[data-test="theme-toggle"]');
  await page.click('[data-test="theme-option-light"]');
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.evaluate(() => localStorage.setItem("marketlistener.theme", "system"));
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("home only exposes predefined operations and rejects arbitrary payloads", async ({ page }) => {
  await page.goto("/");
  const operationButtons = page.locator(".operation-buttons button");
  await expect(operationButtons).toHaveCount(10);
  await expect(page.locator(".operation-buttons input, .operation-buttons textarea")).toHaveCount(0);

  const created = await page.request.post("/api/operations", { data: { kind: "STATUS_REFRESH" } });
  expect(created.status()).toBe(202);

  const extraField = await page.request.post("/api/operations", {
    data: { kind: "STATUS_REFRESH", sql: "delete from runs" },
  });
  expect(extraField.status()).toBe(422);

  const arbitrary = await page.request.post("/api/operations", {
    data: { kind: "__import__('os').system('whoami')" },
  });
  expect(arbitrary.status()).toBe(422);

  await page.reload();
  const queue = page.locator(".el-table").last();
  await expect(queue).toContainText("刷新状态");
  await expect(queue).not.toContainText("STATUS_REFRESH");
  await expect(queue).toContainText(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/);
});

test("data workbench is read-only, bounded and shows real dashboards", async ({ page }) => {
  const listing = await page.request.get("/api/data/f10?page_size=500");
  expect(listing.status()).toBe(200);
  const payload = (await listing.json()) as { items: unknown[] };
  expect(payload.items.length).toBeLessThanOrEqual(500);

  expect([403, 405]).toContain((await page.request.post("/api/data/f10")).status());
  expect((await page.request.get("/api/data/not_sql")).status()).toBe(404);
  expect((await page.request.get("/api/data/f10?page_size=501")).status()).toBe(422);

  await page.goto("/data/");
  await expect(page.locator('h1.page-title')).toContainText("数据");
  await expect(page.locator('[data-test="data-refresh"]')).toBeVisible();
  await expect(page.locator(".dashboard-panel").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".data-browser")).toBeVisible();
  await expect(page.locator(".data-browser .el-table__row").first()).toBeVisible({ timeout: 20_000 });
  await expectCleanTerminal(page);
});

test("F10 API and detail page share one local company model", async ({ page }) => {
  const listing = await page.request.get("/api/f10/companies?page_size=10&market=CN");
  expect(listing.status()).toBe(200);
  const payload = (await listing.json()) as {
    items: Array<{ instrumentKey: string; name: string; code: string }>;
  };
  expect(payload.items.length).toBeGreaterThan(0);
  const first = payload.items[0];
  expect(first.instrumentKey).toBeTruthy();
  expect(first.name).toBeTruthy();
  expect(first.code).toBeTruthy();

  const detailResponse = await page.request.get(
    `/api/f10/companies/${encodeURIComponent(first.instrumentKey)}`,
  );
  expect(detailResponse.status()).toBe(200);
  const detail = (await detailResponse.json()) as {
    instrumentKey: string;
    totalMarketCap?: { value: number; currency: string; asOf: string; source: string };
  };
  expect(detail.instrumentKey).toBe(first.instrumentKey);
  expect(detail.totalMarketCap?.value).toBeGreaterThan(0);
  expect(detail.totalMarketCap?.currency).toBeTruthy();
  expect(detail.totalMarketCap?.asOf).toBeTruthy();
  expect(detail.totalMarketCap?.source).toBeTruthy();

  await page.goto("/f10/");
  await expect(page.locator(".company-list-panel .el-table__row").first()).toBeVisible({
    timeout: 15_000,
  });
  await page.locator(".company-list-panel .el-table__row").first().click();
  await expect(page).toHaveURL(/\/f10\/company\//);
  await expect(page.locator(".company-detail")).toBeVisible({ timeout: 15_000 });
  await expectCleanTerminal(page);
});

test("logs API and page are bounded JSONL event views", async ({ page }) => {
  const response = await page.request.get("/api/logs?page_size=100");
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as { total: number };
  expect(payload.total).toBeGreaterThanOrEqual(0);
  expect([403, 405]).toContain((await page.request.post("/api/logs")).status());

  await page.goto("/logs/");
  await expect(page.locator("h1.page-title")).toContainText("日志");
  await expect(page.locator(".data-controls")).toBeVisible();
  await expect(page.locator(".el-table").last()).toBeVisible();
  await expectCleanTerminal(page);
});

test("industry serves only the new atlas and Android package excludes legacy map", async ({ page }) => {
  const atlasResponse = await page.request.get("/api/industry/atlas");
  expect(atlasResponse.status()).toBe(200);
  const atlasHtml = await atlasResponse.text();
  expect(atlasHtml).toContain("atlas-data");
  expect(atlasHtml).not.toContain("industry-map");

  expect((await page.request.get("/industry-map.html")).status()).toBe(404);

  const infoResponse = await page.request.get("/api/android-package-info");
  expect(infoResponse.status()).toBe(200);
  const info = (await infoResponse.json()) as { package_id: string };
  expect(info.package_id).toBeTruthy();

  const packageResponse = await page.request.get("/api/android-package");
  expect(packageResponse.status()).toBe(200);
  expect(packageResponse.headers()["content-type"]).toContain("application/zip");
});

test("market workbench lists instruments and renders the K line view", async ({ page }) => {
  await page.goto("/market/");
  await expect(page.locator('h1.page-title')).toContainText("行情");
  await expect(page.locator('[data-test="instrument-table"] .el-table__row').first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator('[data-test="instrument-table"] .el-loading-mask')).toHaveCount(0, {
    timeout: 15_000,
  });
  await page.locator('[data-test="instrument-table"] .el-table__row td').first().click();
  await expect(page.locator(".kline-wrap canvas").first()).toBeVisible({ timeout: 15_000 });
  await expectCleanTerminal(page);
});

test("data source page reports local categories and provider configuration", async ({ page }) => {
  await page.goto("/data-sources/");
  await expect(page.locator('[data-test="data-source-inventory"] .el-table__row').first()).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('[data-test="provider-registry"] .el-table__row').first()).toBeVisible();
  await expectCleanTerminal(page);
});
