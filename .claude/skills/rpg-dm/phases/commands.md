# 命令速查

## 状态管理命令

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --action --attr 胆识 [--mod ±N]  # 玩家行动（= d20 + tick + view，推荐）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --d20 --attr 胆识 [--mod ±N]     # 独立 d20（不推进回合）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --tick [--update ...]             # 时间推进（JSON 输出）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --clear_encounter          # 清除待处理遭遇
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --add_item "物品" [--qty N] [--tags tag1,tag2]
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --use_item item_001 [--qty 1]
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --drop_item item_001 [--qty 1]
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --list_inventory [--tag weapon]
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --update strength +1       # 属性钟变动（±1 格）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --create_attr 龙族血脉 --attr_max 6 --direction up
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set player_name "名称"
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set current_location <id>
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set equipped_weapon item_003
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --add_clue "线索描述"
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --add_history "一句话摘要"
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_injury deep_wound --injury_ticks 5 --injury_penalty 3
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --heal
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --oracle                       # 神谕骰（1d6 + 世界诠释）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_truth <维度> <选择>       # 锁定世界真相（游戏中发现时执行，非创建时）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --face_desolation               # Face Desolation 判定（spirit 归零时）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_goal "目标名"             # 设置当前目标（固定誓言自动读取 goal_definitions.json）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_goal 寻弟 '{"dc":10,...}' # DM 原创誓言——手动传入 JSON 属性
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_oath "誓言原话"           # 为目标写入誓言
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --tick_goal_clock               # 推进目标时钟
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --finale_goal                   # 终结行动（1d6+进度 vs DC）
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --complete_goal                 # 完成目标 + 世界突变
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --fail_goal                     # 标记目标失败
```

## 战斗命令

```
python .claude/skills/rpg-dm/scripts/tools/combat.py --init <monster_key> [--count N]
python .claude/skills/rpg-dm/scripts/tools/combat.py --round_event
python .claude/skills/rpg-dm/scripts/tools/combat.py --env_event random
python .claude/skills/rpg-dm/scripts/tools/combat.py --env_event cave_in
python .claude/skills/rpg-dm/scripts/tools/combat.py --tick_constitution <N>
python .claude/skills/rpg-dm/scripts/tools/combat.py --override advance_phase --target <id> --reason "..."
python .claude/skills/rpg-dm/scripts/tools/combat.py --override defeat_enemy --target <id> --reason "..."
python .claude/skills/rpg-dm/scripts/tools/combat.py --override add_effect --target <id|player> --reason "..."
python .claude/skills/rpg-dm/scripts/tools/combat.py --override undo_override --reason "..."
python .claude/skills/rpg-dm/scripts/tools/combat.py --end
```
