# FULL-100 交付记录

**任务**：Provider Contract v2

**角色**：独立实现

**状态建议**：`REVIEW`

## 结果

Provider 探测报告已从 v1 升级为 v2。v2 不再序列化任何整源可用状态；每个能力都独立携带来源无关的参数化请求、能力登记元数据、状态、探测时间、证据、限制和可选错误。单一接口的成功或失败不能由序列化模型推导成整源成功或失败。

`ProviderRequest` 明确记录操作、市场、资产类型、周期、日期范围、标的及附加参数；模型和 Schema 都拒绝非法组合，例如没有周期的 bars 请求、`GLOBAL` bars 请求、在 calendar/health 请求中携带周期或标的、日期范围只给一端。`CapabilityRegistry` 对未知能力和与登记请求不一致的调用明确拒绝。

现有四个 Provider 适配器保持原有探测实现与测试语义，但其输出经私有、受限的旧适配器兼容桥写为 v2；未知名称不能经该桥构造。新的 v2 `Capability` 必须提供显式 `CapabilityRegistration`，不能把未知名称静默映射为 `other`；`CapabilityRegistry` 继续拒绝未知能力与不匹配请求。每个适配器现在也提供可读的来源描述。未探测任何真实 Provider，未把历史的失败、无凭据或不支持情况改写为成功。

## v1 迁移

`migrate_v1_provider_run_result()` 只接受完整 v1 文档，并显式产生 v2：

- v1 的来源名称保留为 v2 来源展示名；原整源状态保留在 `migration.legacy_provider_status`，不会被静默丢弃或作为 v2 路由状态使用。
- 每一项旧能力都保留名称、状态、细节、行数和时间范围；无法识别的旧能力名称映射为显式 `other` 请求操作，而不是删除。
- v1 的运行级错误映射为 `provider-run-error` 合成能力，具有独立 `FAILED` 状态和原始错误分类/消息。
- 迁移拒绝缺字段、未知状态、未知错误分类或不能表示的旧字段，避免无声数据损失。

## 修改范围

- `contracts/provider-run-result.schema.json` 与 `contracts/README.md`
- Provider 基类、v2 模型、显式 v1 迁移、能力注册表、报告运行器及现有适配器的来源描述
- 共享 Provider v2 有效/无效 JSON 夹具、跨语言 Schema 夹具索引和对应桌面测试
- `STATUS.md`、根/桌面 README 与本交付索引

未修改数据包、数据库、Android 业务行为、真实来源探测承诺或凭据配置；本任务也没有启动 FULL-101。

## 实际验证

| 验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| 实施前基线 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0、JBR 21.0.11、锁定依赖、Ruff、13 个共享 Schema 夹具、49 个桌面测试与全部 Android 基线子项通过。 |
| Provider v2 专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_contracts.py desktop\tests\test_provider_contract_v2.py desktop\tests\test_provider_runner.py -q` | PASS：34 项通过，覆盖 JSON Schema/Python 往返、v1→v2 迁移、未知能力、请求错配、非法状态和非法请求。 |
| 完整统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：15 个共享 Schema 夹具、60 个桌面测试、Ruff、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug` 全部通过。pytest 仅有既有 ZIP 同名夹具警告。 |
| 变更完整性 | `git diff --check` | PASS：无空白错误。 |

## 接口、迁移与安全

- **公开 Provider 契约**：`provider-run-result.schema.json` 升级为 v2，移除了 v1 顶层 `provider`/`status`/`error` 表达，并引入 `source` 与逐能力记录；迁移函数保留 v1 信息。
- **兼容性**：既有 Provider 适配器保留其原有的无参抓取钩子；新增 `Provider.fetch(request)` 提供校验后的参数化入口，以便后续任务逐步改造适配器而不宣称新的数据能力。
- **安全与隐私**：没有读取、写入或记录凭据、私钥、个人数据或真实行情；运行器继续对异常消息脱敏。
- **已知边界**：本任务只建立契约、迁移与固定夹具。真实凭据加载、缺配置映射为 `BLOCKED/CONFIGURATION`、超时/重试和 CLI 退出码属于后续 FULL-101。

## 后续

本实现仅进入 `REVIEW`，等待新的独立审查任务。审查和验收应重点复核：v2 Schema 与 Python 交叉约束、v1 迁移是否无声丢失、未知能力/非法请求拒绝、以及报告中不存在整源状态推断。

## 独立审查（2026-08-05，gpt-5.6-terra high）

**结论：CHANGES_REQUIRED。** 审查范围为基线提交 `401b9d9` 至当前工作区的 FULL-100 差异；未实施、未验收、未启动后续任务。

### 发现

1. **P1 — Python 请求模型会接受 Schema 明确拒绝的空值字段，破坏 Schema/Python 严格同构。** `ProviderRequest.__post_init__` 用真值判断而不是“字段已提供”判断，因此 `calendar(period="")`、`health_check(instrument="")` 和 `instruments(start_date="", end_date="")` 都能构造并由 `to_dict()` 序列化；Schema 分别以 `minLength`、日期格式和 calendar/health 的字段禁令拒绝它们（[base.py](../../desktop/src/market_monitor/providers/base.py) 第 94–130 行；[provider-run-result.schema.json](../../contracts/provider-run-result.schema.json) 第 45–76 行）。应在模型层拒绝空字符串及所有不允许的已提供字段，并加入模型→JSON Schema 往返反例测试。
2. **P1 — `legacy_capability()` 是公开的无约束逃逸通道，新的 v2 调用者可绕过显式登记和 Registry。** 函数对任意名称自动生成 `other`/推断请求并返回可通过 v2 Schema 的 `Capability`，随后又从公共 `market_monitor.providers` 导出（[base.py](../../desktop/src/market_monitor/providers/base.py) 第 400–445 行；[__init__.py](../../desktop/src/market_monitor/providers/__init__.py) 第 18、50 行）。独立反例 `legacy_capability("new-undeclared-v2-feature", PASS)` 与反向运行时间仍被 `validate_contract()` 接受，违反“新 v2 能力必须显式登记、兼容桥仅限迁移和旧适配器”的边界。应将桥隔离为不可供新 v2 代码使用的内部兼容路径，或用不可伪造的受限上下文/明确迁移入口强制来源，并增加绕过回归测试。
3. **P1 — 报告和证据的时间范围不变量未校验。** `ProviderRunResult` 仅分别解析 `started_at` 和 `completed_at`，`CapabilityEvidence` 仅分别解析 `earliest`/`latest`，没有比较先后（[base.py](../../desktop/src/market_monitor/providers/base.py) 第 94–106、280–305 行；[contracts.py](../../desktop/src/market_monitor/contracts.py) 第 58–118 行）。反例中 `completed_at < started_at` 被完整 `validate_contract()` 接受；同样可写入 `earliest > latest`。应在模型和通过 JSON 的语义校验中统一拒绝反向区间，并覆盖带不同时区偏移的等价比较。

### 独立复核证据

- `desktop\.venv\Scripts\python.exe -`：三组空字符串 `ProviderRequest` 均被模型接受；公开 legacy 兼容桥生成的未知能力、以及 `completed_at` 早于 `started_at` 的完整 v2 文档被 `validate_contract()` 接受。
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS（Python 3.11.0、依赖锁定、Ruff、15 个共享 Schema 夹具、60 个桌面测试、Android lint/JVM/APK）。该基线通过不能覆盖上述反例。
- `git diff --check`：PASS。

修复后应补充上述反例的模型、Schema 与迁移/隔离测试，重新进入 `REVIEW`；本次不具备进入 `ACCEPTANCE` 的条件。

## P1 修复（2026-08-05）

本次仅修复独立审查列出的三项 P1，未扩展到 FULL-101。

1. **空字符串与请求条件**：`ProviderRequest` 现在以“字段是否提供”（`is not None`）而非真值判断处理 `period`、日期和标的；任一已提供的空/纯空白字符串，以及参数对象中空/纯空白键和值都会被 Python 模型拒绝。Schema 同步使用非空白模式及参数键/值约束；calendar/health 对所有显式提供的 period、标的和日期仍严格拒绝。
2. **兼容桥封闭**：移除了 `market_monitor.providers.legacy_capability` 的公共导出。现存旧适配器只能导入私有 `_legacy_adapter_capability`，它以精确的旧能力名称模式白名单限制调用，任何未识别名称都会失败。v1 迁移使用另一条私有 `_migrated_v1_capability` 路径，可将未知 v1 名称保留为受控的 `other` 语义；这一迁移专用行为不再是新 v2 调用的逃逸通道。
3. **时区与时间范围**：ISO 时间解析现在要求明确时区并统一转换为 UTC；`ProviderRunResult` 拒绝 `started_at > completed_at`，`CapabilityEvidence` 拒绝 `earliest > latest`。JSON Schema 后的 Python 语义校验复用同一模型，因此反向区间和 naive 时间同样被 JSON 契约入口拒绝。

| 修复验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| P1 专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_provider_runner.py desktop\tests\test_akshare_provider.py desktop\tests\test_baostock_provider.py desktop\tests\test_joinquant_provider.py desktop\tests\test_tdx_quant_provider.py -q` | PASS：36 项通过；覆盖空/空白请求字段、公开兼容桥缺席、未知桥调用拒绝、v1 未知项迁移、带时区反向区间及 naive 时间拒绝。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 修复后完整统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：15 个共享 Schema 夹具、68 个桌面测试、Ruff、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug` 全部通过；pytest 仅报告既有 ZIP 同名夹具警告。 |
| 变更完整性 | `git diff --check` | PASS：无空白错误。 |

修复完成后仍只进入 `REVIEW`，必须由新的独立审查者确认 P1 已消除。

## 修复后独立复审（2026-08-05，gpt-5.6-terra high）

**结论：CHANGES_REQUIRED。** 本次只审查基线提交 `401b9d9` 至当前工作区的 FULL-100 差异；未实施、未验收、未启动 FULL-101。此前的三项 P1 已重新复现为拒绝，但发现一项新的迁移数据完整性 P1。

### 已消除的原 P1

- Python 模型与 `validate_contract()` 均拒绝所有已提供的空/纯空白 `period`、`start_date`、`end_date`、`instrument`，以及空/纯空白 `parameters` 键和值；共享 Schema 入口同样拒绝。
- 公共 `market_monitor.providers` 不再导出 `legacy_capability`；私有旧适配器桥可构造白名单内 `health_check`，但拒绝 `undeclared-new-v2-capability`。v1 未知能力仍迁移为显式 `other`，且保留状态、明细、行数、时间范围及 `legacy_provider_status`。
- Python 模型与 JSON 契约入口均拒绝 naive 时间、`completed_at < started_at`，以及跨偏移量比较后 `earliest > latest` 的证据范围。

### 发现

1. **P1 — 公共 v1 迁移函数会接受并无声丢弃无法表示的字段，违背无信息丢失迁移承诺。** `migrate_v1_provider_run_result()` 只读取所需根字段和 `error` 中的分类/消息，未在根对象或 `error` 对象先执行 v1 的 `additionalProperties: false` 约束；相反，能力对象才在 [migration.py](../../desktop/src/market_monitor/providers/migration.py) 第 71–74 行显式拒绝未知字段。因此向公开迁移入口传入完整必填 v1 文档并附加 `future_v1_field` 时，函数成功返回 v2 结果而该字段消失（同理 `error` 的未知字段也会被丢弃）。这与本交付记录“迁移拒绝不能表示的旧字段”的公开承诺冲突，且会令未来 v1 扩展字段静默损失。应在迁移前严格验证 v1 根对象、错误对象和字段类型/约束，或拒绝所有不能逐字段保留的输入，并添加回归测试。

### 独立复核证据

- 内联 `desktop\.venv\Scripts\python.exe -` 专项反例：原三项 P1 的所有空值/空白、桥绕过和时间范围用例均为 `PASS`（即均被模型或契约拒绝）；已知旧适配器与 v1 未知项迁移仍通过。
- 内联迁移反例：含 `future_v1_field: {"must_not": "be_discarded"}` 的 v1 输入输出为 `ACCEPTED AND DROPPED`，生成的 v2 文档不含该字段，确定复现无声数据丢失。
- `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_contracts.py desktop\tests\test_provider_contract_v2.py desktop\tests\test_provider_runner.py desktop\tests\test_akshare_provider.py desktop\tests\test_baostock_provider.py desktop\tests\test_joinquant_provider.py desktop\tests\test_tdx_quant_provider.py -q`：PASS，51 项通过。
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS（Python 3.11.0、50 个锁定依赖、Ruff、15 个共享 Schema 夹具、68 个桌面测试、Android lint/JVM/APK）；pytest 仅有既有 ZIP 同名夹具警告。
- `git diff --check`：PASS。

修复仅限 FULL-100 的 v1 迁移输入严格性与对应回归测试，完成后应重新进入 `REVIEW`。本次不能进入 `ACCEPTANCE`。

## v1 迁移输入严格性 P1 修复（2026-08-05）

本次仅修复复审指出的 v1 无声丢字段问题。新增保留的 `contracts/provider-run-result-v1.schema.json`，它逐字保留历史 v1 的根对象、`error` 和 `capabilities` 结构约束：全部 required 字段、类型、状态枚举、`date-time` 格式、`row_count` 最小值以及各层 `additionalProperties: false`。

公开 `migrate_v1_provider_run_result()` 现在先以 `validate_contract("provider-run-result-v1.schema.json", document)` 验证完整 JSON 对象，之后才读取或迁移字段；Schema 的仓库绝对路径由 `market_monitor.contracts.CONTRACTS_DIR` 推导，不依赖运行时工作目录。历史 v1 的日期时间格式还复用迁移所需的带时区解析器，避免 JSON Schema 格式实现差异放宽迁移输入。任何根级、错误对象或能力对象的未知字段都会在迁移前失败，绝不会被忽略；合法 v1（包括未知旧能力名）仍由专用迁移路径保留为受控 `other` 能力。

| 修复验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| v1 严格迁移专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py -q` | PASS：38 项通过。覆盖根 `future_v1_field`、`error.future_error_field`、能力 `future_capability_field` 的明确拒绝，以及非法状态、负行数、非法日期时间拒绝；合法 v1 与未知旧能力迁移仍通过。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 修复后完整统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：15 个共享 Schema 夹具、74 个桌面测试、Ruff、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug` 全部通过；pytest 仅报告既有 ZIP 同名夹具警告。 |
| 变更完整性 | `git diff --check` | PASS：无空白错误。 |

本修复仍只应进入 `REVIEW`，等待新的独立复审。

## 修复后第二轮独立复审（2026-08-05，gpt-5.6-terra high）

**结论：CHANGES_REQUIRED。** 本次仅审查基线提交 `401b9d9` 至当前工作区的 FULL-100 差异；未实施、未验收、未启动 FULL-101。

### 已复核通过的修复

- 保留的 `provider-run-result-v1.schema.json` 与提交 `e407399` 的历史 v1 Schema 在所有行为约束（根/能力/错误对象、required、类型、枚举、format、minimum、`additionalProperties`）上结构相同；仅 `$id` 与标题为新文件名而更新。
- `migrate_v1_provider_run_result()` 在转换前经绝对 `CONTRACTS_DIR` 路径验证 v1 根、错误和能力对象；根、错误及能力的未知字段均被拒绝，且从无关工作目录调用仍通过正确路由 Schema。
- 上轮三项 P1 已消除：空/空白请求字段被模型与契约入口拒绝；公共 API 不再导出无约束的 legacy bridge；带时区的反向运行/证据时间范围与 naive 时间均被拒绝。普通的未知旧能力仍成功迁移为受控 `other`。

### 发现

1. **P1 — Schema 合法的 v1 名称与归一化冲突不能迁移，违反“合法 v1 / 未知旧能力可迁移”的兼容承诺。** 历史 v1 只要求 `provider` 与能力 `name` 为非空字符串，但迁移在 [migration.py](../../desktop/src/market_monitor/providers/migration.py) 第 39–44 行把它们直接传给受 v2 kebab-case/唯一性约束限制的标识；[base.py](../../desktop/src/market_monitor/providers/base.py) 第 421–447 行的归一化也不为数字开头生成字母前缀。独立反例均首先通过 v1 Schema，随后迁移失败：`provider="123-source"`（v2 source id 非法）、能力 `name="123-unknown"`（capability id 非法）、`"foo bar"` 与 `"foo-bar"`（归一化后 id 重复）；若旧能力名为 `provider-run-error` 且存在合法 v1 根错误，迁移又在 [migration.py](../../desktop/src/market_monitor/providers/migration.py) 第 49–52 行拒绝。应生成稳定、合法且无碰撞的 v2 技术 id（原始名称仍保留于展示/描述/迁移证据），并为合成运行错误选择不与已迁移 id 冲突的 id；添加这些合法旧报告的回归迁移测试。
2. **P2 — 共享夹具索引没有路由 v1 Schema，无法防止 v1 样例被错误地按 v2 判断。** [cases.json](../../tests/fixtures/contracts/cases.json) 第 10–12 行仅登记 v2 Provider 报告；[test_contracts.py](../../desktop/tests/test_contracts.py) 第 18–26 行只遍历该索引。因此新增的 v1 Schema 没有对应的共享合法/非法夹具和明确 `schema: "provider-run-result-v1.schema.json"` 路由。应加入最小 v1 合法夹具及至少一个 v1 非法夹具并登记到共享索引，同时保留 v2 用例，证明两套 Schema 不会互相误判。

### 独立复核证据

- 内联 `desktop\.venv\Scripts\python.exe -`：普通 v1 与未知旧能力成功迁移；根/错误/能力未知字段、非法状态、负行数及非法日期时间被拒绝；无关当前目录时 Schema 仍正确解析。相同脚本证实上述四组 v1 Schema 合法边界输入均迁移失败。
- `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_contracts.py desktop\tests\test_provider_contract_v2.py desktop\tests\test_provider_runner.py -q`：PASS，48 项通过；该通过结果未覆盖 P1 的合法名称边界及 P2 的 v1 共享夹具路由。
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS（Python 3.11.0、50 个锁定依赖、Ruff、15 个共享 Schema 夹具、74 个桌面测试、Android lint/JVM/APK）；pytest 仅报告既有 ZIP 同名夹具警告。
- `git diff --check`：PASS。

修复仅限 FULL-100 的 v1 合法输入标识映射、冲突规避及共享夹具路由；完成后应重新进入 `REVIEW`。本次不能进入 `ACCEPTANCE`。

## v1 标识符迁移与共享夹具 P1/P2 修复（2026-08-05）

本次仅修复第二轮复审的合法 v1 标识迁移和共享夹具路由问题。

- v1 Provider 与能力名称现在通过 SHA-256 的确定性技术 ID 分配器迁移。输入包含稳定域、原始名称、相同原名的出现序号和必要的碰撞序号，不使用 Python 的不稳定 `hash()`。
- 所有生成 ID 都满足 v2 的 lowercase kebab-case、字母首字符和 64 字符限制。数字开头、标点或 Unicode 名称转入 `legacy-<digest>` 形式；不同原名的归一化碰撞及重复同名能力得到不同的稳定后缀。
- 原始 Provider 名称无损保留在 `source.display_name`，原始能力名称无损保留在每项能力的登记说明；已知旧能力仍按既有市场/资产/周期映射，未知旧能力仍只在 v1 迁移专用路径中成为 `other`。
- 有根级 v1 `error` 时，合成能力使用 `migration-root-error-<digest>` 保留命名空间，并在已占用能力 ID 集合中分配，避免与原名 `provider-run-error` 或任何迁移能力冲突。
- 新增 v1 合法共享夹具和根、错误、能力对象各一个未知字段非法夹具，`cases.json` 对它们明确标注 `provider-run-result-v1.schema.json`；v2 夹具保持原有 v2 路由。

| 修复验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| 标识与夹具专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py desktop\tests\test_provider_runner.py -q` | PASS：54 项通过。覆盖数字开头、标点/Unicode、归一化冲突、重复原名、原名 `provider-run-error` 加根错误、确定性重复迁移、v2 roundtrip，以及 v1/v2 共享夹具分别路由和互不误验。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 修复后完整统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：19 个共享 Schema 夹具、80 个桌面测试、Ruff、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug` 全部通过；pytest 仅报告既有 ZIP 同名夹具警告。 |
| 变更完整性 | `git diff --check` | PASS：无空白错误。 |

修复完成后仍只应进入 `REVIEW`，等待新的独立复审。

## 最新独立复审（2026-08-05，gpt-5.6-terra high）

**结论：CHANGES_REQUIRED。** 本次仅审查基线提交 `401b9d9` 至当前工作区的 FULL-100 差异；未实施、未验收、未启动 FULL-101。

### 已复核通过

- 数字开头、标点、Unicode、归一化碰撞、重复名称，以及 `provider-run-error` 同时带根级错误的既有专项输入均能生成满足 v2 pattern 和长度限制的唯一 ID；根错误不会覆盖已迁移能力。
- 保留的 v1 合法/非法共享夹具按显式 `schema` 路由；v1 合法夹具会被 v2 拒绝，v2 合法夹具也会被 v1 拒绝。
- 先前的空字段、公开 legacy bridge、时间范围和未表示字段丢失问题仍被拒绝；迁移元数据与 v2 Schema 一致。

### 发现

1. **P1 — 技术 ID 与原始能力身份仍依赖输入顺序，且原始能力名称没有结构化、无损的 v2 表达。** [migration.py](../../desktop/src/market_monitor/providers/migration.py) 第 39–48 行按照输入数组顺序填充 `used_identifiers`，第 115–130 行只有在当时未占用时才直接采用归一化 ID。因此同一份合法 v1 报告只要交换 `"foo bar"` 与 `"foo-bar"` 的顺序，前者的 ID 会在 `foo-bar` 和 `foo-bar-e42e50ed8395d059` 间变化，后者也会在 `foo-bar` 和 `foo-bar-d28d501a1f5c2ffd` 间变化。所有生成文档均通过 v2 Schema，却不能稳定将某一原始能力绑定到同一技术 ID，违反本轮“不得因顺序或 Python 进程变化不稳定”的要求。并且原始能力名目前仅拼接进 [base.py](../../desktop/src/market_monitor/providers/base.py) 第 421–456 行的自由文本 `registration.description`；v2 Schema 没有可机读的 legacy-name 字段，无法可靠、结构化地恢复原始名称。应以原始名称（以及为重复条目定义的稳定、可审计区分键）派生不依赖数组顺序的 ID，并在 v2 合约/迁移元数据中增加结构化的原始名称保留字段；新增乱序、重复和跨进程确定性回归测试。
2. **P1 — 保留的 v1 Schema 判定为合法的空白 Provider/能力名称仍无法迁移。** [provider-run-result-v1.schema.json](../../contracts/provider-run-result-v1.schema.json) 第 10–11、26–29 行只使用 `minLength: 1`，因此 `provider: " "` 或 capability `name: " "` 均是合法 v1 文档；但 [migration.py](../../desktop/src/market_monitor/providers/migration.py) 第 91–95 行以 `strip()` 拒绝它们。独立复现中两类文档均先通过 v1 Schema、随后迁移抛出 `v1 provider/name must be a non-empty string`。这违反合法 v1 名称（包括空格/标点）必须可迁移的兼容承诺，也说明当前自由文本保留方式不能无损承载这类名称。应为任意 `minLength: 1` 的历史名称分配合法技术 ID，并以结构化字段原样保留其 Unicode/空白内容；如需收紧历史输入语义，则必须先获批变更历史 v1 Schema/兼容性承诺，不能由迁移器单方面拒绝。

### 独立复核证据

- 内联 `desktop\.venv\Scripts\python.exe -`：正反两种能力顺序均迁移且通过 v2 Schema，但 `foo bar`/`foo-bar` 的原始名称到技术 ID 映射如上发生变化；`provider: " "` 与 capability `name: " "` 均通过 v1 Schema，随后被迁移器拒绝。v1/v2 两个合法共享夹具均只被各自 Schema 接受、被另一版本拒绝。
- `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py desktop\tests\test_provider_runner.py -q`：PASS，54 项通过；现有确定性用例只比较同一输入顺序的重复调用，未覆盖乱序身份稳定性或空白合法名称。
- `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` 与 `git diff --check`：PASS。
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS（Python 3.11.0、50 个锁定依赖、Ruff、19 个共享 Schema 夹具、80 个桌面测试、Android lint/JVM/APK）；pytest 仅有既有 ZIP 同名夹具警告。该基线通过不覆盖上述迁移反例。

修复仅限 FULL-100 的 v1 原始名称结构化保留、顺序无关的技术 ID 分配及合法空白名称迁移，并补充针对性回归测试；完成后重新进入 `REVIEW`，本次不得进入 `ACCEPTANCE`。

## v1 原名结构化保留与顺序独立技术 ID P1 修复（2026-08-05）

本次只修复最新复审列出的两项 P1，未启动 FULL-101。

- v2 `SourceDescription` 新增 `legacy_name`，逐字符保留迁移前的 Provider 名称；`CapabilityRegistration` 成对新增 `legacy_name` 与 `legacy_occurrence`，逐字符保留每项旧能力名称并区分同名重复项。Schema、Python 模型、契约解析与 JSON 往返均保留这些迁移专用字段。
- 迁移 ID 统一由稳定的 SHA-256 输入 `domain + NUL + 原始 UTF-8 名称 + NUL + occurrence` 派生，使用 `legacy-<digest>` 格式；不做 `strip()` 或归一化，也不依赖 Python `hash()` 或数组中其他名称的位置。根级 v1 error 继续使用隔离的 `migration-root-error-<digest>` 命名空间。
- v1 Schema 允许的纯空白 Provider/能力名称现在可以迁移：安全的 v2 技术 ID 与展示名由迁移器生成，原始空白值仍精确保存在上述结构化字段。已知能力的请求语义映射保持不变，未知旧名称仍限于迁移专用 `other` 路径。

| 修复验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| 原名与 ID 专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py -q` | PASS；覆盖顺序置换、归一化冲突、重复同名、跨进程确定性、纯空白名称、根错误组合、Schema 与 Python roundtrip。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 完整统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS；50 个锁定依赖、Ruff、19 个共享 Schema 夹具、81 个桌面测试、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug` 均通过。pytest 仅报告既有 ZIP 同名 `manifest.json` 警告。 |

实现完成后仅重新进入 `REVIEW`，等待全新的独立复审；不得自行进入 `ACCEPTANCE` 或启动 FULL-101。

## 最新独立复审（2026-08-05，gpt-5.6-terra high）

**结论：CHANGES_REQUIRED。** 本次仅审查基线提交 `401b9d9` 至当前工作区的 FULL-100 差异；未实施、未验收、未启动 FULL-101。

### 已复核通过

- `SourceDescription.legacy_name` 与 `CapabilityRegistration.legacy_name` / `legacy_occurrence` 在当前 Schema 与 Python 模型中均能逐字符保留 v1 原名；能力两字段的成对存在、非空名称和非负整数 occurrence 均被拒绝反例覆盖。
- v1 迁移技术 ID 由域、原始 UTF-8 字节和 occurrence 的 SHA-256 派生，满足 v2 的字母首字符、kebab-case 与不超过 64 字符约束。不同原名的列表置换映射不变；同名重复保持唯一，根级 error 使用隔离命名空间，不会覆盖迁移能力。
- 独立输入包含 Unicode、空白、NUL 字节、归一化冲突、重复名称和根错误；均可按 v1 Schema 验证、迁移、JSON 往返并通过 v2 Schema。跨进程重复迁移的技术 ID 输出相同。
- 先前 P1/P2（v1 未表示字段拒绝、请求字段/时间范围严格性、未知普通 v2 能力拒绝、共享 v1/v2 夹具显式路由）仍通过回归验证。

### 发现

1. **P1 — 迁移专用的 `legacy_*` 与 `migration` 字段没有与迁移语义绑定，普通 v2 可以伪造或构造矛盾的迁移身份。** [provider-run-result.schema.json](../../contracts/provider-run-result.schema.json) 第 15–23 行和第 26–99 行允许 `migration`、`source.legacy_name`、`registration.legacy_name`/`legacy_occurrence` 任意独立出现；[base.py](../../desktop/src/market_monitor/providers/base.py) 第 154–225、334–353 行与 [contracts.py](../../desktop/src/market_monitor/contracts.py) 第 79–123 行也只分别验证格式，未强制跨字段关系。独立反例均被 v2 `validate_contract()` 接受：(a) 删除合法迁移报告的 `migration`，却保留来源和能力的 `legacy_*`；(b) 删除 `migration` 和 `source.legacy_name`，却保留能力的成对 `legacy_*`；(c) 保留 `migration`，却删除所有 `legacy_*`。这使普通 v2 报告可以声称不存在的 v1 身份，也使所谓的迁移报告失去可审计的原名，违反本轮“仅迁移语义、不导致普通 v2 可伪造/矛盾”的要求。应在 Schema 与 Python 语义层同时规定：非迁移 v2 不得携带任何 `legacy_*`；迁移 v2 必须有 `source.legacy_name`，并对迁移能力/合成根错误建立明确且可验证的字段规则；添加三类反例和模型直构造回归测试。

### 独立复核证据

- 内联 `desktop\.venv\Scripts\python.exe -`：构造含 `"源 \\u0000 \\u2003"`、`" \\u2003 "`、`"\\u0000"` 与 `"中文😀"` 原名的合法 v1 报告；不同原名置换的 `(legacy_name, legacy_occurrence) -> id` 映射相同，JSON 往返通过 v2 Schema。随后上述三种普通/伪造 v2 反例全部被当前 v2 验证器接受。
- `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py desktop\tests\test_provider_runner.py -q`：PASS，55 项通过；`desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests`：PASS；`git diff --check` 与 `git diff --check 401b9d9`：PASS。
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS（Python 3.11.0、JBR 21.0.11、50 个锁定依赖、Ruff、19 个共享 Schema 夹具、81 个桌面测试、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug`）。pytest 仅报告既有 ZIP 同名 `manifest.json` 警告。

修复仅限 FULL-100 的 v2 迁移字段跨字段不变量与对应 Schema/Python 回归测试。修复完成后重新进入 `REVIEW`；本次不得进入 `ACCEPTANCE` 或启动 FULL-101。

## v2 迁移字段跨字段 P1 修复（2026-08-05）

本次只修复最新独立复审发现的普通 v2 可伪造迁移专用字段问题，未启动 FULL-101。

- Schema 使用 Draft 2020-12 的顶层 `if`/`then`/`else` 将普通 v2 与 v1 迁移报告分开：普通 v2 禁止所有 `legacy_*` 字段与保留的 `legacy-` / `migration-root-error-` ID；迁移报告必须提供 `source.legacy_name` 和 `legacy-` 来源 ID。
- 迁移 capabilities 仅可为带成对 `legacy_name` / `legacy_occurrence` 的 `legacy-*` 条目，或至多一个 `migration-root-error-*` 合成条目。后者禁止 legacy 身份字段，固定为 `FAILED`、具有 error、固定 root 描述以及 `other/GLOBAL/GENERAL` 请求语义；允许 v1 的空 capabilities 且无根错误。
- `ProviderRunResult` 对普通报告、迁移报告与合成根错误实施同构语义检查；`validate_contract()` 在 Schema 通过后重新构建这些模型，确保 JSON 解析入口复用相同约束。

| 修复验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| 跨字段专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py -q` | PASS，56 项通过；覆盖复审的三种伪造/缺失身份反例、直接模型构造反例、有/无根错误及空 capabilities 迁移 roundtrip。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 完整统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS；50 个锁定依赖、Ruff、23 个共享 Schema 夹具、92 个桌面测试、Android `lintDebug`、`testDebugUnitTest` 与 `assembleDebug` 均通过。pytest 仅报告既有 ZIP 同名 `manifest.json` 警告。 |

共享 fixtures 新增一个有效的 v1 迁移结果及三种无效跨字段形状。实现完成后仅重新进入 `REVIEW`，等待新的独立复审；不得自审、验收或启动 FULL-101。

## 独立复审（2026-08-05，gpt-5.6-terra high）

**结论：通过，进入 `ACCEPTANCE`。** 本次仅复审基线提交 `401b9d9` 至当前工作区的 FULL-100 差异；未实施、未验收、未启动 FULL-101。

### 复审结果

- 普通 v2 在 Schema 和直接 `ProviderRunResult` 构造入口均拒绝任一 `legacy_*` 字段，以及 `legacy-` / `migration-root-error-` 保留 ID。
- 有 `migration` 的报告必须携带带 `legacy-` ID 的来源及 `source.legacy_name`；迁移能力必须同时带 `legacy_name` / `legacy_occurrence` 和 `legacy-` ID，普通能力及缺失或矛盾身份均被拒绝。
- 合成根错误要求 `FAILED`、`error`、固定描述和严格的 `other/GLOBAL/GENERAL` 无参数请求，禁止 legacy 身份和第二个根错误；合法的无根错误、仅根错误、仅迁移能力和空能力迁移报告均可通过。
- 回归确认 v1/v2 显式 Schema 路由、历史 P1/P2、迁移 SHA-256 确定性与无损原名保留均未回退。Schema 的 `if`/`then`/`else`、`contains`/`maxContains`、`$defs` 引用及 `additionalProperties` 组合均已用正反例复核。

### 独立复审证据

- 内联 `desktop\.venv\Scripts\python.exe -`：分别对普通 v2 伪造 legacy 身份、迁移来源/能力身份缺失或错误、根错误的 error/status/request/description/legacy 字段错误和双根错误进行验证，全部拒绝；对空能力、仅迁移能力、仅根错误迁移报告，模型与 `validate_contract()` 均接受。
- `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_provider_contract_v2.py desktop\tests\test_contracts.py desktop\tests\test_provider_runner.py -q`：PASS，66 项通过。
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS；Python 3.11.0、50 个精确锁定依赖、Ruff、23 个共享 Schema 夹具、92 个桌面测试、Android `lintDebug`、`testDebugUnitTest`、`assembleDebug` 全部通过；pytest 仅报告既有 ZIP 同名 `manifest.json` 警告。
- `git diff --check 401b9d9`：PASS；变更范围与 FULL-100 一致，扫描未发现提交的凭据或私钥。

未发现 P0–P3；交由全新的独立验收角色重跑 FULL-100 规定的验证后决定是否 `ACCEPTED`。

## 独立验收（2026-08-05，gpt-5.6-terra high）

**结论：ACCEPTED。** 本次验收者独立于实现与复审角色；仅验收 `FULL-100`，未实施改动、未启动 `FULL-101`。

### 验收证据

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1`：PASS。验证 Python 3.11.0、50 个精确锁定依赖、Ruff、23 个共享 Schema 夹具、92 个桌面测试以及 Android `lintDebug`、`testDebugUnitTest`、`assembleDebug`；pytest 只报告既有 ZIP 同名 `manifest.json` 警告。
- 独立内联 `desktop\.venv\Scripts\python.exe -` 专项：PASS。覆盖 v2 Schema/Python roundtrip、参数请求的合法/空白/错误组合、能力显式登记/未知拒绝/相互独立状态、普通 v2 迁移身份拒绝、严格 v1 Schema 及 v1/v2 显式路由、v1 未知名/数字/Unicode/空白/归一化冲突/重复名与根错误迁移、技术 ID 跨顺序稳定、原名结构化无损、时间范围和未知字段拒绝、迁移字段矛盾与根错误约束。
- `git diff --check 401b9d9`：PASS。验收范围限定为 FULL-100 契约、Provider 模型/迁移、适配器兼容、夹具、测试和入口文档；没有启动后续任务。对源代码与文档扫描未发现私钥或 AWS 访问键特征；新增/变更源码和文档中没有应提交的大型行情文件。Android 构建中间产物虽大，但未被纳入变更范围。

### 验收决定

未发现 P0–P3。`FULL-100` 标记为 `ACCEPTED`，依赖满足后仅解锁 `FULL-101` 为 `READY`。
