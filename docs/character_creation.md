# 角色创建

> 当 `--view` 显示 `player_name` 为 `"冒险者"`（默认值）时触发。
> 数据来源：`rules/{active_world}/character_options.json`。
> 严格按序执行，每次只问一个问题。

---

## Phase 1 — 提问 (AskUserQuestion)

| Step | header | question | 数据源 | 备注 |
|------|--------|----------|--------|------|
| 1 | 种族 | 你属于哪个种族？ | `races` | description=desc+属性修正；人类→(Recommended) |
| 2 | 职业 | 你选择了什么道路？ | `classes` | description=desc+属性修正+起始装备；战士→(Recommended) |
| 3 | 过往 | 你从哪里来？ | `backgrounds` | description=desc+属性修正；不标记推荐 |
| 4 | 目标 | 你为何上路？ | `goals` | description=desc+`tension_effect` 摘要（若过往∈tension_with） |
| 5 | 命名 | 你的名字是？ | `sample_names` | 选3个名字 + Other |

---

## Phase 2 — 写入

### Step 6: 属性钟修正

种族 + 职业 + 过往 attr_mods 同属性累加（每 +1 = 推进 1 格）。

```
python tools/state_mgr.py --update strength +N     # 力量钟 6 格，默认 3 格
python tools/state_mgr.py --update agility +N      # 敏捷钟 6 格，默认 3 格
python tools/state_mgr.py --update constitution +N  # 体质钟 8 格（受伤推进），默认 1 格
# magic / wealth / reputation / sanity 各 6 格，默认 3 格（magic 默认 1）
```

### Step 7: 身份、目标、出生点

```
python tools/state_mgr.py --set player_name "名字"
python tools/state_mgr.py --set player_race "种族名"
python tools/state_mgr.py --set player_class "职业名"
python tools/state_mgr.py --set_background "过往名"
python tools/state_mgr.py --set_goal "目标名" '{"clock_name":"时钟名","clock_max":N,"clock_trigger":"触发条件"}'
python tools/state_mgr.py --set current_location "种族的start_location"
```

### Step 8: 起始装备

来自职业 starting_items，逐物品执行。武器/防具自动装备。

```
python tools/state_mgr.py --add_item "物品名" --tags tag1,tag2
```

---

## Phase 3 — 确认与开场

- **Step 9**: `--view` 展示完整角色卡，问"准备好了吗？"
- **Step 10**: 写 200-300 字开场叙事。查 `world_constants.json` 获取出生地感官细节。若过往与目标有 tension_with → 加一句暗示氛围。禁止透露碎片位置/NPC秘密/未亲历信息。

**注意**：角色创建期间不执行 `--tick`。开场叙事结束后才进入正常游戏循环。
