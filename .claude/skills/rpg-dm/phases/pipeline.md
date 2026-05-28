# 流水线预查与种子分支

## 流水线预查

`config.json` → `pipeline.speculative_lookup` 为 `true` 时生效：

DM 展示选项的同时，静默预跑最可能选项的只读查询（`--lookup_npc`、`--lookup_location`、`--list_inventory` 等）。写操作（`--action`、`--tick`）禁止预跑。玩家选择命中则跳过重复查询，未命中只白跑了轻量只读（< 0.5s）。

## 投机神谕

DM 展示选项的空档期，可静默预跑 `--oracle` 覆盖最可能出现的环境问题（"门锁了吗""里面有人吗"）。`next_oracle` 已覆盖通用情况，此条用于需要第二个神谕或问题已明确的场景。

## 种子分支

展示选项前为每个分支预写 3 个具体细节（sensory / npc / risk）：

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --seed_branch \
  '{"option":"潜入暗巷","sensory":"通风口积灰的铜锈味","npc":"两个守卫在聊昨晚赌局","risk":"备用电源在左手第三扇门"}' \
  ...
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --get_seed 0    # 玩家选择后提取对应种子
```
