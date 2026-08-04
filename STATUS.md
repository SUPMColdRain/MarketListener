# 正式开发实时状态

> 本文件是唯一实时任务状态源。最后更新：2026-08-05（FULL-002 实现交付）。

## 当前入口

- 当前任务：`FULL-002`
- 当前状态：`REVIEW`
- 当前角色：FULL-002 实现已交付，等待全新的独立审查任务
- 当前证据：`docs/deliveries/FULL-002.md`
- 第一项 `READY`：无；FULL-002尚未独立验收。
- FULL-001 验收原子更新已完成：`FULL-001`=`ACCEPTED`，`FULL-002`=`READY`；其余任务保持 `PENDING`。

## 状态表

| 任务 | 状态 | 依赖 | 当前说明/解除条件 |
|---|---|---|---|
| FULL-001 | ACCEPTED | 无 | 独立验收已重跑全部文档专项验证并通过，见交付记录“独立验收”章节 |
| FULL-002 | REVIEW | 001 | 首个回退提交和锁定工具链已验证；等待独立审查 |
| FULL-003 | PENDING | 002 | 等待依赖 |
| FULL-100 | PENDING | 003 | 等待依赖 |
| FULL-101 | PENDING | 100 | 等待依赖 |
| FULL-110 | PENDING | 101 | 等待依赖 |
| FULL-111 | PENDING | 101 | 等待依赖；真实凭据仅在本机配置 |
| FULL-112 | PENDING | 101 | 等待依赖；真实凭据仅在本机配置 |
| FULL-113 | PENDING | 101 | 等待依赖 |
| FULL-120 | PENDING | 110–113 至少三个接受 | 等待依赖和真实能力证据 |
| FULL-121 | PENDING | 120 | 等待依赖 |
| FULL-122 | PENDING | 121 | 等待依赖和真实数据 |
| FULL-123 | PENDING | 122 | 等待依赖和 Android 13+ 16 KB 设备验收 |
| FULL-200 | PENDING | 121 | 等待依赖 |
| FULL-201 | PENDING | 121 | 等待依赖 |
| FULL-202 | PENDING | 200、201 | 等待依赖 |
| FULL-203 | PENDING | 202 | 等待依赖 |
| FULL-204 | PENDING | 203 | 等待依赖 |
| FULL-300 | PENDING | 123 | 等待依赖 |
| FULL-301 | PENDING | 204、300 | 等待依赖 |
| FULL-302 | PENDING | 301 | 等待依赖 |
| FULL-303 | PENDING | 302 | 等待依赖 |
| FULL-400 | PENDING | 121 | 等待依赖 |
| FULL-401 | PENDING | 203、400 | 等待依赖 |
| FULL-402 | PENDING | 300、400 | 等待依赖 |
| FULL-403 | PENDING | 401、402 | 等待依赖 |
| FULL-404 | PENDING | 301、403 | 等待依赖 |
| FULL-500 | PENDING | 300 | 等待依赖 |
| FULL-501 | PENDING | 500 | 等待依赖 |
| FULL-502 | PENDING | 501、203 | 等待依赖 |
| FULL-503 | PENDING | 500 | 等待依赖 |
| FULL-504 | PENDING | 502、503 | 等待依赖 |
| FULL-600 | PENDING | 204 | 等待依赖 |
| FULL-601 | PENDING | 204 | 等待依赖 |
| FULL-602 | PENDING | 204 | 等待依赖 |
| FULL-610 | PENDING | 101、用户开通QMT | 外部门控，不阻塞离线正式版 |
| FULL-700 | PENDING | 003 | 等待依赖 |
| FULL-701 | PENDING | 700 | 等待依赖 |
| FULL-702 | PENDING | 701 | 等待依赖 |
| FULL-703 | PENDING | 702、500 | 等待依赖 |
| FULL-704 | PENDING | 703、300 | 等待依赖 |
| FULL-800 | PENDING | 202、204 | 等待依赖 |
| FULL-801 | PENDING | 800 | 等待依赖 |
| FULL-802 | PENDING | 801 | 等待依赖 |
| FULL-803 | PENDING | 所有非门控必选任务 | 等待依赖 |
| FULL-804 | PENDING | 本机连续20次成功 | 外部门控，需用户单独批准成本 |
| FULL-900 | PENDING | 803 | 等待依赖 |

## 已知外部条件

- JQData、Tushare 凭据由用户在本机配置，不写入仓库。
- QMT 尚未作为已开通条件，`FULL-610` 不得进入主链。
- Android 发布验收需要 Android 13+、16 KB 页面设备或等价模拟环境。
- Day 0 的 Provider 失败、Chaquopy 失败和真机缺口仍是历史事实；本计划没有把它们改写为成功。

## 状态维护规则

状态只能按 `Plan_full.md` 的状态机更新。任何 Agent 开始前先重读本文件：实现角色不得从无 `READY`/`CHANGES_REQUIRED` 状态自动选择 `PENDING`，审查角色只领取 `REVIEW`，验收角色只领取 `ACCEPTANCE`。审查/验收完成后必须写证据链接，再更新状态和下一项入口。
