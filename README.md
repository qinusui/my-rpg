# my-rpg

> 以 Claude Code 为宿主的多世界观沉浸式单人跑团引擎。没有图形界面——只有文字、骰子，和你的选择。

## 可用世界观

| 世界观 | 类型 | 简介 |
|--------|------|------|
| **云室**（默认） | 后启示录废土 | 白息笼罩的荒原、旧世界的锈蚀废墟、乙醇雾中扭曲的变异生物。你在干岸定居点的祭坛区醒来——圣水的库存正在缓慢减少，禁地深处有某种规律性的冷白闪光。 |
| **破碎之冠** | 暗黑奇幻 | 艾瑟兰大陆，八片王冠碎片散落各处。龙神的低语在暗中侵蚀理智，封印正在崩解。传统的中世纪奇幻设定，有城堡、森林、港口城市。 |

云室使用**四属性 + 三轨道 + 印记**系统，破碎之冠使用**七属性钟**系统。引擎的核心规则通用，世界观通过各自覆写层提供差异化机制与叙事。

## 和传统跑团有什么不同

**你不需要当 DM。** Claude Code 就是你的 DM——它描述场景、扮演 NPC、结算战斗、推进剧情。你只需要扮演你的角色。

**你的选择真的在改变世界。** 每次游玩结束时，你创造的 NPC、发现的地点、做出的抉择，都会被固化到世界文件中。下次打开——世界已经不同了。三五次冒险之后，你得到的世界是独一无二的，由你的选择亲手缔造。

**没有"读剧本"的负担。** 传统跑团需要有人提前准备模组、读规则书、安排遭遇。这里一切都是即兴的——DM 根据你的行动实时生成剧情，同时被规则引擎约束，不会放飞。

**终端即场景。** 在 Windows Terminal 中运行时可启用场景背景增强；初始化与自动生图细节见下方“可选增强”。

## 快速开始

把下面这段话发给 Claude Code：

> 请参考 https://raw.githubusercontent.com/qinusui/my-rpg/main/INSTALL.md
> 帮我安装 my-rpg，默认使用云室世界观，并用中文向我介绍如何开始第一局游戏。

Agent 会自动完成安装、配置环境、初始化存档。通常你只需确认授权并按提示继续；若要手动执行步骤，请参考 `INSTALL.md`。

> 也可以把这段话发给其他 AI 编码 Agent（Gemini CLI、Cursor 等），流程一致。

## 你需要知道的事

**这是一款叙事跑团，不是刷怪游戏。** 没有经验值、没有等级、没有最优解。你的角色会受伤、会失败、会被世界改变。失败不是惩罚——是故事的一部分。

**你只需要扮演你的角色。** 当你面对选择时，弹出的是交互式选项菜单——点击即可。你也可以随时输入自己的行动，DM 会理解并响应。

**D20 决定关键成败。** 当你尝试冒险行动时，DM 会掷一个 D20。1 = 大失败，20 = 大成功。难度从 12（简单）到 22（极难）。你的属性和印记会影响修正值。

**战斗是回合制的。** 遭遇怪物后进入战斗——攻击、使用物品、逃跑、对话，每个选择都有后果。战斗系统自动结算，DM 把结果翻译成叙事。

**长篇剧情会自然停顿。** 场景切换、真相揭示、情感峰值后，DM 会停下来让你消化，同时展示"继续"或"稍作停留"的选择。你不会被信息淹没。

## 可选增强

### Windows Terminal 场景背景

在 Windows Terminal 中游玩时，终端背景图自动跟随场景切换。首次使用只需执行一次：

```bash
python tools/bg.py --init
```

### AI 自动生成背景图

引擎可以在游戏过程中为每个新场景自动生成专属背景——不需要手动画图、找图、改名：

1. 在[阿里云百炼控制台](https://bailian.console.aliyun.com/)开通 wanx-v1，获取 API Key
2. 推荐设置环境变量 `DASHSCOPE_API_KEY`（兼容 `config.json` 的 `image_gen.providers.wanx.api_key` 与 `services.dashscope_api_key`）
3. `pip install dashscope`

生成是异步的——玩到的时候图片可能已经就位了。生成过的场景永久缓存，不会重复消耗 API。若你只想纯文字游玩，可在 `config.json` 里关闭 `display.background_image`。

**玩家间分享背景图**：引擎内置了导出/导入工具，方便玩家之间交换生成的背景图：

```bash
python tools/bg.py --export --filter-world cloud_chamber   # 导出云室所有图
python tools/bg.py --export --filter-tag "森林"            # 按标签筛选
python tools/bg.py --import "path/to/share.zip"            # 导入，自动 SHA256 去重
```

导出包是标准 zip，内含 `manifest.json`（prompt、tags、来源世界观等元数据）+ 所有图片。接收方导入后新图直接加入共享库，已有图片自动跳过。

### 切换世界观

```bash
python .claude/skills/rpg-dm/scripts/tools/world_loader.py list       # 查看可用世界
python .claude/skills/rpg-dm/scripts/tools/world_loader.py switch <key>   # 切换
python tools/state_mgr.py --init                                       # 重置游戏状态
```

> 也可简写为 `python -m scripts.tools.world_loader`（需从项目根目录运行）。

### 架构速览

```
my-rpg/
├── rules/                        # 世界观数据（地点、NPC、遭遇表等）
│   ├── shattered_crown/          # 破碎之冠
│   └── cloud_chamber/            # 云室
├── state.json                    # 当前会话状态
├── config.json                   # 引擎配置（图像生成、叙事风格等）
├── tools/                        # CLI 工具（wrapper 代理到新位置）
│   ├── state_mgr.py              # 状态视图 / 行动执行
│   ├── combat.py                 # 战斗初始化
│   └── bg.py                     # 背景图管理
└── .claude/skills/rpg-dm/        # 引擎核心（DM 行为规范 + 逻辑）
    ├── SKILL.md                  # DM 路由器 & 行为约束
    ├── phases/                   # 阶段规则文件（combat, goals, narrative 等）
    └── scripts/
        ├── engine/               # 核心运行时
        │   ├── trigger.py        # 统一入口：bg切换 + 遭遇管线
        │   ├── game_engine.py    # 回合调度 & D20 判定
        │   ├── narrator.py       # 叙事输出构建
        │   └── state.py          # 状态读写
        └── tools/                # 内部工具（world_loader, bg.py 本体等）
```

**关键设计决策**：
- `.claude/skills/rpg-dm/` 是版本控制的，包含引擎所有代码和 DM 行为规范
- `tools/*.py` 是代理脚本，保持与旧命令行兼容
- 引擎输出格式向后兼容，外部集成无需修改

### 创建新世界观

想在其他设定下跑团？直接告诉 Claude：

> "我想在 1920s 克苏鲁背景下跑，主角是私家侦探"

Claude 会读取设计规范，生成完整的世界观文件包，注册后直接开始游戏。

## 游玩成本

一次典型 session（20-30 回合，探索 3-5 个场景）的成本：

| 项目 | 模型 | 费用 |
|------|------|------|
| LLM API | DeepSeek-V3 | **¥0.15-0.30** |
| LLM API | Claude Sonnet 4 | **$0.50-1.00** |
| LLM API | Claude Opus 4 | **$2.50-4.00** |
| 图像生成 | wanx-v1（5 张） | **¥0.80**（新用户 500 张免费） |

**用 DeepSeek 跑团，图像靠免费额度时，一次不到 ¥0.30——几分钱人民币。** 即使免费额度耗尽，图像部分约 ¥0.80，整局不到 ¥1.00。

> 你用的是 Claude Code，但 Claude Code 底层模型可以切换。DeepSeek 以 1/10 的价格提供接近 Sonnet 的体验，是目前性价比最高的选择。

## 配置

| 配置项 | 默认值 | 作用 |
|--------|--------|------|
| `display.background_image` | `true` | 终端背景图总开关 |
| `display.title_bar` | `true` | 标题栏显示角色信息 |
| `narrative.implicit_description` | `true` | 叙事语言代替游戏术语 |
| `narrative.style` | `"epic"` | 叙事风格（epic/noir_urban/hardboiled/brutal） |

## 世界缔造

每次冒险结束时，DM 会自动将你的旅程沉淀到世界文件中。你创造的角色、发现的地点、做出的选择——都会成为世界的一部分。**甚至你的失败也有跨会话的延续**：角色死亡会留下遗迹和传说，精神崩解的角色会成为 NPC——下一次冒险中，你可能会在祭坛角落看到一个眼神空洞的信徒，或在低地遇到一个灰皮肤的沉默者，你不知道他曾经是一个玩家角色。这是这个引擎最核心的哲学：**玩家不是"通关者"，玩家是世界的共同缔造者。**

---

*[Claude Code](https://claude.ai/code) · Python 3.10+*
