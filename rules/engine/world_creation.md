# 世界观创建协议

> DM 按此协议一步步带着玩家创建新世界观。每一步：DM 解释当前步骤 → AI 生成建议内容 → 玩家确认或修改 → 写入文件。

---

## 前置条件

- 玩家已提出新世界观的初始想法（一句话即可）
- DM 已读取 `rules/reference/world_design_spec.md`（设计约束手册）
- 当前不在游戏中（无活跃角色状态）

## 流程总览

```
Phase 1: 核心定义   →  world.md 核心章节
Phase 2: 骨架搭建   →  world_constants.json 骨架 + bestiary.md + origins.md
Phase 3: 血肉填充   →  完整的所有文件
Phase 4: 验证       →  跨文件一致性报告
```

每步输出文件后立即写入，不等到阶段结束。

---

## Phase 1：核心定义

### 步骤 1：世界观注册

DM 向玩家确认世界观名称（中文）和英文 key。

**AskUserQuestion**：
- header: "世界名称"
- question: "这个世界叫什么名字？先给一个中文名和一个英文标识（用于文件名和命令，下划线格式）。"
- options: 不预设选项，由玩家自由输入。DM 根据玩家输入生成 key 建议，玩家确认。

**AI 建议**：根据玩家的一句话描述，生成 1-2 个命名建议。

**确认后执行**：
```
python tools/world_loader.py register <key> "<中文名>" rules/<key>
python tools/world_loader.py switch <key>
mkdir rules/<key>/backgrounds rules/<key>/sessions
```

---

### 步骤 2：核心冲突

DM 解释：核心冲突是世界的底色——不是主线剧情，是所有地区都能感受到的张力。

**AskUserQuestion**：
- header: "核心冲突"
- question: "这个世界的核心冲突是什么？用一句话定义驱动整个世界的那股张力。"
- options: 不预设，由玩家自由输入。

**AI 建议**：基于玩家的一句话描述，生成 2-3 个核心冲突方向，每个方向附一句解释为什么它能驱动世界。玩家选择或自己写。

**确认后执行**：写入 `world.md` 的核心冲突段落。

---

### 步骤 3：失败底线

DM 解释：如果玩家什么都不做、或做错了关键选择，世界最坏能坏到什么程度。

**AskUserQuestion**：
- header: "失败底线"
- question: "这个世界最坏能坏到什么程度？那个不可逆的失败条件是什么？"
- options: AI 生成 2-3 个选项，每条包含失败条件的描述和它为什么不可逆。

**AI 建议**：每个选项包含：失败条件名称 + 触发方式 + 不可逆后果 + 玩家能否在失败后继续游戏。

**确认后执行**：追加写入 `world.md`。

---

### 步骤 4：英雄定义

DM 解释：这个世界里"英雄"长什么样——决定了角色创建选项的风格。

**AskUserQuestion**：
- header: "英雄定义"
- question: "这个世界的'英雄'是什么？他们是战士、幸存者、探索者、还是别的什么？"
- options: AI 生成 3 个选项，如"废墟中的幸存者——普通人在绝境中做出选择"、"被选中的人——背负着无法推卸的使命"、"流浪者——不属于任何地方，但到过所有地方"。

**AI 建议**：附上对属性倾向的暗示（这个英雄类型的角色通常在哪些属性上更强）。

**确认后执行**：追加写入 `world.md`。此步骤也确定了 `origins.md` 中固定起源的风格基调。

---

## Phase 2：骨架搭建

### 步骤 5：主要地区（3-5 个）

DM 解释：每个地区必须有名字、感官描述、以及这里的核心矛盾。

**AskUserQuestion**（逐个地区，共 3-5 轮）：
- header: "地区 N"
- question: "第 N 个主要地区是什么？描述它的地理特征和在这里生活的人面临的矛盾。"
- options: AI 基于已确认的核心冲突生成 3 个地区候选，每个包含名称 + 一句感官描述 + 这里的人面临的地区性冲突。

**AI 建议**：每个地区候选包含：名称（中文+英文key）、sensory（always/sound/mood 三行）、white_breath_level 估算（如果有类似白息的环境压力）、地区性冲突。

**全部确认后执行**：
- 写入 `world_constants.json` 的 `locations` 字段
- 写入 `world.md` 的地区章节
- 为每个地区在 `encounter_tables.json` 中创建骨架条目（含 danger_max/danger_tick 占位值、空的 omens 和 pool）

---

### 步骤 6：势力（2-3 个）

DM 解释：势力之间有矛盾，每个势力有认知盲区。

**AskUserQuestion**（逐个势力，共 2-3 轮）：
- header: "势力 N"
- question: "这个势力的名字、目标、以及他们最大的认知盲区是什么？"
- options: AI 基于已确认的地区和核心冲突生成候选势力。

**AI 建议**：每个势力包含：名称、控制区域、公开目标、真实目标、认知盲区（believes_wrongly / unaware_of）、与其他势力的矛盾。

**确认后执行**：写入 `world.md` 的势力章节。

---

### 步骤 7：怪物（5-8 种）

DM 解释：怪物绑定地区。每种怪物需要回答：在哪儿出现、威胁来自什么、非战斗应对方式。

**AskUserQuestion**（逐个怪物，共 5-8 轮）：
- header: "怪物 N"
- question: "这种怪物叫什么？它在什么环境下出现？它的威胁来自什么？"
- options: AI 基于已确认的地区生成 3 个怪物候选，每个绑定一个地区。

**AI 建议**：每个怪物包含：名称（中文+英文key）、绑定地区、生态描述、威胁类型（数量/强度/环境配合）、非战斗应对方式、叙事钩子。

**确认后执行**：写入 `bestiary.md`。

---

### 步骤 8：角色起点（3 个固定起源）

DM 解释：角色起点决定了玩家开局时是谁、在哪、知道什么、在乎什么。参照云室的起源格式。

**AskUserQuestion**（逐个起源，共 3 轮）：
- header: "起源 N"
- question: "这个角色的出身是什么？他们在哪生活、在乎什么、有什么危机正在逼近？"
- options: AI 基于已确认的地区和势力生成 3 个起源候选。

**AI 建议**：每个起源包含：key、大地点、社会地位、在乎的事物、初始已知真相、初始危机、属性倾向（四项总和=8，单项 1-3）、特殊能力、社会关系。参照 `rules/cloud_chamber/origins.md` 的格式。

**确认后执行**：写入 `origins.md`。

---

## Phase 3：血肉填充

### 步骤 9：NPC（8-15 个）

DM 解释：每个 NPC 必须有认知缺陷。不追求数量——追求每个人都是活的信息茧房。

**AskUserQuestion**（分批，每批 2-3 个 NPC）：
- header: "NPC 群"
- question: "这批 NPC 是谁？他们在哪、在做什么、他们的认知盲区是什么？"
- options: AI 基于已确认的地区和势力生成 NPC 候选。

**AI 建议**：每个 NPC 包含：name_cn、location、role、quirk（口头禅/习惯动作）、voice（说话风格）、cognition（knows / believes_wrongly / conceals / unaware_of 至少填两个）。

**确认后执行**：写入 `world_constants.json` 的 `npcs` 字段。

---

### 步骤 10：物品（8-12 种）

DM 解释：物品分层——武器/防具/消耗品/任务物品/传说物品各几个。

**AskUserQuestion**（分批，每批 3-4 个物品）：
- header: "物品"
- question: "这些物品是什么？它们的外观、来历、特殊之处？"
- options: AI 基于世界观特征生成物品候选，覆盖多个层级。

**AI 建议**：每个物品包含：名称、类别、外观、来历/传说、效果描述（叙事性，不写数值）。

**确认后执行**：写入 `items.md`。

---

### 步骤 11：世界级进度钟（2-3 个）

DM 解释：进度钟是"世界在玩家不在场时自己运转的证据"。

**AskUserQuestion**：
- header: "进度钟"
- question: "这个世界有哪些压力在悄悄累积？哪些事情即使玩家不碰也会自己推进？"
- options: AI 生成 3-4 个候选进度钟，每个包含：名称、满格值、推进节奏、满格后果。

**AI 建议**：基于核心冲突和失败底线设计。至少一个是"世界在恶化"，至少一个与某个势力相关。

**确认后执行**：写入 `world.md` 的进度钟章节。

---

### 步骤 12：代价库

DM 解释：玩家失败时 DM 从代价库中选取后果。按轻微/实质/致命三级分类。

**AI 直接生成**（无需逐条确认，根据已有世界观内容自动生成）：
- 社会代价 3-4 条
- 物质代价 3-4 条
- 身体代价 3-4 条
- 信息代价 3-4 条
- 叙事代价 3-4 条

**生成后 DM 向玩家概述**，玩家确认或提出修改。

**确认后执行**：写入 `consequences.md`。

---

### 步骤 13：遭遇表和环境事件

DM 解释：每个地区需要遭遇表（危机钟 + omen + 遭遇池）和环境事件。

**AI 直接生成**（基于已确认的地区和怪物）：
- 每个地区的 `encounter_tables.json` 条目：danger_max、danger_tick、omens（按 max-2 规范）、trigger.blocked_by、pool（含 tags）
- `environment_events.json`：每个地区 2-4 个环境事件

**生成后 DM 展示摘要**，玩家确认。

**确认后执行**：写入 `encounter_tables.json` 和 `environment_events.json`。

---

## Phase 4：验证

### 步骤 14：跨文件一致性检查

**AI 自动执行以下检查**（无需玩家参与）：

**单文件完整性**：
- □ 每个地点有三层信息（sensory/narrative/mechanical）
- □ 每个 NPC 有至少两个认知缺陷维度
- □ 有至少一个不可逆的失败条件
- □ 没有全知 NPC
- □ 所有怪物都绑定了地点
- □ 结局是真实的选择分歧而非好/坏/真结局

**跨文件一致性**：
- □ `world_constants.json` 每个地点在 `encounter_tables.json` 中都有对应条目
- □ `encounter_tables.json` 所有 pool 怪物在 `bestiary.md` 中有定义
- □ 每个 encounter pool 的怪物与该地点的生态环境一致
- □ `origins.md` 每个起源都有 `key` 字段
- □ 所有遭遇池条目使用新格式 `{"id": "...", "weight": N, "tags": [...]}`

**输出验证报告**，列出通过/未通过项。未通过项 DM 决定是否立即修复。

---

### 步骤 15：世界注册完成

```
python tools/world_loader.py switch <key>
```

告知玩家：世界观创建完成。可以通过 `python tools/state_mgr.py --init` 开始角色创建。

---

## 文件产出清单

| 文件 | 产出阶段 | 内容 |
|------|---------|------|
| `world.md` | Phase 1 + 2 | 核心冲突、失败底线、英雄定义、地区、势力、进度钟 |
| `world_constants.json` | Phase 2 + 3 | NPC、地点（含 sensory/mood）、NPC cognition |
| `bestiary.md` | Phase 2 | 怪物生态、威胁类型、叙事钩子 |
| `origins.md` | Phase 2 | 3 个固定起源（含在乎的事物） |
| `items.md` | Phase 3 | 物品分层清单 |
| `encounter_tables.json` | Phase 3 | 每个地区的危机钟 + omen + pool（含 tags + blocked_by） |
| `environment_events.json` | Phase 3 | 每个地区的环境事件 |
| `consequences.md` | Phase 3 | 五类失败代价 |
| `default_state.json` | Phase 3（自动生成） | 初始状态模板（属性系统由世界观决定） |
| `oracle.json` | Phase 3（自动生成） | 神谕表（基于世界观基调生成 6 个条目，每个 3+ variations） |

---

## DM 规范

- 每步严格使用 AskUserQuestion——不跳过玩家确认
- AI 生成的建议内容必须声明"这是 AI 建议，可以修改或重来"
- 每次玩家确认后立即写入文件——不积累到阶段结束
- 步骤 12、13 可以批量生成后概述征求确认，无需逐条
- 如果玩家在任意步骤说"重来"，DM 重新生成该步骤的建议
- 禁止在玩家确认前写入文件
