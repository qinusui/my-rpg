# 动态时间与遭遇系统

玩家每次做出实质性行动后，必须执行 `python tools/state_mgr.py --tick`。

---
## 地点危机钟

每个地点有隐藏的危机钟（`danger_max`/`danger_tick`），取代原来的二元 D20 遭遇掷骰。每次 tick 推进危机钟，满格才触发遭遇。

**推进流程**：

1. 掷 `danger_tick`（骰子记法，如 "1d3"），推进当前地点的危机钟
2. 掷 D20 运气骰：1 = 灾难（危机额外 +N），20 = 好运（危机 -3）
3. 越过 omen 阈值 → 返回对应感官线索，DM 嵌入叙事做 foreshadowing
4. 满格 → 加权随机抽取遭遇（按 `action_tags` 上下文过滤），触发遭遇，危机钟归零
5. 若当前行动类型在 `trigger.blocked_by` 列表中 → 遭遇挂起（`deferred_encounter`），等待下一轮符合条件的行动触发

**DM 必须**：
- 每轮 `--view` 查看危机钟进度（仅 DM 可见）
- 收到 `omen` 时在叙事中埋入对应感官线索，不可忽略
- 满格触发遭遇时，omen 的累积线索让遭遇不突兀
- `--action` 时使用 `--tags` 标记行动类型（social/combat/patrol/ritual/rest），让引擎正确过滤遭遇池

**omen 阈值规范**：
- 最后一道 omen 设在 `danger_max - 2`，确保 DM 有 2 次 tick 的缓冲空间铺开压力
- 高危区 `danger_tick` 使用固定值或小骰子（1 或 1d2），防止 omen 被跳过

**遭遇挂起机制**：
- 当危机钟满格但当前行动类型被 `blocked_by` 阻塞时，遭遇写入 `deferred_encounter`
- 危机钟不归零——挂起的遭遇在下一次非阻塞行动中立即触发
- 触发后危机钟归零，恢复正常周期

---
## 返回 JSON 字段

| 字段 | 含义 | DM 行动 |
|------|------|---------|
| `danger` | `{current, max, advance}` — 当前地点的危机钟状态 | `--view` 查看，叙事中不暴露数值 |
| `omen` | 非 null → 越过了某个感官阈值 | 将 omen 文本嵌入当前叙事 |
| `encounter` | 非 null → 危机钟满格，强制触发战斗 | 执行战斗初始化流程 |
| `deferred_encounter` | 非 null → 遭遇已触发但被阻塞挂起 | 在下轮非阻塞行动中自动触发 |
| `encounter_pending` | 非 null → 上一遭遇未清除 | 先 `--clear_encounter` 再推进 |
| `catastrophe` | true → D20=1，危机额外跃升 | 叙述灾难并推进相关进度钟 |
| `boon` | true → D20=20，危机减少 | 叙述意外好运 |
| `filled_clocks` | 非空 → 有钟已满 | 立即引爆对应后果 |
| `flags` | 阈值标志列表 | 调整选项范围 |
| `goal_clock` | 目标时钟状态 | 满足触发条件时推进 |
| `tension` | 过往×目标张力 | 不可忽略，在叙事中体现 |
| `reminders` | 非空字符串数组 → 本轮可能遗漏的操作 | 逐条检查，执行对应命令 |
| `injury_healed` | true → 伤残计时归零 | 叙事中体现康复 |

DM 的职责：**把 JSON 翻译成叙事**。

---
## 灾难与好运

D20 运气骰独立于危机钟，但会影响它：

- **D20=1（灾难）**：危机额外 +`max(2, danger_max//3)`，可能直接触发遭遇。DM 必须在叙事中体现突如其来的变故
- **D20=20（好运）**：危机 -3。周围威胁暂时退散，DM 叙述一段喘息或意外收获

灾难不等于自动遭遇——它是一次急剧的危险升级，和 omen 一样需要嵌入叙事。
