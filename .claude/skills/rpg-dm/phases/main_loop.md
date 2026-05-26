# 游戏主循环

## 每轮流程

```
Turn 1:       --view → bg.py --set <location> → 叙事 → AskUserQuestion（必须）
Turn 2+:  [view 已知] → AskUserQuestion（必须） → 玩家行动 → --action --attr ... → 处理结果 → 叙事 → AskUserQuestion（必须）
```

1. **首轮**运行 `state_mgr.py --view` 获取初始状态视图 → 如果 `combat_state.enemies` 中有未 defeated 的敌人，必须先执行 `combat.py --init <monster>` 进入战斗流程 → 叙事 → **必须** AskUserQuestion
2. **每轮**（含首轮）玩家做出实质性行动后执行 `state_mgr.py --action --attr <属性> [--mod ±N]`，内部自动完成 d20 + tick + 状态视图（一次调用替代三次）
3. 处理 action 返回的 roll/danger/omen/遭遇/时钟/标志（详见 `docs/tick_system.md`）→ 叙事 → **必须** AskUserQuestion
4. **章节推进检视**：叙事中每揭示一个可锁定真相时，必须在同回合内执行 `--set_truth`。叙事中每发现一条可追踪线索时，必须在同回合内执行 `--add_clue`。禁止将线索和真相的机械写入推迟到会话结束。
5. 游戏结束时同样给选项——"新开一局" / "导出会话" / "就此结束"——结局叙事不给选项等于把玩家晾在废墟里

## 战斗检测硬约束

> 完整战斗规则 → `phases/combat.md`

每次 `--view` 或 `--action` 返回的状态视图中，如果出现以下任一条件：
- `combat_state.enemies` 中有 `defeated: false` 的条目
- `pending_encounter` 已触发且未被清除
- 玩家主动选择攻击性行动

**必须立即路由到战斗流程：`combat.py --init <monster_key>` → 进入战斗循环。** 禁止绕过战斗直接走叙事。

---

## 动态模块注入

引擎输出中的 `context.engine.inject_modules` 列出当前阶段需要的规则文件。每次 `--action` / `--tick` 后检查此字段，如有则必须在继续前读取所有列出的文件。

## 流水线与选项

选项展示与预查机制 → `phases/options.md`
流水线预查与种子分支 → `phases/pipeline.md`

## 神谕系统

DM 对以下问题没有明确答案时，掷神谕骰决定：

- 环境状态（门是开是关、天气、光线条件）
- 位置细节（NPC 此刻在哪、物品放在哪里）
- 时机（援军多久到、事件何时发生）
- 旁观者（路人是否注意到、有没有目击者）
- 遗留细节（之前未设定的房间里有什么）

```
python tools/state_mgr.py --oracle
```

返回 1d6 结果 + 世界专属诠释。诠释由 DM 根据上下文决定具体表现。

**消耗式预掷**：`--action` 和 `--tick` 输出中自动附带 `next_oracle` 字段（格式 `{"value": 4, "consumed": false}`），减少 DM 等待。DM 使用该神谕后调用 `--consume_oracle` 标记已消耗，下次行动自动生成新神谕。未消耗则复用。

## 场景背景

> 完整规则 → `docs/background_system.md`

首次使用初始化：`python tools/bg.py --init`

`--set` / `--combat` 自动收拢已完成的生成任务，无需手动 `--poll`。

| 时机 | 命令 |
|------|------|
| 到达新地点 | `bg.py --set <location_id>`（自动——随 `--set current_location` 触发） |
| 新地点/怪物无背景图 | `bg.py --submit <scene_id> --prompt "..." --tags "..." --mood ...` |
| 战斗开始 | `bg.py --combat <skirmish\|battle\|boss\|ambush> --monster <key>` |
| 氛围变化 | `bg.py --mood <key>`（自动——由 `--action --tags` 推断，无需 DM 手动调用） |
| 玩家不喜欢当前图 | `bg.py --skip <scene_id>` |
| 玩家收藏当前图 | `bg.py --pin <scene_id>` |
| 会话结束 | `bg.py --reset`（**必须**） |

## D20 检定

> 完整规则 → `docs/d20.md`

独立 d20 掷骰（不推进回合，用于非行动性判定）：

```
python tools/state_mgr.py --d20 --attr strength[,agility] [--mod ±N]
```

玩家行动时使用 `--action`（= d20 + tick + view），以下场景才单独用 `--d20`：
- 防御/反应性掷骰（敌人行动触发的检定）
- NPC 之间的对抗掷骰
- 连续多次检定中的额外掷骰（同一回合内）

- 1 = 大失败，20 = 大成功。DC: 10 = 简单，15 = 中等，20 = 困难
- 多属性用逗号分隔，修正取平均值。`--mod` 为局势修正，必须在掷骰前决定
- 伤残的 `dc_penalty` 加到 DC 上

## 动态时间与遭遇

> 完整规则 → `docs/tick_system.md`

每次实质性行动后执行 `python tools/state_mgr.py --tick`。DM 的职责：把 JSON 翻译成叙事。

地点危机钟随每次 tick 推进，`omen` 字段提供感官线索用于 foreshadowing，满格才触发遭遇——不再是二元 D20 掷骰。

## 进度钟

> 完整规则 → `docs/clocks.md`

```
python tools/state_mgr.py --create_clock "钟名" --clock_max N --consequence "满格后果"
python tools/state_mgr.py --tick_clock "钟名"
python tools/state_mgr.py --set_clock "钟名" N
python tools/state_mgr.py --reset_clock "钟名"
```

推进后禁止在叙事中展示数值。`filled: true` 时立即引爆后果——不是预告，是发生。

## 代价库

> 完整规则 → `docs/consequences.md`

D20 失败时：打开活跃世界观的 `consequences.md` → 判定失败等级（差 1-4=轻微，5-9=实质，10+/nat1=致命）→ 选取代价 → 立即执行 → 叙事体现。

废止句式："虽然失败了但是……""侥幸的是……""幸好……"

## 知识防火墙

> 完整规则 → `docs/knowledge_firewall.md`

世界文件是 DM 知识库，不是玩家知识库。每次查阅后自问："我的角色此刻站在哪里？看到什么？听到什么？背包里有什么？"——答案之外，不说。

知识追踪：
```
python tools/state_mgr.py --learn_fragment <N>
python tools/state_mgr.py --learn_npc "名称"
python tools/state_mgr.py --reveal_lore "文献名"
```

## NPC 关系

> 完整规则 → `docs/npc_relationships.md`

```
python tools/state_mgr.py --affinity "海拉"                              # 查询
python tools/state_mgr.py --affinity "海拉" close --milestone "..."       # 升级
```

8 档刻度：hostile → wary → cold → stranger(默认) → acquaintance → friend → close → intimate。禁止跳级，禁止数值化展示，浪漫线必须由玩家主动推动。

## 日志与复盘

关键剧情节点：`python tools/state_mgr.py --add_history "一句话摘要"`
长时间未玩后再次打开时，主动用 history 做前情提要。
