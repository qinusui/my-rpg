# 云室 — 世界专属规则

> DM 每局开始前必须通读此文件。这些规则只在活跃世界观为 `cloud_chamber` 时生效。

---

## 一、属性与轨道

云室使用**四属性 + 三轨道**双轨系统。

### 属性（用于 D20 检定）

四项属性代表角色的适应性成长，范围 1-4，方向 `up`。修正值直接使用 filled 值（非中点偏移）。

| 属性 | key | 满格 | 含义 | 适用检定类型 |
|------|-----|------|------|-------------|
| 躯壳 | `躯壳` | 4 | 物理承载力、耐力、抵抗伤害 | 承受伤害、持久行动、抵抗毒素 |
| 清明 | `清明` | 4 | 精神锐度、感知力、意志力 | 察觉谎言、抵抗白息、保持专注 |
| 根系 | `根系` | 4 | 与世界/旧物的连接、知识积累 | 解读旧世界文字、操作设备、感知地脉 |
| 胆识 | `胆识` | 4 | 行动勇气、社交魄力、决断力 | 威吓、交涉、危险环境中的果断行动 |

属性靠特定经历提升（`--update 躯壳 +1`），上限 4。

### 轨道（损伤/消耗计量）

三条轨道方向为 `down`——填满意味着耗尽/崩溃。

| 轨道 | key | 满格 | 初始 | 含义 |
|------|-----|------|------|------|
| 身体 | `health` | 5 | 0 | 物理损伤——被攻击、坠落、中毒推进此轨道 |
| 清醒 | `spirit` | 5 | 0 | 精神完整度——白息侵蚀、枯萎症推进此轨道 |
| 补给 | `supply` | 5 | 2 | 圣水、食物、水——消耗时推进此轨道 |

任一轨道满格触发对应危机判定。`health`≥5 触发濒死，`spirit`≥5 触发 Face Desolation，`supply`≥5 触发断供（health 和 spirit 同时承压）。

### 阈值标志（`--view` 自动显示）

| 标志 | 触发条件 | DM 行为 |
|------|---------|--------|
| `wounded` | health ≥ 2 | 某些体力判定需额外说明 |
| `near_death` | health ≥ 4 | 触发【濒死】标签，每轮需判定维持 |
| `wither_early` | spirit ≥ 2 | DM 描述早期幻觉症状 |
| `face_desolation` | spirit ≥ 4 | DM 准备触发 Face Desolation 判定 |
| `supply_low` | supply ≥ 3 | 补给告急，每次消耗需判定是否真有效 |
| `supply_exhausted` | supply ≥ 5 | 断供，health 和 spirit 同时承压 |

### 印记系统

印记是经历留下的痕迹，提供**情境限定**的 D20 加值。不是全局 buff——只在相关场景下生效。

| 印记示例 | 加值 | 适用场景 |
|---------|------|---------|
| 见过灰质者 | +1 | 与低地生物交流判定 |
| 拆开过旧世界机器 | +1 | 面对基座设备判定 |
| 在嗜醇林存活过 | +1 | 极端环境生存判定 |
| 读懂过旧世界文字 | +2 | 旧世界文献解读（普通难度直接免除） |

```
python tools/state_mgr.py --add_mark "名称" --mark_bonus +1 --mark_context "适用场景"
```

### 完整判定公式

```
D20 + 属性值 + 印记加值 + 局势修正 vs DC

DC 范围: 12(简单) / 15(中等) / 18(困难) / 22(极难)
```

```
python tools/state_mgr.py --d20 --attr 胆识 --mark "见过灰质者" --mod ±N
```

---

## 二、角色创建

当 `--view` 显示 `player_name` 为 `"无名者"`（默认值）时触发。

**数据源**：`truths.md`（5 个认知维度）+ `origins.md`（3 个身份起点）。

**6 步 AskUserQuestion**，每次只问一个问题：

1. **维度一：对酿主的理解** → `--set_truth brewer_understanding <A/B/C>`. 数据源：`truths.md` §维度一
2. **维度二：圣水的效力** → `--set_truth holy_draught_effect <A/B/C>`. 数据源：`truths.md` §维度二
3. **维度三：对基座的传闻** → `--set_truth plinth_rumor <A/B/C>`. 数据源：`truths.md` §维度三
4. **维度四：关于灰质者** → `--set_truth gray_souls_view <A/B/C>`. 数据源：`truths.md` §维度四
5. **维度五：血酒契约** → `--set_truth first_vow <寻源/归座/救渴>`. 数据源：`truths.md` §维度五
   - 寻源 = 史诗誓言 DC 18，归座/救渴 = 地区誓言 DC 12
6. **身份起点** → `--set origin <scrubber/straggler/exile>`. 数据源：`origins.md`
   - 用 `--set_clock` 设置四项属性钟初始值（详见 origins.md 中各起点的命令）
   - 弃子额外：添加标签【枯萎先兆】
7. **命名**：`--set player_name "名字"`

角色创建期间不执行 `--tick`。最后写 200-300 字开场叙事，查 `world_constants.json` 获取 `altar_district` 感官细节。

---

## 三、世界专属机制

### 白息侵蚀

每进入新地点，DM 查 `world_constants.json` 中该地点的 `white_breath_level`：

| 等级 | spirit 推进 | 叙事表现 |
|------|-----------|---------|
| `low` | 每 3 轮 +1 | 几乎感觉不到 |
| `medium` | 每 2 轮 +1 | 头重、视野边缘模糊 |
| `high` | 每轮 +1 | 声音失真、分不清方向 |
| `extreme` | 每轮 +1 + 枯萎症判定 | 幻觉与现实不分 |

DM 静默执行 `--update spirit +N`，只在叙事中通过感官描写体现——不直接报告数字变化。

### 枯萎症叙事规范

```
spirit 0     正常，无症状
spirit 1-2   早期：偶尔看到不存在的影子，声音有轻微回响
spirit 3     中期：分不清某些记忆是真实还是幻觉，NPC对话有时"变形"
spirit 4     晚期：DM 可在叙事中插入玩家不确定真假的内容
spirit 5     触发 Face Desolation
```

### Face Desolation

spirit 满格（≥5）时执行。掷 1d6：

```
python tools/state_mgr.py --face_desolation
```

| 掷骰 | 结果 | 效果 |
|------|------|------|
| ≥6 | 强成功 | spirit-2，继续 |
| 3-5 | 弱成功 | 留下永久标签【desolation_scarred】，spirit-1，继续 |
| ≤2 | 失败 | 精神永久崩解，游戏结束 |

### 圣水使用

根据 `world_truths.holy_draught_effect` 决定效果：
- **精神锚点(A)**：恢复 spirit
- **物理抗体(B)**：恢复 health
- **诅咒之源(C)**：恢复选择轨道，但触发【依赖】标签检定

### 战斗伤害轨道

云室的伤害轨道为 `health`（由 `default_state.json` 的 `combat_damage_attr` 指定）。`combat.py --tick_constitution <N>` 实际更新的是 health 轨道的 filled 值。
