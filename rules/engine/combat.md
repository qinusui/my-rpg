# 战斗流程

> 完整规则（含 DM 覆盖权） → `docs/combat.md`

触发：`--tick` 返回 `encounter` 非 null，或玩家主动挑衅。

**战斗数值由 DM 根据叙事现编**——bestiary.md 只提供来历/习性/叙事钩子，combat.py 只做状态追踪，不计算伤害或 AC。

**初始化**：grep bestiary.md → 查 world_constants.json → `bg.py --combat <层级> --monster <key>` → `combat.py --init <monster_key> [--count N]` → AskUserQuestion（header="战斗"）

**每回合**：`--round_event`（效果+环境事件+回合计数）→ DM 描述行动 → `state_mgr.py --d20` 判定 → DM 现编后果 → `combat.py --tick_constitution <N>` 更新伤害轨道 → 叙事

**阶段推进**（手动）：`combat.py --override advance_phase --target <id> --reason "..."`

**结束**：`state_mgr.py --clear_encounter` → `bg.py --set <location>`

> 伤害轨道由各世界观的 `default_state.json` → `combat_damage_attr` 指定。命令名称 `--tick_constitution` 不变，但实际更新的属性取决于世界观。
