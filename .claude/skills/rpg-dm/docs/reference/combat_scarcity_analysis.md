# Combat Scarcity Analysis — 战斗稀少根因分析

## 三假设验证结果

### 假设 1: _filter_pool 过滤太激进 → ❌ 不是代码 bug

_filter_pool 无匹配时回退到全池，不会丢失战斗条目。但 **altar_district 遭遇池本身就没有战斗条目**（0/3）。这是数据设计而非代码缺陷。

- dry_bank_edge / lowland_boundary / ethanol_grove / forbidden_zone 都有战斗条目
- 在这些区域 action_tags 不影响战斗触发（fallback 返回全池）

### 假设 2: danger_tick 推进慢 → ⚠️ 部分正确

| 地点 | max | tick | 平均轮次到遭遇 |
|------|-----|------|-------------|
| altar_district | 12 | 1d3 | ~6 |
| dry_bank_edge | 10 | 1d2 | ~7 |
| ethanol_grove | 8 | 1d2 | ~5 |
| deep_lowland | 8 | 1 | ~8 (最慢) |

altar_district 是最高的（12），deep_lowland tick 固定为 1。但没有哪个区域的钟是"卡住"的——每个 action 都在推进。

### 假设 3: pending_encounter 挂起不释放 → ✅ 有部分 bug

当 `_filter_pool` 返回空池（total_weight=0）时，`rng.randint(1, 0)` 会崩溃。已添加防护。

老 `pending_encounter`（Phase 2 残留）在 danger 未满时不会被清除。已在 `_apply_danger_tick` 开头添加了 stale pending 检测并 force-release。

## 真正原因

**根本原因是 DM 层面：遇到 `combat_state` 或 `encounter` 时没有调 `combat.py --init`。**

即使遭遇正确触发了，DM 如果没有执行战斗流程，玩家就永远看不到战斗选项。这不是引擎问题，是 DM 路由缺失。

## 已修复

- `trigger.py`: empty pool guard + stale pending_encounter auto-release
- `SKILL.md`: 每轮检查 combat_state.enemies
- `main_loop.md`: --view 输出 combat_state 必须走 combat 流程
- `options.md`: 强制对战选项硬约束

## 建议后续

如需祭坛区出现战斗遭遇，需在 `encounter_tables.json` 的 altar_district pool 中添加含 `"combat"` tag 的条目。
