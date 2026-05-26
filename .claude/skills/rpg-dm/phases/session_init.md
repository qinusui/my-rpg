# 会话初始化

## 引擎模式

读取 `config.json` 的 `engine_mode`（默认 `manual`）：

### auto —— 引擎判定结论驱动

DM 不读机械规则文件，只读引擎的结构化输出 + 世界数据文件。

**会话初始化（auto）**：
- 跳过 `docs/core/rules_index.md`
- 跳过 `docs/d20.md`、`docs/tick_system.md`、`docs/consequences.md`、`docs/clocks.md`、`docs/combat.md`、`docs/goals.md`
- 正常读取：`rules/{active_world}/rules.md`（世界专属机制）、`config.json`、chronicle

**每轮流程（auto）**：
1. `--action` / `--tick` 输出的 `engine_narrator_context.narrator_prompt` 为判定结论
2. DM 直接翻译 `narrator_prompt` 成叙事——不再手工查 DC 表或代价库
3. `engine_narrator_context.judgment` 已包含成败等级、代价类别、禁止句式
4. 引擎未覆盖的判定（复杂社交后果、NPC 之间的非玩家行动）DM 可自由发挥

**失败处理（auto）**：
- `judgment.consequence_categories` 列出匹配失败等级的代价方向
- DM 选最自然的一项执行 → `state_mgr.py` 更新状态 → 叙事体现
- 无需翻阅 `consequences.md`

### manual —— DM 独立判定

当前行为，不变。DM 读取全部规则文件，引擎输出仅作辅助参考。

**会话初始化（manual）**：
- 读取 `docs/core/rules_index.md`
- 读取全部 `docs/` 规则文件
- DM 依据规则书独立做机械判定

### 切换

修改 `config.json` → `engine_mode` 为 `"auto"` 或 `"manual"`，下次会话生效。不影响 `state.json` 存档。

## 世界观（模块化，即插即用）

引擎与世界观数据完全分离。`CLAUDE.md` 是通用游戏控制台，`rules/` 下的文件夹是游戏卡带。

**启动协议**：

1. 确认 `rules/settings.json` 中的 `active_world` 指向正确的世界观
2. 世界观文件均位于 `rules/{active_world}/` 目录下
3. 所有工具（combat.py、state_mgr.py 等）自动从活跃世界观的 JSON 文件读取数据

**游戏规则**：

- 遭遇怪物时，grep `rules/{active_world}/bestiary.md` 定位目标怪物条目（禁止读全文）
- 获得物品时，grep `rules/{active_world}/items.md` 定位目标物品条目（禁止读全文）
- 未收录的怪物/物品可即兴创建，但必须追加到活跃世界观的对应文件中
- 新 NPC/地点通过 `--add_npc` 写入活跃世界观的 `world_constants.json`

**切换已有世界观**：

```
python tools/world_loader.py list                     # 查看可用世界观
python tools/world_loader.py switch <key>
python tools/state_mgr.py --init                     # 重置游戏状态
```

**创建新世界观**：当用户表示想在其他设定下跑团时，DM 读取 `rules/reference/world_design_spec.md`，基于用户的一句话描述生成完整世界观文件包。生成流程在该文档 §5 中定义。生成完成后执行注册+切换即可开始。

## 会话初始化流程

开始游戏时，DM 必须按序执行：

```
python tools/session_enrich.py --snapshot   # 1. 存快照，会话结束时自动 diff
```

然后读取核心规则索引与世界覆写：

```
必须读取 docs/core/rules_index.md           # 2. 核心规则入口与边界
必须读取 rules/{active_world}/rules.md       # 3. 世界覆写：属性映射、专属机制、叙事差异
```

然后读取 `config.json`，将以下值载入当前会话：

| 字段 | 默认值 | 作用 |
|------|--------|------|
| `display.background_image` | `true` | 终端背景图总控——设 `false` 完全关闭，或展开为对象细控子项 |
| `display.background_image.enabled` | `true` | 总开关 |
| `display.background_image.locations` | `true` | `false` 时地点切换不改变背景 |
| `display.background_image.combat` | `true` | `false` 时战斗不改变背景 |
| `display.background_image.moods` | `true` | `false` 时情绪预设不生效 |
| `display.background_image.auto_generate` | `true` | `false` 时不自动提交生图任务 |
| `narrative.implicit_description` | `true` | `false` 时 DM 可自由使用数值和游戏术语 |

后续所有规则以 config.json 的值为准。文件缺失或字段缺失时使用上表默认值。

然后读取 chronicle：

```
python tools/session_enrich.py --chronicle view
```

读取后必须先执行一次"回声筛选"（见下方"回声压力协议"），选出本局前 2-3 场会激活的历史回声，再写开场。

然后渲染开场背景（若 `display.background_image.enabled` 不为 `false`）：

```
python tools/bg.py --init                          # 首次需初始化（仅需一次）
python tools/bg.py --set <current_location>        # 开场即渲染当前位置背景
```

若 `--init` 失败（未检测到 Windows Terminal 配置），DM 必须通过 AskUserQuestion 引导玩家完成设置：询问终端类型、配置文件路径、目标 Profile 名称或 GUID，然后用 `--init <guid>` 重试。

首次初始化完成后，DM 使用 AskUserQuestion 询问玩家偏好：
- 终端背景不透明度（默认 0.3，可建议 0.2-0.5）
- 是否需要自动生图（`auto_generate` 开关）
- 是否完全关闭背景图（纯文字模式）

以上询问仅在 `--init` 首次成功后执行一次，后续会话跳过。<!-- 修正：移除 new_player_defer_auto_generate 新手保护，改为 --init 时主动询问偏好 -->

## 历史影响协议

chronicle 是跨会话的**世界记忆层**——不仅是日志，它主动参与叙事生成。

### 核心原则

世界记得发生过的事，但不认识你。影响必须是间接的、模糊的：

```
❌ 上一局玩家救了Maren，这一局Maren记得你
✅ 这一局有个老人说"上个旱季有个外乡人在祭坛附近救了人"
```

### DM 处理规则

| 类型 | 融入方式 |
|------|---------|
| **relics** | 对应地点的感官描写中自然融入。`permanent:true` 的遗迹每次必现 |
| **legends** | 根据 `spread` 决定哪些 NPC 知道——`low` 只有特定圈子听说过；`medium` 大多数人听过但版本各异；`high` 人尽皆知 |
| **faction_shifts** | 影响对应势力 NPC 的认知和行为，`reason` 字段 DM 知道但玩家需自己发现 |
| **endings** | 世界状态的背景底色，不主动提及，除非玩家行动触碰到相关内容 |
| **broken** | 崩解的前玩家角色——以 NPC 形态存在于世界中。玩家不知道他的过去，DM 以碎片感官描写暗示 |

### 禁止

- 禁止任何 NPC 直接说出"上一个冒险者做了什么"——只能说"听说"、"传说"
- 禁止 chronicle 内容成为解谜的钥匙——它增加厚度，不提供答案
- 禁止精确复现上一局的细节——每个版本都有偏差
- 禁止让崩解角色说出自己的过去——他/她已记不得自己是谁

### 回声压力协议（Accumulation Without Resolution）

目标：历史让世界变厚，不让世界被单局"解完"。

#### 回声加权（用于选择，不用于宣布真相）

对每条候选 chronicle 条目按四项打分后排序：
- 近期性：最近两局 +2，其余 +1
- 相关性：与本局开场地点/势力直接相关 +2，间接相关 +1
- 持久性：`relic.permanent=true` +2，`broken` +1
- 张力性：会制造分歧、摩擦、误传、代价 +1

> 分数只决定"本局先用谁"，不决定"谁是真的"。

#### 激活上限（防 lore dump）

每局开场前 2-3 场，历史回声激活总量建议 3-4 条：
- `endings` 最多 1 条
- `faction_shifts` 最多 1 条
- `broken` 最多 1 条
- `relics` 最多 2 条（含 `permanent`）
- `legends` 最多 1 组（可包含互相冲突的两个版本）

#### 压力分层（只加压，不给答案）

- 轻压：地点多一层痕迹、NPC 语气更谨慎
- 中压：配给/通行/信任出现摩擦
- 高压：势力动作前置、关系代价提前显形

硬约束：
- `endings` 只能改"世界底色与姿态"，不能给"唯一真相"
- 任何历史回声都不能永久解除核心威胁
- 历史互相冲突时必须允许并存，不做场外裁定
