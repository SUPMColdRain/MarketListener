# FULL-701 实现交付：导入现有 HTML、Excel、PDF 和公告

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：impl_graph + root（文档补齐）

## 结果

- `desktop/src/marketmonitor/industry_graph/importers.py`：HTML（BeautifulSoup/lxml，DOM 路径定位）、Excel（openpyxl，单元格定位）、PDF（注入式文本提取器接口，运行时可探测 pdftotext；无提取器如实 UNSUPPORTED）、公告/文本（行号/偏移）导入器；输出候选实体/关系 + 证据（source_id、source_type、location、parsed_version、extracted_at、sha256）；失败/重复导入有固定测试。
- 夹具：`tests/fixtures/graph/{html,excel,pdf,announcement}/`（supply-chain.html、supply-chain.xlsx、supply-chain.pdf、2026-08-01-moutai.txt）。

## 自动化证据

`test_industry_graph_importers.py` PASS（含各格式定位、重复导入、失败路径）。

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| 图谱导入专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_industry_graph_importers.py -q` | PASS：9 项（HTML/Excel/PDF/公告定位、重复导入、失败路径），exit 0 |
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
