# 战斗流程

当 `--tick` 返回的 JSON 中 `encounter` 非 null，或玩家主动挑衅怪物时触发。

---

## 预生成（战斗开始前）

NPC 台词、环境叙事、进度钟中往往提前暗示某怪物即将遭遇。DM 应在暗示节点立即提交生成，利用叙事推进的时间窗口让图片提前就位：

```
python tools/bg.py --submit combat_<monster_key> --prompt "基于bestiary描述的中文提示词" --style combat --tags "关键词"
```

若已有专属图则跳过。`--poll` 在每次"继续"间隙和回合间隙自动收拢。

## 初始化

1. grep 活跃世界观的 `bestiary.md` 定位目标怪物（不读全文），了解习性、弱点、掉落、外貌
2. 检索活跃世界观的 `world_constants.json` 获取当前地点的固化感官细节
3. `python tools/bg.py --combat <skirmish|battle|boss|ambush> --monster <monster_key>`
   - 根据怪物威胁等级选择层级（见 `docs/background_system.md` 战斗层级表）
   - `--monster` 命中专属图则用专属图，未命中回退通用图
4. 若 bestiary.md 中有外貌描述且尚未提交生成：
   ```
   python tools/bg.py --submit combat_<monster_key> --prompt "基于bestiary描述的中文提示词" --style combat
   ```
5. `python tools/combat.py --init <monster_key> [--count N]` 初始化战斗状态
6. 使用 AskUserQuestion 展示战斗选项，header 用"战斗"

## 每回合流程

1. **回合事件**：`python tools/combat.py --round_event` → 结算持续效果 + 自动掷环境事件（15%概率）+ **自动执行所有存活敌人的攻击**
   - DM 将返回的 effect_ticks / effects_expired / environment_event / enemy_attacks 翻译为叙事
   - `enemy_attacks` 数组包含每个敌人的攻击结果（命中/未命中/暴击/大失败/伤害钟格）
   - 间隙：`python tools/bg.py --poll`（通常不需手动——`--set`/`--combat` 自动收拢）
2. **手动环境事件**（DM 强制触发时）：
   ```
   python tools/combat.py --env_event random       # 随机抽取
   python tools/combat.py --env_event cave_in      # 指定事件
   ```
3. AskUserQuestion 战斗选项
4. **玩家行动**：
   - 攻击 → `python tools/combat.py --attacker player --target <id> --action attack`
   - 使用物品 → 背包交互流程
   - 逃跑/对话 → D20 检定
5. **手动怪物行动**（特殊行为/传奇动作——普通攻击已在 `--round_event` 中自动执行）：
   `python tools/combat.py --attacker <id> --target player --action attack`
6. 所有 combat.py 返回的 JSON 均含 `dm_override` 块，DM 可随时覆盖

## 战斗结束

- 怪物全灭 → combat.py 自动返回 `combat_over: true, victory: true`
- 玩家逃跑 → `python tools/combat.py --end`
- 战斗结束后：`python tools/state_mgr.py --clear_encounter`
- 背景恢复：`python tools/bg.py --set <current_location>`

## 伤害即钟格推进

combat.py 直接以钟格结算伤害——不再有原始伤害到钟格的转换层。

- **玩家**：每次命中推进体质钟 N 格。体质钟填满（8/8）= 玩家倒下。
- **敌人**：每次命中推进当前阶段钟 N 格。弱小敌人单阶段；强大敌人多阶段——满格后自动切换下一阶段，AC、攻击模式、行为全部可变。最后一阶段满格=敌人倒下。

武器和怪物的 `ticks` 字段为钟格骰（如 `"1d3"` = 1-3 格，`"2d2"` = 2-4 格）。

### 阶段切换

combat.py 自动返回 `phase_transition` 字段，DM 必须在叙事中体现：

- `from`/`to`：阶段名
- `ac_was`/`ac_now`：AC 变化
- `behavior`：新阶段行为描述
- `attack`：新阶段攻击模式

---

# DM 覆盖权

代码负责计算和记录，DM 负责裁量和叙事。每次覆盖必须留理由，记录到 dm_log 中。

## 叙事层（自由覆盖，无需 --override）

- 修改敌人的台词、反应、表情
- 调整场景描述的细节
- 决定 NPC 的态度和情绪

## 规则层（可覆盖，必须留理由）

```
python tools/combat.py --override modify_ticks --value 3 --reason "..."
python tools/combat.py --override add_effect --reason "..."
python tools/combat.py --override advance_phase --target <id> --reason "..."
python tools/combat.py --override undo_override --reason "..."
```

`--reason` 必填，不写不执行。

## 数据层（不建议覆盖，需二次确认）

这些操作绕过战斗结算，使用 state_mgr.py 的 `--set` / `--use_item` 等命令。覆盖记录不会进入 dm_log，需自行在叙事中交代：

- 直接修改阶段/属性值
- 删除物品或线索
- 回滚已发生的事件
