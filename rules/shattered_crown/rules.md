# 破碎之冠 — 世界专属规则

> DM 每局开始前必须通读此文件。这些规则只在活跃世界观为 `shattered_crown` 时生效。

## 加载顺序与边界（Core + Overlay）

1. 先读 `docs/core/rules_index.md` 与其指向的核心规则文档
2. 再读本文件的世界覆写内容
3. 若本文件与核心规则冲突：以本文件为准

本文件聚焦四类内容：
- 破碎之冠属性映射与阈值标志
- 破碎之冠专属机制（碎片追踪、封印崩解、张力机制等）
- 破碎之冠叙事约束与创角差异
- 对核心规则的必要覆写

---

## 一、属性钟

破碎之冠使用七属性进度钟系统。方向 `up`=更多更强，`down`=更多更弱。

| 属性 | key | 满格 | 初始 | 方向 | 含义 |
|------|-----|------|------|------|------|
| 力量 | `strength` | 6 | 3 | ↑ | 近战攻击、攀爬、举重 |
| 敏捷 | `agility` | 6 | 3 | ↑ | 潜行、闪避、开锁、远程 |
| 体质 | `constitution` | 8 | 1 | ↓ | 血量/耐久——受伤推进此钟 |
| 理智 | `sanity` | 6 | 3 | ↓ | 精神压力——龙神低语、目睹恐怖推进此钟 |
| 魔力 | `magic` | 6 | 1 | ↑ | 施法、地脉感知、符文解读 |
| 财富 | `wealth` | 6 | 3 | ↑ | 金钱、交易、贿赂 |
| 声望 | `reputation` | 6 | 3 | ↑ | 名声、威慑、社交 |

体质和理智为 `down` 方向：filled 越高越糟。修正值自动取反。

**阈值标志**（`--view` 自动显示）：

| 标志 | 触发条件 | DM 行为 |
|------|---------|--------|
| `bribe_unlocked` | wealth ≥ 5 | 选项中出现贿赂/贵族社交/雇佣佣兵 |
| `destitute` | wealth ≤ 1 | 平民冷淡，旅店拒客，只能睡马厩或街头 |
| `renown` | reputation ≥ 5 | 选项中出现"名声威慑""召集援兵" |
| `suspicious` | reputation ≤ 1 | 守卫盘查概率翻倍，商人加价 |
| `force_retreat` | constitution ≥ 6 | 强制出现撤退/治疗选项 |
| `hallucination` | sanity ≥ 4 | 选项中出现 1 个幻觉/恐惧伪装选项 |
| `arcane_sense` | magic ≥ 5 | 选项中出现奥术感知、魔力交涉、地脉探寻 |

---

## 二、角色创建

当 `--view` 显示 `player_name` 为 `"冒险者"`（默认值）时触发。

**数据源**：`character_options.json`（races / classes / backgrounds / goals / styles）。

**5 步 AskUserQuestion**（+1 步选风格），每次只问一个问题：

1. **种族**：`character_options.json` → `races` → `--set player_race`。description 含属性修正
2. **职业**：`character_options.json` → `classes` → `--set player_class`。description 含属性修正+起始装备
3. **过往**：`character_options.json` → `backgrounds` → `--set_background`
4. **目标**：`character_options.json` → `goals` → `--set_goal`。若过往与目标有 `tension_with` 匹配→描述中加张力提示
5. **叙事风格**：`character_options.json` → `styles` → 写入 `config.json` 的 `narrative.style`
6. **命名**：从 `races[所选种族].sample_names` 取 3 个名字 + Other → `--set player_name`

### 属性钟修正

种族+职业+过往的 `attr_mods` 同属性累加。每 +1 = 填 1 格（up 钟），每 -1 = 减 1 格。

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --update strength +N
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --update constitution +N   # down 方向，+1=受伤加深
```

### 起始装备与出生点

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set current_location <种族的start_location>
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --add_item "物品名" --tags tag1
```

角色创建期间不执行 `--tick`。最后写 200-300 字开场叙事，查 `world_constants.json` 获取出生地感官细节。

---

## 三、世界专属机制

### 王冠碎片知识追踪

八片王冠碎片散落在艾瑟兰各处。玩家发现相关信息时 DM 记录：

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --learn_fragment <1-8>
```

`--view` 展示已知碎片编号。`docs/knowledge_firewall.md` 约束 DM 不透露未发现碎片的信息。

### 过往×目标张力

当角色的过往与目标在 `character_options.json` 中存在 `tension_with` 匹配时：

- `--view` 自动展示张力段落
- `--tick` 自动输出 `tension` 字段，DM 不可忽略
- 张力提供双向修正：有利面（如特定情境 DC-2）和不利面（如 san 钟 +1）

张力不是惩罚——是角色的内在驱动力。

### 龙神封印进度钟

世界级进度钟"封印崩解"（8 格）。DM 在重大主线事件发生时刻意推进。满格意味着封印进入临界状态——不是龙神立刻苏醒，但时间窗口急剧缩小。

### 战斗伤害轨道

破碎之冠的伤害轨道为 `constitution`。`combat.py --tick_constitution <N>` 推进体质钟的 filled 值（方向为 down，所以推进=恶化）。
