# 角色创建

> 触发条件：`player_name` 为默认值，或 `scar`/`drive`/`appearance` 任一为空。

## 通用约束

- 每次只问一个问题（AskUserQuestion），严格按 `rules/{active_world}/rules.md` §二中的步骤顺序执行
- 角色创建期间不执行 `--tick`
- 所有叙事正文使用 `>` 引用块，禁止 HTML 标签
- 选项描述中不能出现属性名和数值——全部用叙事语言表达

## 步骤判定（断点续建）

DM 从 `state.json` 读取以下字段，确定当前应该进入哪一步：

```
origin      → 空则步骤 1
scar        → origin 非空但 scar 空则步骤 2
drive       → scar 非空但 drive 空则步骤 3
appearance  → drive 非空但 appearance 空则步骤 4
属性未调整   → appearance 非空但属性仍为起源默认值则步骤 5
player_name → 以上全部非空但 name 仍为 "无名者" 则步骤 6
```

若步骤 1-5 均已完成后会话中断，下次启动时 player_name 为 "无名者" 的概率极低（步骤 5 时 name 通常已设），但若确实发生，则进入步骤 6。

## 各步骤执行要点

### 步骤 1：身份起点

1. 读 `rules/{active_world}/origins.md`，从固定池随机抽 1 个
2. 按 `rules.md` §原创起源规范 即兴创作 2 个
3. AskUserQuestion：label 用起源名，description 以人物处境和在乎的事物为首句，不标明哪个来自固定池
4. 玩家选定后：`--set origin <key>`（引擎自动注入 NPC、初始物品、初始位置）

### 步骤 2：旧伤

1. 读 `origins.md` 中所选起源的 `scar_options`，随机抽 1 个
2. 按 `rules.md` 步骤 2 中的维度矩阵即兴创作 2 个
3. AskUserQuestion：以人物感受为首句，不直接说"你的旧伤是……"
4. 玩家选定后：`--set scar "旧伤描述"`

### 步骤 3：执念

1. 读 `origins.md` 中所选起源的 `drive_options`，随机抽 1 个
2. 按 `rules.md` 步骤 3 中的维度矩阵即兴创作 2 个
3. 执念应与步骤 2 选择的旧伤形成呼应——旧伤是过去，执念是未来
4. 玩家选定后：`--set drive "执念描述"`

### 步骤 4：形貌

1. 读 `origins.md` 中所选起源的 `appearance_options`，随机抽 1 个
2. 按 `rules.md` 步骤 4 中的维度矩阵即兴创作 2 个
3. 必须是感官描写——能看到、听到、闻到的具体细节。禁止泛化和数字
4. 玩家选定后：`--set appearance "形貌描述"`

### 步骤 5：取舍

1. 读当前属性值（`--view`）
2. 提供 3-4 个纯叙事选项，每个对应一项属性 +1 和另一项 -1，也提供"保持不变"
3. 选项描述不能出现属性名和数值——只写叙事后果
4. 确保变完后属性仍在 1-4 范围内
5. 玩家选定后：`--update attr1 +1` 和 `--update attr2 -1`

### 步骤 6：命名

`--set player_name "名字"`。命名完成后按 `rules.md` §开场白原则 写开场叙事。

## 开场叙事

角色创建完成后，DM 直接进入开场叙事（不需要额外 `--tick`）：

1. `bg.py --set <current_location>`
2. 按 `rules.md` 的开场白原则和参考范例写开场叙事
3. 叙事中自然融入旧伤、执念和形貌——不逐条罗列，而是在处境中让线索自己浮现
4. 叙事结束 → AskUserQuestion（第一个游戏选择）
