# FULL-111 交付记录

**任务**：FULL-111 JQData 真实登录、额度、日线、分钟线、ETF、指数和期货探针

**角色**：独立实现
**状态建议**：`REVIEW`（按用户指示，统一审查延后到 5.1–5.9 全部实现完成后执行）

## 结果

`JoinQuantProvider` 已具备覆盖登录、额度、日线、30 分钟线、1 分钟线、ETF、指数和期货的独立能力探针：健康检查（`health_check`）、额度（新增 `jqdata-query-quota`）、沪深股票/ETF 的 `1d/30m/1m`、沪深300 指数的 `1d/30m/1m`、当前期货合约发现及该合约 `1d/30m/1m`。额度探针使用 JQData SDK 的 `get_query_count()` 读取当日总/剩余请求条数，任何一项失败只标记该项 `FAILED`，不掩盖其他能力。

本机当前没有配置 `JQDATA_USERNAME`/`JQDATA_PASSWORD`（环境变量与仓库外配置 `%USERPROFILE%\market-monitor.env` 均缺失），因此真实登录、额度与数据探针如实输出 `BLOCKED/CONFIGURATION`，未用固定响应伪造真实数据验收。

## 修改文件

- `desktop/src/market_monitor/providers/joinquant.py`：新增额度能力 `jqdata-query-quota`（显式 v2 `CapabilityRegistration`，`ProviderRequest(OTHER)`），其余 20 项沿用既有独立探针。
- `desktop/tests/test_joinquant_provider.py`：固定 SDK 响应增加 `get_query_count`，新增额度缺失字段失败独立上报用例；能力数断言从 20 更新为 21。
- `docs/deliveries/README.md` 与 `STATUS.md`：交付索引与状态更新。

## 公开接口或数据变化

- ProviderRunResult v2 报告新增一条能力记录 `jqdata-query-quota`（`OTHER/GLOBAL/GENERAL`），证据含 `total`/`spare` 额度数值；JSON Schema、`ProviderRequest`、报告结构无其他变化，旧报告兼容。
- `.env.example` 本次与 FULL-112 一并补充 `TUSHARE_TOKEN=`；JQData 配置变量名不变。

## 测试记录

| 测试 | 实际命令或操作 | 结果 |
|---|---|---|
| 单元/固定响应专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_joinquant_provider.py desktop\tests\test_tushare_provider.py -q --tb=short` | PASS，10 项；覆盖 JQData 登录调用、21 项能力、额度数值、额度缺字段失败、限流分类、缺凭据 CONFIGURATION。 |
| 桌面全量 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests -o addopts='' -q --tb=no` | PASS，352 项；仅有既有 ZIP 同名 `manifest.json` 警告。 |
| v2 契约往返 | 内联 `ProbeRunner` 报告 → `validate_contract("provider-run-result.schema.json")` | PASS，21 项能力（含 `jqdata-query-quota`）通过 Schema 校验。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0、JDK 21、54 个精确锁定依赖、Ruff、31 个共享 Schema 夹具、桌面全量 352 项与 Android `lintDebug`/`testDebugUnitTest`/`assembleDebug` 全部通过；仅有既有 ZIP 同名 `manifest.json` 警告。 |
| CLI 缺配置 | `python -m market_monitor.cli probe --provider joinquant --report-dir reports\full111-cli-check`（清空本机 JQDATA 变量） | 退出码 3，`CONFIGURATION_BLOCKED`；报告为 `BLOCKED/CONFIGURATION`。 |
| 真实登录/数据探针 | 本机无本地凭据，未执行 | 未执行（如实阻塞）；待用户在仓库外配置后由验收角色重跑。 |

## 数据源状态

| 来源 | 状态 | 样本与周期 | 行数/时间范围 | 失败或缺口 |
|---|---|---|---|---|
| JQData | BLOCKED/CONFIGURATION（真实探针）；固定响应单测 PASS | 沪深股票/ETF/指数/期货，`1d/30m/1m` | 未探测（缺凭据） | 本机无 `JQDATA_USERNAME`/`JQDATA_PASSWORD` 本地配置 |

## 风险与未完成项

- 真实行数、时间范围、周期、额度和失败原因必须由用户在本机配置凭据后重跑 `probe --provider joinquant` 才能确认；本次未声称真实数据通过。
- 期货合约发现依赖 SDK 当日返回的合约列表；若返回为空则该项为 `UNSUPPORTED`，属预期行为。

## 自检

- [x] 已阅读 `ADR.md`、`CONTEXT.md` 和当前任务验收标准。
- [x] 未提交凭据、私钥、个人数据或大体量行情。
- [x] 未擅自改变架构、扩大范围或静默降级。
- [x] 错误和外部阻塞没有被模拟数据掩盖（缺凭据如实 `BLOCKED`）。
