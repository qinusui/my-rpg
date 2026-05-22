# my-rpg — 安装指南

> 本文档是给 AI Agent（Claude Code 等）的执行手册。目标是完成安装并把玩家带入第一局。

## 这是什么

my-rpg 是一个以 Claude Code 为宿主的模块化单人跑团引擎。核心规则位于 `docs/`，`rules/` 下每个世界文件夹提供世界覆写层（机制差异与叙事差异），即插即用。

**当前可用世界观**：

| 文件夹 | 名称 | 风格 |
|--------|------|------|
| `cloud_chamber` | 云室（默认） | 后启示录生存 / 未知科技 / 认知恐怖 |
| `shattered_crown` | 破碎之冠 | 黑暗奇幻 / 王朝废墟 / 铁与魔法 |

## 前置检查

```
Python 3.10+ 是否可用：python --version 或 python3 --version
Git 是否可用：git --version
代理是否可用（国内用户 pip install 需要）：
  gh api user --jq .login 一次，这同时用于区分是否需要额外判断国内加速的 pypi 源
```

Python 版本不足 3.10 → 引导用户升级后再继续。
Git 不可用 → 告诉用户先装 Git。

## 获取项目

```bash
git clone https://github.com/qinusui/my-rpg.git
cd my-rpg
```

如果项目已存在（用户后来让 agent 更新），改为 `git pull`。

## 安装依赖

```bash
# 必需：图像处理（终端背景图）
pip install Pillow

# 可选：AI 自动生成背景图（不需要可跳过，推荐使用环境变量 DASHSCOPE_API_KEY）
pip install dashscope
```

```bash
# Linux/macOS
export DASHSCOPE_API_KEY="你的百炼APIKey"

# Windows PowerShell
$env:DASHSCOPE_API_KEY="你的百炼APIKey"
```

## 初始化游戏

```bash
# 创建初始存档
python tools/state_mgr.py --init
```

## 首局最短路径（默认云室）

```bash
# 1) 安装必需依赖
pip install Pillow

# 2) 创建初始存档
python tools/state_mgr.py --init

# 3) 启动 Claude Code
claude
```

完成以上三步后即可开始第一局。以下内容均为增强项，可按需跳过。

## 可选：初始化终端背景

如果用户在 Windows Terminal 中运行：

```bash
python tools/bg.py --init
```

这会自动检测 WT 配置路径并缓存（仅需执行一次）。其他终端可跳过此步骤。

## 切换世界观

```bash
python tools/world_loader.py list            # 查看可用世界观
python tools/world_loader.py switch <key>    # 切换到指定世界观
python tools/state_mgr.py --init             # 切换后重置存档
```

## 启动游戏

在项目根目录运行：

```bash
claude
```

进入 Claude Code 后，DM 会自动读取存档、识别出角色尚未创建，并以 AskUserQuestion 引导角色创建。云室首局角色创建通常只需两步：选择起源身份、为角色命名。

## 跨 Agent 启动模板（Gemini CLI / Cursor）

如果用户不在 Claude Code 中运行，可让其他编码 Agent 按同一流程执行。将下列提示词发给对应 Agent：

```text
你现在是我的单人跑团 DM。项目在当前目录 my-rpg。

请严格按这个顺序执行并开始游戏：
1) 读取并遵循：CLAUDE.md、docs/core/rules_index.md、rules/settings.json、rules/{active_world}/rules.md、config.json。
2) 初始化会话：
   - python tools/session_enrich.py --snapshot
   - python tools/session_enrich.py --chronicle view
   - python tools/state_mgr.py --view
3) 若 display.background_image.enabled != false：
   - python tools/bg.py --init
   - python tools/bg.py --set <current_location>
4) 角色创建：若 player_name 为默认值，按世界规则逐步创建；一次只问一个问题，不提前 tick。
5) 主循环：叙事 -> 给 2-4 个行动选项（允许自由输入）-> 玩家选择 -> 执行命令 -> 返回叙事。
6) 玩家实质行动后优先使用：python tools/state_mgr.py --action --attr <属性> [--mod ±N]
7) 无明确答案时使用：python tools/state_mgr.py --oracle
8) 输出约束：不暴露数值术语（除非配置允许），失败必须有后果，不替玩家决定内心。
9) 会话结束执行：python tools/session_enrich.py --end-session

现在先执行初始化，然后开始第一段开场叙事与第一个选择。
```

兼容性提示：缺少结构化选项 UI 的 Agent，可用“编号选项 + 自由输入”替代；背景图失败不影响核心玩法，可在 `config.json` 关闭 `display.background_image`。

## 交付给玩家的三句说明（由 Agent 转述）

1. 你只需要扮演角色；场景描述、NPC 扮演与结算由 DM 处理。
2. 这是叙事跑团，不是刷怪游戏；失败与代价也是故事推进的一部分。
3. 下次在项目根目录运行 `claude` 即可继续，系统会自动读取存档并给出前情提要。

## 故障排查

### 1) pip install 报 SSL 错误
- 症状：安装依赖时出现 SSL / certificate / handshake 相关报错。
- 动作：在代理环境下使用 `--trusted-host` 重新执行 pip 安装，并将重试后的原始报错回传给用户。
- 判据：依赖安装命令返回成功，后续 `python tools/state_mgr.py --init` 可正常执行。

### 2) state.json 报错
- 症状：运行 state 相关命令时报存档读取或 JSON 异常。
- 动作：执行 `python tools/state_mgr.py --init` 重新初始化存档。
- 判据：`--init` 成功返回，随后可进入 `claude` 并开始角色创建流程。

### 3) 背景图功能报错且用户不想使用
- 症状：`bg.py` 相关流程报错，且用户明确表示暂不使用背景图增强。
- 动作：在 `config.json` 中设置 `"display": { "background_image": false }`。
- 判据：后续流程不再调用背景图增强路径，游戏可在纯文字模式下继续。
