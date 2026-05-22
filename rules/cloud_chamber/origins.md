# 身份起点

DM 在角色创建时用 AskUserQuestion 呈现三个起点。玩家选一个，不可更改。结果写入 state.json 的 origin 字段。

起点选择后，DM 用 `--set_clock` 设置四项属性钟的初始值。

---

## 祭坛洗刷工 (The Scrubber)

- **社会地位**：最底层
- **初始已知真相**：圣水会腐蚀金属（物理特性）
- **初始危机**：目睹圣樽破碎，掌握了不该掌握的物质
- **属性倾向**：躯壳 3 / 清明 1 / 根系 2 / 胆识 2
- **特殊能力**：能凭气味判断圣水纯度
- **社会关系**：定居点贱民身份，祭司对你有天然优越感

```
python tools/state_mgr.py --set_clock 躯壳 3
python tools/state_mgr.py --set_clock 清明 1
python tools/state_mgr.py --set_clock 根系 2
python tools/state_mgr.py --set_clock 胆识 2
```

---

## 远征队弃子 (The Straggler)

- **社会地位**：中层，但已被宣告死亡
- **初始已知真相**：见过灰质者，知道低地真实生态
- **初始危机**：处于枯萎症早期，被定居点视为已死之人
- **属性倾向**：躯壳 2 / 清明 2 / 根系 1 / 胆识 3
- **特殊能力**：在低地的方向感和生存判定有利。获得永久标签【枯萎先兆】
- **社会关系**：定居点无法公开你的身份，你必须伪装

```
python tools/state_mgr.py --set_clock 躯壳 2
python tools/state_mgr.py --set_clock 清明 2
python tools/state_mgr.py --set_clock 根系 1
python tools/state_mgr.py --set_clock 胆识 3
```

---

## 基座流放者 (The Plinth-Exile)

- **社会地位**：外来者，被视为带来诅咒的怪物
- **初始已知真相**：懂旧世界语言，能读懂生锈机器上的标识
- **初始危机**：地表氧气稀薄，持续承受适应性体质损耗
- **属性倾向**：躯壳 1 / 清明 3 / 根系 2 / 胆识 2
- **特殊能力**：面对旧世界设备时免除首次检定失败的最坏结果
- **社会关系**：没有任何定居点关系，从零建立

```
python tools/state_mgr.py --set_clock 躯壳 1
python tools/state_mgr.py --set_clock 清明 3
python tools/state_mgr.py --set_clock 根系 2
python tools/state_mgr.py --set_clock 胆识 2
```
