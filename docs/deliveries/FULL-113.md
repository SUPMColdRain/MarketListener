# FULL-113 交付记录

**任务**：FULL-113 修复 BaoStock 字段和周期请求，验证网络、日线及复权

**角色**：独立实现
**状态建议**：`REVIEW`（按用户指示，统一审查延后到 5.1–5.9 全部实现完成后执行）

## 结果

BaoStock 适配器保持“每项能力独立探测”的语义，并补充结构化失败信息：

- 日线/30 分钟请求使用正确字段集合 `date,time,code,open,high,low,close,volume,amount,adjustflag`，周期映射为 BaoStock 的 `d`/`30`，复权参数 `adjustflag="3"`（前复权）。
- 登录、日历、K线、复权因子任一环节失败只标记对应能力 `FAILED`，不再抹掉其他结果；`FAILED` 能力现在携带结构化 `error`。
- 空结果上报 `NO_COVERAGE`，网络错误上报 `NETWORK`，均由固定响应单测覆盖。

真实探测（2026-08-06 本机，`NO_PROXY=*`）：

- `www.baostock.com:10030` DNS 解析正常（114.94.20.92），但 TCP 5 秒与 10 秒均连接超时，BaoStock SDK 登录三次均报“网络接收错误”。
- CLI 探针如实输出运行级 `FAILED/NETWORK`（`provider-run-error`），退出码 2，未伪造成成功。
- 跨源重叠对比按要求仅在可达时执行；当前 BaoStock 不可达，真实对比为 `BLOCKED`（AKShare 与 BaoStock 的 bars/factors 均为 NETWORK 错误，报告明确 `row_blending: DISABLED`）。

## 修改文件

- `desktop/src/market_monitor/providers/baostock.py`：失败能力补充结构化 `error`；无其他语义改动（字段/周期/复权映射此前已正确，本次以测试固定）。
- `desktop/tests/test_baostock_provider.py`：新增字段集合/周期/复权参数断言、登录网络错误分类、日历网络超时独立失败、空 K 线 `NO_COVERAGE` 共 4 项测试。
- `desktop/src/market_monitor/providers/akshare.py`：日线字段归一与前复权（与 FULL-110 共用改动，使重叠对比可比较）。
- `docs/deliveries/README.md` 与 `STATUS.md`：交付索引与状态更新。

未修改 Provider 契约 Schema、报告 Schema、数据库或 Android 业务行为。

## 实际验证

| 验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| AKShare/BaoStock 专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_akshare_provider.py desktop\tests\test_baostock_provider.py -q` | PASS，13 项；覆盖字段/周期/复权、网络超时、空结果、部分失败不抹其他。 |
| 桌面全量 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests -o addopts='' -q --tb=no` | PASS，366 项；仅既有 ZIP 同名 `manifest.json` 警告。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 真实探针 | `python -m market_monitor.cli probe --provider baostock --report-dir artifacts\full-113-baostock --timeout-seconds 150` | 退出码 2；`provider-run-error` FAILED/NETWORK“网络接收错误”，证据见 `artifacts/full-113-baostock/provider-capabilities.json`。 |
| 网络可达性 | 内联 Python：DNS `www.baostock.com` → `114.94.20.92`；TCP `:10030` 5s/10s 超时 | 证据见 `artifacts/full-113-baostock/tcp-check.json`。 |
| 重叠样本对比 | `compare_daily_bars(AkShareProvider(), BaostockProvider())` → `artifacts/full-113-baostock/provider-comparison.{json,md}` | `BLOCKED`，4 条 NETWORK 错误；`row_blending: DISABLED`；未产出任何混合行。 |
| 统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0、JDK 21、锁定依赖、Ruff、共享 Schema 夹具、366 项桌面测试与 Android `lintDebug`/`testDebugUnitTest`/`assembleDebug` 全部通过；仅有既有 ZIP 同名 `manifest.json` 警告。中间两次失败均为其他并行 Agent 未完成的未提交改动（契约夹具并发写入、`DslProgram.kt` 依赖缺失），已通知对应 Agent 修复后复跑通过。 |

## 数据源状态

| 来源 | 真实状态 | 样本与周期 | 失败或缺口 |
|---|---|---|---|
| BaoStock | FAILED/NETWORK（不可达） | 未取到 | `www.baostock.com:10030` TCP 连接超时；SDK 登录“网络接收错误” |
| AKShare（对比侧） | 部分 FAILED/NETWORK（东财断连） | 未取到 | 与 FULL-110 同一外部端点问题 |

## 接口、迁移与安全

- **公开契约**：ProviderRunResult v2 报告结构未变；失败能力现在可序列化结构化 `error` 字段（Schema 本就允许）。
- **兼容性**：字段/周期/复权映射与既有行为一致；无数据库或数据包变化。
- **安全与隐私**：无凭据、私钥、个人数据或大体积真实行情写入仓库。

## 风险与未完成项

- **外部阻塞**：BaoStock 服务器本机不可达（TCP 超时）。解除条件：服务器可达后由验收角色重跑 `probe --provider baostock` 与跨源重叠对比；长期不可达不阻塞主链（Plan_full.md §7）。
- 重叠样本对比逻辑已具备（固定响应测试 + `compare_daily_bars` 的 `row_blending: DISABLED` 报告），但真实重叠对比待可达后执行，本次不声称完成。
