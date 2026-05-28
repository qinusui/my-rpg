# 身份起点

以下三个为**固定池**。每次角色创建时，DM 从中随机抽 1 个，再即兴原创 2 个，合计 3 个作为 AskUserQuestion 选项——不标明哪个是固定的。

玩家选定后不可更改。结果写入 state.json 的 origin 字段。属性钟按所选起源的命令设置。

原创起源必须满足 §原创起源规范（见 rules.md §二）。

---

## 祭坛洗刷工 (The Scrubber)

- **key**: `scrubber`
- **大地点**：祭坛区
- **社会地位**：最底层
- **在乎的事物**：每天配给的那一小份口粮要带回去给妹妹；圣樽台阶第三级松动的石板下藏着一本旧世界的图册
- **初始已知真相**：圣水会腐蚀金属（物理特性）
- **初始危机**：目睹圣樽破碎，掌握了不该掌握的物质
- **属性倾向**：躯壳 3 / 清明 1 / 根系 2 / 胆识 2
- **特殊能力**：能凭气味判断圣水纯度
- **社会关系**：定居点贱民身份，祭司对你有天然优越感

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 躯壳 3
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 清明 1
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 根系 2
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 胆识 2
```

---

## 远征队弃子 (The Straggler)

- **key**: `straggler`
- **大地点**：低地边界
- **社会地位**：中层，但已被宣告死亡
- **在乎的事物**：远征队里还有一个人没出来——你答应过要带他回去；口袋里有一块刻了名字的金属牌，那是你唯一没丢掉的东西
- **初始已知真相**：见过灰质者，知道低地真实生态
- **初始危机**：处于枯萎症早期，被定居点视为已死之人
- **属性倾向**：躯壳 2 / 清明 2 / 根系 1 / 胆识 3
- **特殊能力**：在低地的方向感和生存判定有利。获得永久标签【枯萎先兆】
- **社会关系**：定居点无法公开你的身份，你必须伪装

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 躯壳 2
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 清明 2
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 根系 1
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 胆识 3
```

---

## 基座流放者 (The Plinth-Exile)

- **key**: `plinth_exile`
- **大地点**：禁地附近
- **社会地位**：外来者，被视为带来诅咒的怪物
- **在乎的事物**：你被流放前有人塞给你一张纸条，上面写着一个坐标和一句话——"到了那里，呼吸是免费的"；你想证明那个人没有说错
- **初始已知真相**：懂旧世界语言，能读懂生锈机器上的标识
- **初始危机**：地表氧气稀薄，持续承受适应性体质损耗
- **属性倾向**：躯壳 1 / 清明 3 / 根系 2 / 胆识 2
- **特殊能力**：面对旧世界设备时免除首次检定失败的最坏结果
- **社会关系**：没有任何定居点关系，从零建立

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 躯壳 1
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 清明 3
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 根系 2
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 胆识 2
```

---

## 守卫逃兵 (The Guard Deserter)

- **key**: `guard_deserter`
- **大地点**：祭坛区
- **社会地位**：前执法者，现为逃亡者
- **在乎的事物**：你逃跑那晚，有个和你一起值夜的新兵替你挡了追兵——你不知道他现在是死是活；你腰上还挂着他塞给你的半块干饼
- **初始已知真相**：曾见过不该存在的东西——祭坛后殿的某扇门后面，有什么在呼吸
- **初始危机**：正在被曾经的同袍追杀，他们说你擅离职守，但你知道真正的原因
- **属性倾向**：躯壳 3 / 清明 1 / 根系 2 / 胆识 2
- **特殊能力**：熟悉祭坛区的每一条巷子和巡逻路线，在祭坛区的潜行和逃脱判定有利
- **社会关系**：曾经的守卫同袍现在可能是追兵，也可能是装作不认识你的旧友

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 躯壳 3
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 清明 1
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 根系 2
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_clock 胆识 2
```

[来源：session_2026-05-24]
