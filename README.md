# My RPG

一个运行在 Claude Code 中的模块化 RPG 引擎。世界观与引擎分离——换世界如换游戏卡带。

## 前置条件

- [Claude Code](https://claude.ai/code)（AI 对话终端）
- [Python 3.10+](https://www.python.org/)（游戏逻辑）
- Python 依赖：`pip install Pillow`

## 快速开始

```bash
# 1. 初始化游戏状态
python tools/state_mgr.py --init

# 2. 启动 Claude Code（在项目根目录）
claude

# 3. 在 Claude Code 中直接开始游玩
#    DM 会自动读取状态并推进剧情
```

## 游戏机制简介

### 对话式叙事

与普通 RPG 不同，这里没有图形界面——一切通过**文字叙事**进行。DM（Claude Code）描述场景，你通过选项回应。每次行动都会推进时间，遭遇怪物、发现物品、触发事件都由幕后系统驱动。

### 属性与检定

角色有 5 项属性：生命、理智、财富、声望、魔力。关键行动使用 D20 检定（1=大失败，20=大成功），DC 从 10（简单）到 20（困难）不等。属性阈值会解锁或限制可选行动。

### 战斗

遭遇怪物后进入回合制战斗。攻击、使用物品、逃跑、对话——每个选择都有后果。战斗系统自动结算命中与伤害，DM 将其翻译为叙事。

### 叙事分块

长篇剧情自动切分为叙事节拍点，段落间隙 DM 执行后台预计算（世界常数查表、预掷骰子），阅读无需等待。

### 叙事预演

展示选项前，DM 为每个分支预先锁定细节（感官、NPC 状态、潜在风险）。无论你选哪个方向，细节都是"早已注定"的，杜绝临时编造。

### 场景背景图（Windows Terminal）

在 Windows Terminal 中运行时，终端背景图会跟随游戏场景自动切换。进入城市、踏入地牢、触发战斗——背景氛围随之改变。

**首次使用**（只需执行一次）：

```bash
python tools/bg_switcher.py --init
```

`--init` 自动检测 Windows Terminal 的 `settings.json` 路径和当前 profile GUID，缓存到 `rules/settings.json`。后续会话自动读取，无需重复初始化。

**自动生成背景图（百炼 wanx-v1）**：

引擎可在游戏过程中自动为每个新场景生成专属背景——无需手动找图、改图、改名。

1. 在[阿里云百炼控制台](https://bailian.console.aliyun.com/) 开通 wanx-v1 服务，获取 API Key
2. 将 Key 写入 `config.json` 的 `services.dashscope_api_key` 字段
3. 安装依赖：`pip install dashscope`

配置完成后，DM 每次进入新地点时自动提交生成任务，图片就位后自动切换。生成过的场景永久缓存于 `rules/{active_world}/backgrounds/`——同一地点不会重复生成。

```bash
# 手动提交（通常由 DM 自动完成）
python tools/bg_generator.py --submit freeport_docks --prompt "暮色中的港口码头，雾气从水面升起，桅杆林立的剪影..."

# 战斗图 / Boss 图（--style 预设：scene 地点 | combat 敌人 | boss 首领）
python tools/bg_generator.py --submit combat_goblin_scout --prompt "哥布林侦察兵，绿色皮肤，手持短弓..." --style combat
python tools/bg_generator.py --submit combat_shadow_stalker --prompt "暗影追猎者，半透明雾状身躯..." --style boss

# 收拢已完成的图片
python tools/bg_generator.py --poll
```

**手动替换背景图片**：

1. 打开 `rules/{active_world}/backgrounds/` 目录
2. 查看 `backgrounds.json` 了解每个场景对应的文件名
3. 用你自己的图片（照片、概念艺术、截图）替换对应文件，保持文件名一致即可
4. 引擎无需修改——下次切换场景时自动生效

**通用共享背景图**：`rules/_shared/backgrounds/` 中的图片对所有世界观生效。新世界上传后无需配置即可使用下列通用场景键名：

| 场景键 | 对应画面 |
|--------|---------|
| `city` | 城市街景 |
| `tavern` | 酒馆 |
| `market` | 市场 |
| `docks` | 港口码头 |
| `forest` | 密林 |
| `mountain` | 山城要塞 |
| `cave` | 矿洞/地城 |
| `wasteland` | 荒原 |

也可替换共享目录中的图片——所有世界同步更新。各世界在专属 `backgrounds.json` 中用相同 key 即可覆盖共享配置。

**可用命令**：

```bash
# 切换背景到指定场景
python tools/bg_switcher.py --set freeport_city

# 战斗背景
python tools/bg_switcher.py --combat                    # 普通战斗（通用图）
python tools/bg_switcher.py --combat boss               # Boss 战（通用图）
python tools/bg_switcher.py --combat --monster goblin   # 查专属战斗图（命中则用，未命中回退）

# 调整透明度（0.05~1.0）
python tools/bg_switcher.py --opacity 0.35

# 情绪预设（透明度随叙事氛围变化）
python tools/bg_switcher.py --mood danger

# 查看当前背景状态
python tools/bg_switcher.py --status

# 恢复默认（无背景图）
python tools/bg_switcher.py --reset

# 异步生成背景图（--style: scene 地点 | combat 敌人 | boss 首领，默认 scene）
python tools/bg_generator.py --submit <scene_id> --prompt "中文提示词" [--style combat|boss]
python tools/bg_generator.py --poll
python tools/bg_generator.py --status
```

**情绪预设对照**：

| 预设 | 透明度 | 适用场景 |
|------|--------|---------|
| `safe` | 0.20 | 据点、安全屋——背景退后，文字主导 |
| `normal` | 0.30 | 正常探索（默认值） |
| `tension` | 0.40 | 追踪、潜入、对峙——紧张逼近 |
| `danger` | 0.45 | 战斗、陷阱、濒死——高存在感 |
| `tragedy` | 0.15 | NPC 死亡、大失败、世界崩解——褪色感 |

**自定义背景图范围**：在 `config.json` 中可精细控制哪些场景使用背景图：

```json
"display": {
  "background_image": {
    "enabled": true,        // 总开关，设为 false 完全关闭
    "locations": true,      // 地点背景图
    "combat": true,         // 战斗 / Boss 背景图
    "moods": true,          // 情绪预设（透明度变化）
    "auto_generate": true   // 自动提交百炼 wanx-v1 生图任务
  }
}
```

也可直接设为 `false`（布尔值）完全关闭所有功能。

**会话结束时**：DM 自动执行 `python tools/bg_switcher.py --reset` 恢复终端默认背景，不会把游戏画面留在你的终端上。

## 切换世界观

本引擎支持即插即用的世界模块。上传新世界只需三步：

```bash
# 1. 注册
python tools/world_loader.py register cyber_wasteland 赛博荒原 rules/cyber_wasteland

# 2. 切换
python tools/world_loader.py switch cyber_wasteland

# 3. 重置
python tools/state_mgr.py --init
```

查看可用世界观：

```bash
python tools/world_loader.py list
```

### 世界观文件结构

```
rules/cyber_wasteland/
├── world.md               # 背景、地图、因果链
├── bestiary.md            # 怪物/NPC 图鉴（叙事）
├── bestiary.json          # 怪物数据（战斗引擎消费）
├── items.md               # 物品库（叙事）
├── items.json             # 物品数据（武器/防具/消耗品）
├── world_constants.json   # NPC 特征与地点感官细节
├── encounter_tables.json  # 遭遇概率表
├── environment_events.json# 环境事件表
├── threshold_rules.json   # 属性阈值规则
└── default_state.json     # 初始状态模板
```

## 工具速览

| 命令 | 用途 |
|------|------|
| `python tools/state_mgr.py --view` | 查看当前角色状态 |
| `python tools/state_mgr.py --tick` | 推进回合（触发遭遇/D20大失败大成功/满格时钟） |
| `python tools/state_mgr.py --d20 [--attr health] [--mod N]` | D20 检定（属性修正 + DM 局势修正） |
| `python tools/state_mgr.py --set_injury <type>` | 设置伤残状态（含持续 tick 和 DC 惩罚） |
| `python tools/state_mgr.py --heal` | 支付代价治愈伤残 |
| `python tools/state_mgr.py --create_clock "名称" --clock_max 6` | 创建进度钟 |
| `python tools/state_mgr.py --tick_clock "名称"` | 推进进度钟 1 格 |
| `python tools/state_mgr.py --update health -3` | 修改属性 |
| `python tools/state_mgr.py --add_item "物品名" --tags weapon` | 获得物品 |
| `python tools/state_mgr.py --list_inventory` | 查看背包 |
| `python tools/combat.py --init goblin --count 3` | 初始化战斗 |
| `python tools/combat.py --attacker player --target goblin_1 --action attack` | 玩家攻击 |
| `python tools/bg_switcher.py --init` | 初始化终端背景图（首次使用，自动检测 WT 配置） |
| `python tools/bg_switcher.py --set <scene>` | 切换背景到指定场景 |
| `python tools/bg_switcher.py --combat [boss] [--monster <key>]` | 切换战斗背景（支持怪物专属图） |
| `python tools/bg_switcher.py --reset` | 恢复终端默认背景 |
| `python tools/bg_generator.py --submit <scene> --prompt "..." [--style combat|boss]` | 异步提交背景图生成（百炼 wanx-v1） |
| `python tools/bg_generator.py --poll` | 收拢已完成图片并写入世界配置 |
| `python tools/world_loader.py switch <world>` | 切换世界观 |
| `python tools/world_loader.py list` | 列出可用世界观 |
| `python tools/session_enrich.py --snapshot` | 保存会话开始快照（每轮游戏开始时执行） |
| `python tools/session_enrich.py --report` | 查看会话富化报告与本次增量 |
| `python tools/session_enrich.py --archive` | 归档旧线索/历史（保留最近+伤疤） |
| `python tools/session_enrich.py --export-session "名称"` | 导出会话叙事存档 |

## 世界缔造机制 —— 亲手打造你的艾瑟兰

这是引擎的核心设计哲学：**每次游玩都是一次世界缔造**。

每当你扮演角色完成一场冒险，你创造的 NPC、发现的地点、做出的抉择，都会被固化到世界观文件中。下次游玩时——无论是你自己还是别人——这个世界已经因为你的行动而不同了。

### 自动沉淀

DM（Claude Code）会在会话结束时自动运行 `session_enrich.py`，将本次游玩数据与世界观文件同步。你不需要做任何额外操作。

### 你沉淀了什么

| 你的行动         | 固化为                                         |
| ------------ | ------------------------------------------- |
| 在酒馆遇到一个新 NPC | NPC 特征写入 `world_constants.json`             |
| 第一次踏入一个地方    | 地点感官细节写入 `world_constants.json`             |
| 遇到一种没见过的怪物   | 怪物数据写入 `bestiary.json` + 叙事写入 `bestiary.md` |
| 获得一件独特的物品    | 物品属性写入 `items.json` + `items.md`            |
| 发现一个世界真相     | 背景故事更新 `world.md`                           |
| 做出了改变世界格局的决定 | 结局路线、势力版图永久写入世界文件                           |
| 用非战斗方式解决了怪物  | "可非战斗解决"特性写入图鉴（未来 DM 会读到）                   |

### 世界文件 = 会生长的卡带

每次游玩后，`rules/{world}/` 下的文件会越来越丰富。三五个玩家各自扮演不同角色、各自做出不同选择后，你得到的世界观文件是独一无二的——**它是你的玩家群体亲手缔造的历史**。

如果要分享你的世界，只需打包 `rules/{world}/` 文件夹。另一个人放入 `rules/`，执行 `python tools/world_loader.py register`，就能在你缔造的世界中继续冒险——所有你创造的 NPC、地点、物品都在那里等着。

## 项目结构

```
my-rpg/
├── CLAUDE.md              # DM 核心引擎指令
├── state.json             # 游戏存档
├── config.json            # 玩家配置（显示/叙事偏好）
├── rules/
│   ├── settings.json      # 活跃世界观指针 + WT 背景缓存
│   ├── _shared/           # 共享背景图（所有世界通用）
│   ├── reference/         # 引擎参考文档（扩展示例）
│   └── shattered_crown/   # ← 默认世界观
│       ├── backgrounds.json    # 场景→背景图映射
│       ├── backgrounds/        # 背景图片目录
│       └── ...
└── tools/
    ├── state_mgr.py        # 状态管理
    ├── combat.py           # 战斗引擎
    ├── world_loader.py     # 世界观管理器
    ├── session_enrich.py   # 会话富化——叙事沉淀回世界
    ├── bg_switcher.py      # Windows Terminal 背景图切换
    ├── bg_generator.py    # 百炼 wanx-v1 背景图自动生成
    └── box.py             # 表格对齐工具
```
