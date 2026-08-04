# desktop（数据生产端）

数据生产端包含 Provider 探针、标准化、质量检查、行情包与签名的当前代码基线。Day 0 已停止且没有真实 Provider `PASS`；正式任务从 `../START_HERE.md` 和 `../STATUS.md` 启动，完整任务边界见 `../Plan_full.md`。

## 环境

- Python 3.11.0（`.python-version`；虚拟环境位于 `desktop/.venv`，不入库）
- `requirements.lock` 固定运行时与测试传递依赖；`pyproject.toml` 的直接依赖与锁文件一致

## 命令

```powershell
py -3.11 -m venv desktop\.venv
desktop\.venv\Scripts\python -m pip install -c desktop\requirements.lock -e "desktop[dev]"
desktop\.venv\Scripts\python -m market_monitor --version
desktop\.venv\Scripts\python -m pytest desktop\tests
```

统一基线验证使用仓库根目录的 `powershell -ExecutionPolicy Bypass -File scripts\verify.ps1`；它也会执行固定为 `ruff==0.12.11` 的静态检查。

`Plan.md` 的 D0 编号仅保留为历史记录，不是后续会话的自动执行队列。
