# FULL-112 交付记录

**任务**：FULL-112 Tushare 日线、基础资料、财务、日历和分钟线权限探针

**角色**：独立实现
**状态建议**：`REVIEW`（按用户指示，统一审查延后到 5.1–5.9 全部实现完成后执行）

## 结果

新增 `TushareProvider` 适配器与 6 项显式 v2 能力：`tushare-calendar`（SSE 交易日历）、`tushare-daily`（600519.SH 日线）、`tushare-stock-basic`（上市基础资料）、`tushare-financial`（利润表财务数据）、`tushare-minute`（1 分钟线权限/覆盖）、`tushare-account`（账户积分与接口权限）。每项独立调用 Tushare 接口并独立上报 `PASS/FAILED`，权限不足（`没有访问权限`）、积分不足（`积分不足`）、频率限制、网络与 token 错误分别归类为 `NO_COVERAGE`、`RATE_LIMIT`、`NETWORK`、`AUTHENTICATION`，单接口失败不掩盖其他接口。

本机当前没有配置 `TUSHARE_TOKEN`（环境变量与仓库外配置均缺失），因此真实探针如实输出 `BLOCKED/CONFIGURATION`，未用固定响应伪造真实权限/积分/频率/覆盖验收。

## 修改文件

- `desktop/src/market_monitor/providers/tushare.py`：新增适配器（能力登记、固定响应转换、错误分类、token 本地配置）。
- `desktop/tests/test_tushare_provider.py`：固定 SDK 响应专项测试。
- `desktop/src/market_monitor/providers/registry.py`、`desktop/src/market_monitor/providers/__init__.py`：注册 `TushareProvider`。
- `desktop/pyproject.toml`、`desktop/requirements.lock`：新增并锁定 `tushare==1.4.29`（含 `bs4`、`simplejson`、`websocket-client` 精确版本）。
- `.env.example`：新增 `TUSHARE_TOKEN=`。
- `docs/deliveries/README.md` 与 `STATUS.md`：交付索引与状态更新。

## 公开接口或数据变化

- CLI 注册 provider 新增 `tushare`（`probe --provider tushare`）；ProviderRunResult v2 报告新增 6 项能力记录，均为显式 `CapabilityRegistration`，未使用 legacy 兼容桥。
- 新增本地配置要求 `TUSHARE_TOKEN`，缺配置时由 runner 输出 `BLOCKED/CONFIGURATION`（`configuration-tushare-token`）。
- Python 依赖锁定新增 `tushare==1.4.29`；JSON Schema 与既有报告结构无变化。

## 测试记录

| 测试 | 实际命令或操作 | 结果 |
|---|---|---|
| 单元/固定响应专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_joinquant_provider.py desktop\tests\test_tushare_provider.py -q --tb=short` | PASS，10 项；覆盖 Tushare 6 项能力、token 传递、日期/时间范围、缺 token 不触网、权限/积分错误独立上报与错误分类。 |
| 桌面全量 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests -o addopts='' -q --tb=no` | PASS，352 项；仅有既有 ZIP 同名 `manifest.json` 警告。 |
| v2 契约往返 | 内联 `ProbeRunner` 报告 → `validate_contract("provider-run-result.schema.json")` | PASS，6 项能力全部通过 Schema 校验。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0、JDK 21、54 个精确锁定依赖、Ruff、31 个共享 Schema 夹具、桌面全量 352 项与 Android `lintDebug`/`testDebugUnitTest`/`assembleDebug` 全部通过；仅有既有 ZIP 同名 `manifest.json` 警告。 |
| CLI 缺配置 | `python -m market_monitor.cli probe --provider tushare --report-dir reports\full112-cli-check`（清空本机 TUSHARE 变量） | 退出码 3，`CONFIGURATION_BLOCKED`；报告为 `BLOCKED/CONFIGURATION`。 |
| 真实探针 | 本机无本地 token，未执行 | 未执行（如实阻塞）；待用户在仓库外配置后由验收角色重跑。 |

## 数据源状态

| 来源 | 状态 | 样本与周期 | 行数/时间范围 | 失败或缺口 |
|---|---|---|---|---|
| Tushare | BLOCKED/CONFIGURATION（真实探针）；固定响应单测 PASS | 600519.SH 日线/1 分钟、日历、基础资料、财务、账户积分 | 未探测（缺 token） | 本机无 `TUSHARE_TOKEN` 本地配置 |

## 风险与未完成项

- 真实权限、积分、频率和覆盖必须由用户在本机配置 token 后重跑 `probe --provider tushare` 才能确认；本次未声称真实数据通过。
- 不同积分档位下 `income`/`stk_mins` 可能返回权限错误，适配器按接口独立上报，不把整源标记为失败。

## 自检

- [x] 已阅读 `ADR.md`、`CONTEXT.md` 和当前任务验收标准。
- [x] 未提交凭据、私钥、个人数据或大体量行情。
- [x] 未擅自改变架构、扩大范围或静默降级。
- [x] 错误和外部阻塞没有被模拟数据掩盖（缺 token 如实 `BLOCKED`）。
