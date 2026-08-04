# FULL-002 交付记录

## 实现交付

**任务**：FULL-002 建立首个 Git 与锁定工具链基线

**角色**：实现

**状态建议**：`REVIEW`

## 结果

- 创建首个 Git 根提交 `b270463bc9fe63932faf4e01858d8d5d870697d9`（`chore: establish accepted project baseline`），包含已独立验收的 FULL-001、既有代码和 Day 0 历史证据。
- 以 `.python-version` 固定 Python 3.11.0；`pyproject.toml` 固定直接依赖与 setuptools 构建后端，`desktop/requirements.lock` 固定49个运行/测试依赖。
- 以 `.java-version` 和 Gradle配置强制 JDK 21；JDK 20会在配置阶段被明确拒绝。
- 固定 Gradle 8.5及分发 SHA-256、AGP 8.3.2、Kotlin 2.0.0、Android SDK 34 revision 3、Build Tools 34.0.0、`minSdk=33`、`targetSdk=34`。
- 开启 Gradle全配置依赖锁并生成 `android/app/gradle.lockfile`，固定151个 Android传递模块。
- 新增 `.gitattributes` 与密钥/Keystore忽略规则；仓库本地设置 `core.autocrlf=false`、`core.safecrlf=true`。

## 修改文件

- `.gitattributes`
- `.gitignore`
- `.java-version`
- `.python-version`
- `toolchain.versions.toml`
- `desktop/pyproject.toml`
- `desktop/requirements.lock`
- `android/build.gradle.kts`
- `android/app/build.gradle.kts`
- `android/app/gradle.lockfile`
- `android/gradle/wrapper/gradle-wrapper.properties`
- `README.md`
- `desktop/README.md`
- `android/README.md`
- `Experience.md`
- `Log.md`
- `STATUS.md`
- `docs/deliveries/README.md`
- `docs/deliveries/FULL-002.md`

## 实际验证

| 验证 | 命令/方式 | 结果 |
|---|---|---|
| 预提交范围 | `git add -n .`、大文件与敏感赋值只读扫描 | PASS；128个基线文件，无≥5 MB待提交文件；5个候选均为代码变量或固定脱敏测试值 |
| 索引安全 | `git diff --cached --check`、暂存对象大小、私钥/Token形式扫描 | 无大对象或秘密；历史 Markdown 存在换行空白提示但不影响内容 |
| 首个回退点 | `git commit`、`git rev-list --max-parents=0 HEAD`、`git fsck --no-dangling` | PASS；唯一根提交为 `b270463bc9fe63932faf4e01858d8d5d870697d9` |
| Python版本 | `desktop\.venv\Scripts\python.exe --version` | PASS；Python 3.11.0 |
| Python锁解析 | `pip install --dry-run --ignore-installed --index-url https://pypi.org/simple -c desktop\requirements.lock -e ".\desktop[dev]"` | PASS；所有直接和传递依赖解析为锁定版本 |
| Python一致性 | Python `tomllib` + `importlib.metadata` 比较清单、直接依赖、锁文件与已安装环境 | PASS；49/49一致，无动态或缺失版本 |
| Python健康/测试 | `pip check`；`pytest desktop\tests -q` | PASS；无破损依赖，49 passed（1个预期zip重复名警告） |
| JDK门禁 | JDK 20运行 `gradlew help` | EXPECTED FAIL；明确提示项目要求 JDK 21 |
| Gradle/JDK版本 | JBR 21设置 `JAVA_HOME` 后运行 `gradlew --version` | PASS；Gradle 8.5，JVM 21.0.11 |
| Android SDK | 读取 Platform 34和 Build Tools 34.0.0的 `source.properties` | PASS；Platform revision 3、API 34、Build Tools 34.0.0 |
| Gradle依赖锁 | `:app:dependencies --write-locks` 与锁文件解析 | PASS；生成151个精确模块，无动态版本 |
| Android构建 | 英文临时盘符下，JDK 21运行 `testDebugUnitTest assembleDebug --no-daemon` | PASS；6 tests、0 failures，`BUILD SUCCESSFUL`，Debug APK 45,041,639 bytes |
| 配置总检 | Python检查版本清单、两种锁文件、Gradle/SDK配置和Git根提交 | PASS；`TOOLCHAIN LOCK CONSISTENCY PASS` |

Android首次从中文物理路径执行时，APK组装成功但测试worker的5个测试类全部 `ClassNotFoundException`。仅使用英文 junction仍会被 JDK 21规范化回中文路径；临时 `subst` 到纯英文盘符后，6项测试全部通过。该事实已同步至环境说明，不能把首次失败隐藏为成功。

## 接口、迁移与安全

- **业务行为**：无变化；未修改数据源、契约、数据库、行情包或 Android界面逻辑。
- **构建接口**：Gradle现在必须由 JDK 21运行；Python安装必须使用锁文件；Android依赖更新必须显式重写并审查 lockfile。
- **数据库/数据包迁移**：无。
- **安全**：`.env`、私钥、证书、Keystore、`local.properties`、虚拟环境、构建产物和大行情目录均被忽略；未提交真实凭据或私钥。

## 已知限制

- 本机全局 `java` 当前为 Java 26，且本机pip默认配置指向不受信任的HTTP镜像；项目命令必须显式设置 JDK 21，Python锁解析验证使用了 PyPI HTTPS。
- Android JVM测试在中文物理路径下仍需临时英文盘符；FULL-003统一验证脚本应自动处理空闲盘符和清理。
- `FULL-002` 本身作为根提交之上的独立实现提交供审查，可直接与 `b270463` 比较；不得在本实现任务中自行接受或启动 FULL-003。
