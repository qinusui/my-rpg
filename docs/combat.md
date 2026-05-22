# 战斗流程

当 `--tick` 返回的 JSON 中 `encounter` 非 null，或玩家主动挑衅怪物时触发。

---

## 核心原则

**战斗数值由 DM 根据叙事现编。** bestiary.md 只提供来历、习性和叙事钩子——不提供 AC、伤害骰、HP。combat.py 是状态追踪器，不是计算引擎。

骰子只回答"行不行"，后果由 DM 决定。

---

## 预生成（战斗开始前）

NPC 台词、环境叙事、进度钟中往往提前暗示某怪物即将遭遇。DM 应在暗示节点立即提交生成，利用叙事推进的时间窗口让图片提前就位：

```
python tools/bg.py --submit combat_<monster_key> --prompt "基于bestiary描述的中文提示词" --style combat --tags "关键词"
```

若已有专属图则跳过。`--set`/`--combat` 自动收拢已完成的生成任务。

## 初始化

1. grep 活跃世界观的 `bestiary.md` 定位目标怪物（不读全文），了解来历、习性、叙事钩子
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

```
DM 描述战况
  ↓
AskUserQuestion 战斗选项
  ↓
DM 根据玩家选择调用 state_mgr.py --d20 判定
  ↓
DM 根据骰子结果现编后果（命中程度、伤害大小、叙事转折）
  ↓
DM 决定体质钟变化幅度
  ↓
combat.py --tick_constitution <N>     # 更新玩家体质钟
  ↓
combat.py --round_event               # 推进回合，结算效果，掷环境事件
  ↓
叙事
```

### 回合事件

`python tools/combat.py --round_event` 执行以下操作：

1. 结算持续效果（减少剩余回合数，报告到期效果）
2. 自动掷环境事件（15% 概率，纯叙事——无 AC/命中修正）
3. 回合数 +1

**不再自动执行敌人攻击。** 敌人的行动由 DM 根据叙事感觉描述，通过 `--d20` 判定后果。

### 环境事件

环境事件是纯叙事提示——无数值修正。DM 根据事件描述决定当场的影响：

```
python tools/combat.py --env_event random       # 随机抽取
python tools/combat.py --env_event cave_in      # 指定事件
```

### 玩家行动

DM 描述玩家意图 → `python tools/state_mgr.py --d20 --attr <属性> [--mod ±N]` → 根据结果现编后果。

| 骰子结果 | 含义 |
|----------|------|
| 大成功 (nat 20) | 超预期命中，可附加额外效果 |
| 成功 (≥ DC) | 命中，DM 决定体质钟推进幅度 |
| 失败 (< DC) | 未命中或部分命中 |
| 大失败 (nat 1) | 灾难性失误 |

**DM 根据叙事感觉决定伤害幅度**——不查表，不翻数值。同一招打同一个怪物，在不同情境下可以造成不同程度的伤害。

### 体质钟更新

```
python tools/combat.py --tick_constitution <N>    # 玩家受伤 N 格
```

体质钟满格（8/8）= 玩家倒下。怪物不追踪体质钟——DM 根据叙事判断何时倒下或逃跑。

---

## 阶段系统

多阶段怪物（精英/Boss）保留阶段概念，但阶段切换完全由 DM 手动触发：

```
python tools/combat.py --override advance_phase --target <id> --reason "..."
```

DM 在叙事中判断阶段切换的时机——当玩家造成足够伤害或触发特定条件时，手动推进阶段并描述新形态。

阶段信息仅用于叙事节奏，不附带数值变化。

---

## 战斗结束

- DM 判断怪物全灭 → `python tools/combat.py --end`
- 玩家倒下（体质钟满） → `--round_event` 或 `--tick_constitution` 自动返回 `combat_over: true`
- 战斗结束后：`python tools/state_mgr.py --clear_encounter`
- 背景恢复：`python tools/bg.py --set <current_location>`

---

# DM 覆盖权

DM 负责裁量和叙事。每次覆盖必须留理由，记录到 dm_log 中。

## 叙事层（自由覆盖，无需 --override）

- 修改敌人的台词、反应、表情
- 调整场景描述的细节
- 决定 NPC 的态度和情绪

## 规则层（可覆盖，必须留理由）

```
python tools/combat.py --override advance_phase --target <id> --reason "..."
python tools/combat.py --override defeat_enemy --target <id> --reason "..."
python tools/combat.py --override add_effect --target <id|player> --reason "..."
python tools/combat.py --override undo_override --reason "..."
```

`--reason` 必填，不写不执行。

## 数据层（不建议覆盖，需二次确认）

这些操作绕过战斗结算，使用 state_mgr.py 的 `--set` / `--use_item` 等命令。覆盖记录不会进入 dm_log，需自行在叙事中交代：

- 直接修改属性值
- 删除物品或线索
- 回滚已发生的事件
