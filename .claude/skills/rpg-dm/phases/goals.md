# 目标生命周期

> 完整规则 → `docs/goals.md`

## 誓言选择

玩家发现 2-3 个真相后触发：

- DM 从世界专属 `oaths.md` 固定池随机抽 1 个 + 即兴原创 2 个（1+2，与角色创建相同逻辑）
- 原创誓言按三维度框架生成（对象层 × 规模层 × 张力层），两个不得使用相同维度组合
- 三个一起用 AskUserQuestion 呈现（不标明哪个来自固定池）
- 玩家选定后：`python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_goal "誓言名"` → 玩家用自己的话宣告 → `--set_oath "誓言原话"`

## 推进与终结

- `--tick` 自动输出 `goal_clock` 字段，满足触发条件时：`python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --tick_goal_clock`
- 进度满格时提示玩家终结时机已到，玩家主动宣告：`python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --finale_goal`
- 终结成功后：`python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --complete_goal [--goal_location <key>] [--goal_npc <名>] [--goal_lore <key>]`
- 完成后展示 AskUserQuestion 分叉（"就此封笔" / "继续前行"）
- 失败条件发生时：`python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --fail_goal`。目标失败 ≠ 游戏结束，禁止提供"重试"
