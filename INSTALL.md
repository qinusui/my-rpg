# my-rpg — 安装指南

> 本文档写给 AI Agent（Claude Code 等）。Agent 请按序执行每一步。

## 这是什么

my-rpg 是一个以 Claude Code 为宿主的模块化单人跑团引擎。引擎与世界观数据完全分离——`rules/` 下的每个文件夹是一个独立游戏卡带，即插即用。

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

# 可选：AI 自动生成背景图（不需要可跳过，安装后在 config.json 填写 API Key）
pip install dashscope
```

## 初始化游戏

```bash
# 创建初始存档
python tools/state_mgr.py --init
```

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

进入 Claude Code 后，DM 会自动读取存档、识别出角色尚未创建，然后以 AskUserQuestion 引导角色创建。云室的角色创建只需两步：选择起源身份、为角色命名。创建完成后，DM 会将你投入世界——故事从那里开始。

## 游戏流程简介

**告诉用户这三件事就够了：**

1. **你只需要扮演你的角色。** DM（Claude Code）负责描述场景、扮演 NPC、结算战斗。当你面对选择时，弹出的是交互式选项菜单——点选即可。你也可以随时输入自己的行动。
2. **这是一款叙事跑团，不是刷怪游戏。** 没有经验值、没有等级。你的角色会受伤、会失败、会被世界改变。失败不是惩罚——是故事的一部分。
3. **下次继续玩。** 在项目根目录运行 `claude` 即可——DM 会自动读取上次的存档，用一段"前情提要"帮你回到故事中。

## 故障排查

```
问题：pip install 报 SSL 错误
→ 代理环境下可能需要 --trusted-host，Agent 直接重试并把报错原文传给用户

问题：state.json 报错
→ python tools/state_mgr.py --init 重新初始化

问题：后台图功能报错但不想用
→ config.json 中设置 "display": { "background_image": false }
```
