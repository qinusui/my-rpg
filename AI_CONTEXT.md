# AI Context — my-rpg 引擎架构

这份文档写给其他 AI 编码代理阅读，使其能在不跑团的冷启动状态下理解项目结构、提出修改建议或实现新功能。

## 项目本质

my-rpg 是一个 **AI 充当 DM 的叙事跑团引擎**。没有图形 UI——玩家和 AI 之间通过终端文字、骰子和交互式选项来推进。项目分四层：

```
CLAUDE.md (路由器 — 阶段分发 + 安全约束)
    ↓
rules/engine/*.md (规则文件 — AI 读到什么就执行什么)
    ↓
tools/*.py (命令行工具 — 状态读写、战斗结算、背景切换)
    ↓
engine/*.py (计算模块 — 骰子、判定、叙事提示词组装)
    ↓
rules/{world}/ (世界观数据库 — 引擎不感知世界观，完全抽离)
```

**核心设计原则：引擎与世界观数据完全分离。** 世界观文件夹是"游戏卡带"，通过 `rules/settings.json` 的 `active_world` 字段切换。切换世界观改变所有数据文件，但不触及任何引擎代码。

## 文件地图

### 根目录

| 文件 | 作用 |
|------|------|
| `CLAUDE.md` | AI 操作手册：阶段路由表、安全约束、DM 发挥边界、自我修正协议、动态模块注入规则 |
| `README.md` | 面向人类玩家的项目介绍和快速入门 |
| `config.json` | 用户配置：`engine_mode`、显示开关、叙事风格、生图提供商/API key |
| `config.example.json` | `config.json` 模板 |
| `state.json` | 唯一存档文件：角色、背包、时钟、战斗状态、目标、世界真相、种子分支 |
| `INSTALL.md` | AI 代理可执行的安装步骤 |

### `rules/` — 规则与世界观数据库

```
rules/
├── settings.json              # active_world 指针 + 世界观注册表 + WT 终端配置缓存
├── world_constants.json       # 跨世界共享的 NPC/地点基础数据
├── world_setting.md           # 破碎之冠世界观设定
├── bestiary.md                # 共享怪物数据库
├── items.md                   # 共享物品数据库
│
├── engine/                    # 12 个阶段规则文件（AI 在进入对应阶段时读取）
│   ├── session_init.md        # 会话初始化：engine_mode 判定、世界加载、初始化步骤
│   ├── character_creation.md  # 角色创建：触发检测、逐问题 AskUserQuestion 流程
│   ├── main_loop.md           # 主循环：回合结构、神谕、章节推进、动态模块注入
│   ├── narrative.md           # 叙事输出：沉淀规则、格式约束、隐式描述模式
│   ├── options.md             # 选项设计：AskUserQuestion 格式要求、最多 4 选项、风险优先
│   ├── pipeline.md            # 流水线预查：推测性查询、神谕预掷、种子分支
│   ├── combat.md              # 战斗：触发检测、初始化、每轮流程、阶段推进、清理
│   ├── inventory.md           # 背包交互：触发条件、标签过滤、使用/装备流程
│   ├── goals.md               # 目标系统：誓言选择、目标时钟、终章结算
│   ├── endings.md             # 结局系统：5 条结局路径、死亡 vs 精神崩解判定
│   ├── session_end.md         # 会话结束：--end-session 自动链、手动步骤
│   └── commands.md            # 命令参考：state_mgr.py 全命令速查
│
├── reference/                 # 参考文档
│   ├── world_design_spec.md   # 新世界观设计规范（三条铁律、属性/轨道系统要求）
│   └── knowledge_firewall_examples.md  # NPC 认知偏差示例
│
├── _shared/                   # 跨世界共享资源
│   ├── backgrounds.json       # 共享背景图映射（地点/战斗/情绪/叙事节拍）
│   ├── backgrounds/           # 55 张预制背景图（JPG/PNG）
│   ├── index.json             # 跨世界图片复用索引
│   └── _pending_tasks.json    # 异步生图任务队列（PENDING/RUNNING/DONE/FAILED）
│
├── cloud_chamber/             # 世界观：云室（后启示录废土）
│   ├── rules.md               # 世界专属机制（属性/轨道/白息/枯萎/圣水）
│   ├── world.md               # 背景故事
│   ├── truths.md              # 可发现的真相维度（多可能值 + 锁定效果）
│   ├── origins.md / oaths.md  # 角色出身 / 固定誓言
│   ├── mainline_arc.md        # 四幕叙事协议
│   ├── chronicle_echo_protocol.md    # 历史回响注入
│   ├── npc_persona_protocol.md       # NPC 认知层（知道/误信/隐瞒/不知）
│   ├── bestiary.md / items.md        # 世界专属怪物/物品
│   ├── consequences.md        # 失败代价库
│   ├── *.json                 # 机器可读数据（default_state, encounter_tables, oracle 等）
│   ├── backgrounds.json       # 世界专属背景图注册表
│   ├── backgrounds/           # AI 生成的背景图 + .meta.json
│   └── sessions/              # 会话编年史和导出文件
│
└── shattered_crown/           # 世界观：破碎之冠（暗黑奇幻）
    └── (镜像 cloud_chamber 结构)
```

### `engine/` — Python 计算模块

所有模块被 `tools/state_mgr.py` 导入。不直接访问文件系统（由 tools 层处理 IO）。

| 模块 | 职责 |
|------|------|
| `game_engine.py` | 回合编排器：串联环境、D20、NPC、叙事、誓言、编年史 |
| `state.py` | 状态读写（原子写入）、钟表运算、属性修正、标记加成、阈值旗标 |
| `dice.py` | D20/D6 投骰、骰子字符串解析、神谕表生成 (`generate_oracle`, `get_next_oracle`) |
| `combat.py` | 战斗机制：伤害轨道管理、效果施加、环境事件、阶段推进 |
| `narrator.py` | 构建 `narrator_prompt` 字符串：动作 + 骰子 + 环境 + 誓言 + 编年史提示 |
| `judge.py` | 结果判定：D20 vs DC → 五档结果（大失败~大成功），确定后果类别 |
| `vow.py` | 目标定义查询、誓言状态检查 |
| `chronicle.py` | 编年史读写：传说、遗物、势力变化、结局。地点提示提取 |
| `npc.py` | NPC 认知系统：世界常量 + 会话富化叠加、好感度管理 |
| `environment.py` | 环境事件：白息等级检测、战斗环境事件生成（15%/回合，从世界 `environment_events.json`） |
| `fallback.py` | 优雅降级：`resolve_missing_location`、`resolve_missing_npc`、`resolve_rule_gap` |
| `__init__.py` | 公共 API：导出 `run_turn` 等高阶函数 |

### `tools/` — CLI 工具

每个工具是独立的 Python 脚本，AI 在游戏过程中通过 Bash 调用。所有输出为 JSON。

| 工具 | 主要命令 | 用途 |
|------|----------|------|
| `state_mgr.py` | `--init`, `--view`, `--action`, `--d20`, `--tick`, `--oracle`, 背包 CRUD, 钟表更新, NPC/地点查询, 线索/历史管理, 目标生命周期, 真相锁定, 战斗清理, 种子分支 | **游戏状态总控中心** |
| `bg.py` | `--init`, `--set`, `--combat`, `--mood`, `--reset`, `--submit`, `--poll`, `--skip`, `--pin`, `--export`, `--import` | 终端背景切换 + AI 图像生成 |
| `combat.py` | `--init`, `--round_event`, `--tick_constitution`, `--clear_encounter` | 战斗状态追踪 |
| `session_enrich.py` | `--snapshot`, `--report`, `--export-session`, `--chronicle`, `--end-session` | 会话生命周期管理 |
| `world_loader.py` | `list`, `switch`, `world_file()` | 世界观卡带管理 |
| `box.py` | stdin TSV → 对齐表格 | CJK 等宽表格格式化 |
| `config_loader.py` | `load_config()` | 配置读取（1 秒 mtime 缓存） |

`bg.py` 的生图部分通过 `tools/image_gen/` 下的提供商系统实现：`base.py`（抽象基类）、`wanx.py`（阿里百炼 wanx-v1）、`__init__.py`（工厂函数 `get_generator()`）。

### `tests/`

| 文件 | 覆盖 |
|------|------|
| `test_config_loader_cache.py` | 配置缓存命中 + mtime 触发的重载 |
| `test_session_export_schema.py` | 导出 JSON 格式验证 |
| `test_wanx_api_key_resolution.py` | API key 优先级链 |

`docs/` 下有更多扩展文档，涵盖 D20 判定、钟表系统、战斗、代价框架、目标、结局、悲剧、叙事输出、NPC 关系、知识防火墙、背景系统和生图提供商规范。

## 一回合的完整数据流

```
1. AI 读取 CLAUDE.md → 路由到 rules/engine/main_loop.md
2. AI 执行: python tools/state_mgr.py --view       # 读状态
3. AI 生成叙事 (遵循 rules/engine/narrative.md)
4. AI 弹出 AskUserQuestion 选项 (遵循 rules/engine/options.md)
5. 玩家选择
6. AI 执行: python tools/state_mgr.py --action --attr <属性>
   └─ 内部 engine/game_engine.py 串联:
      ├─ environment.py: 环境事件检测
      ├─ dice.py: D20 投骰 + 神谕
      ├─ judge.py: 结果 vs DC 判定
      ├─ combat.py: 若战斗中则施加效果
      ├─ vow.py: 检查誓言状态
      ├─ chronicle.py: 提取编年史提示
      └─ narrator.py: 构建 narrator_prompt
7. AI 处理 --action 输出，生成下一段叙事
8. 回到步骤 2
```

进入战斗时插入 `combat.md` 的阶段流程（combat.py --init → 循环 → clear_encounter → bg.py --set）。触发目标系统时插入 `goals.md` 的誓言流程。章节推进时检视 `mainline_arc.md`。

## 双引擎模式

`config.json` → `engine_mode`：

| 模式 | DM 读取 | DM 不读 | 判定来源 |
|------|--------|---------|---------|
| `manual`（默认） | 全部机制规则文件 | — | DM 从原始数据独立判定 |
| `auto` | 仅世界 rules.md + chronicle + config | 机制规则文件 | 引擎输出的 `narrator_prompt` 字段 |

auto 模式下引擎预计算 DC、后果和禁用措辞，DM 只需将 `narrator_prompt` 翻译为叙事语言。

## 修改时必须遵守的约束

1. **引擎/世界观分离** — 引擎代码不导入世界专属模块。世界数据只在 `rules/{world}/` 下。
2. **世界持久化** — 后果立即写入世界文件，不在会话结束时才落盘。
3. **知识防火墙** — NPC 有多层认知（knows / believes_wrongly / conceals / unaware_of），DM 必须忠实维护。
4. **失败不可逆** — 没有重试循环。失败留下伤疤。死亡角色成为遗物/NPC。精神崩解的角色成为 NPC。
5. **禁止替玩家决定内心** — DM 不能决定玩家的感受、判断、信念。
6. **安全** — 禁止 `rm`/`del` 命令；禁止写 `my-rpg/` 外的文件（`bg.py` 修改 WT `settings.json` 的背景字段除外）；禁止网络访问（图像生成 API 除外）。
7. **状态单文件** — `state.json` 是唯一存档。所有工具从它读，所有工具向它写。

## 扩展指南

### 新增世界观

1. 读 `rules/reference/world_design_spec.md`
2. 创建 `rules/{world_key}/`，包含 `rules.md`、`world.md`、`bestiary.md`、`items.md`、`default_state.json` 和 JSON 数据文件
3. 在 `rules/settings.json` → `worlds` 中注册
4. `python tools/world_loader.py switch {world_key} --init`

### 新增机制（如制造、派系声望）

1. 在 `engine/` 中新增计算模块
2. 在 `tools/state_mgr.py` 中新增 CLI 子命令
3. 在 `rules/engine/` 中新增阶段指令文件
4. 更新 `CLAUDE.md` 阶段路由表
5. 如需世界专属数据，在各世界文件夹中新增对应文件
6. 在 `tests/` 中新增测试

### 新增生图提供商

1. 创建 `tools/image_gen/{provider}.py`，实现 `base.py` 中的 `ImageGenerator` 抽象类
2. 在 `config.example.json` 中添加提供商配置
3. `__init__.py` 的工厂函数按文件名自动发现

### 新增 CLI 工具

1. 创建 `tools/{tool}.py`，使用 argparse，输出 JSON
2. 若涉及 `my-rpg/` 外的文件操作，在 `CLAUDE.md` 安全约束中新增例外
3. 在 `rules/engine/commands.md` 中记录

## 背景图系统

两层：

**静态切换** — `bg.py --set/--combat/--mood` 修改 Windows Terminal 背景图。使用 `rules/_shared/backgrounds/` 下的 55 张预制 JPG。不需要 API key。

**AI 生成** — `bg.py --submit` 将 prompt 发送到 wanx-v1。异步模式：立即返回 task_id，`_auto_poll()` 在每次 `--set`/`--combat` 前透明检查已完成任务。若 `config.json` 中 `auto_generate` 开启，缺失的怪物专属图和地点图会在首次遇到时自动提交生成。生成的图片缓存在 `rules/{world}/backgrounds/` 并索引到 `rules/_shared/index.json` 供跨世界复用。

## 叙事沉淀

DM 即兴编造的细节，满足以下任一条件时写入世界文件：
- 玩家主动询问过该细节
- NPC 明确说出了该事实
- 玩家行动造成了物理改变
- 事件影响了势力关系

写入格式：`[来源：session_{YYYYMMDD}]` 标注在 `world_constants.json` 或世界 `.md` 文件的条目中。

## state.json 主要字段

| 字段 | 内容 |
|------|------|
| `clocks` | 所有属性/轨道钟表: `{max, filled, direction, modifier}` |
| `attr_order` / `track_order` | 显示排序 |
| `combat_damage_attr` | 战斗伤害作用于哪个轨道（世界观决定） |
| `inventory` | 物品列表: `[{id, name, qty, tags}]` |
| `combat_state` | 活跃战斗数据: `{enemies, effects, environment, round, log}` |
| `active_goal` | 当前誓言/目标及时钟 |
| `completed_goals` | 已完成目标列表 |
| `chapter` / `turn_count` | 进度计数器 |
| `player_name` / `origin` / `current_location` | 角色基本信息 |
| `world_truths` | 已锁定的真相维度及值 |
| `marks` | 角色印记: `[{name, bonus, context}]` |
| `tags` / `injury` / `affinities` | 角色状态标签 |
| `clues` / `history` / `events` | 会话叙事元数据 |
| `future_seeds` | 预分支选项详情 (sensory/npc/risk) |
| `dm_log` | DM 覆盖记录 |
| `pending_encounter` | 待触发的遭遇 |
| `_next_oracle` | 预掷的神谕值 |
| `_last_enrichment` / `_enrichment_turn` | 会话富化追踪 |
