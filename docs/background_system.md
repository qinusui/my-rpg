# 场景背景系统

终端背景图跟随场景自动切换。`bg.py` 统一管理切换与生成，自动读取 `config.json` 的 `display.background_image`。

## 首次初始化

```
python tools/bg.py --init
```

仅需执行一次，自动检测 WT settings.json 路径和当前 profile GUID，缓存到 `rules/settings.json`。

## 背景切换触发点

`--set` / `--combat` 在切换前自动收拢已完成的异步生成任务——DM 不再需要手动 `--poll`。

**自动化**：`--set`、`--combat`、`--reset`、`--mood` 已挂钩到引擎事件，DM 不再需要手动执行：
- 地点变化 → `state_mgr.py --set current_location <id>` 自动触发 `bg.py --set <id>`
- 战斗初始化 → `combat.py --init <怪物> --threat <层级>` 自动触发 `bg.py --combat`
- 氛围变化 → `state_mgr.py --action --tags <tags>` 自动触发 `bg.py --mood`（由 `--tags` 推断）
- 会话结束 → `session_enrich.py --end-session` 自动触发 `bg.py --reset`

**全部自动**：DM 只需在 `--action` 时正确标记 `--tags`，背景切换完全不再占用 DM 注意力。

| 触发时机 | 命令 | 说明 |
|---------|------|------|
| 玩家到达新地点 | `bg.py --set <location_id>` | 自动——随 `--set current_location` 触发 |
| 新地点尚无背景图 | `bg.py --submit <scene_id> --prompt "..." --tags "..." --mood ...` | `--set` 返回 `needs_background: true` 时执行——DM 根据感官描述生成中文提示词+标签 |
| 战斗初始化 | `bg.py --combat <skirmish\|battle\|boss\|ambush> --monster <key>` | 自动——随 `combat.py --init` 触发，`--threat` 参数对应战斗层级 |
| 怪物线索暗示 | `bg.py --submit combat_<key> --prompt "..." --style combat --tags "..."` | NPC 台词/环境叙事中暗示某怪物即将遭遇时提前提交 |
| 氛围变化 | `bg.py --mood <key>` | **DM 手动**——情绪峰值或戏剧节点，支持 moods + narrative 全部 key |
| 战斗结束 | `bg.py --set <location_id>` | 自动——随 `--set current_location` 触发 |
| 玩家不喜欢 | `bg.py --skip <scene_id>` | 删图片+meta，prompt 记入 `_rejected.json` |
| 玩家收藏 | `bg.py --pin <scene_id>` | 复制图片到 `_shared/`，跨世界观可复用 |
| 恢复默认 | `bg.py --reset` | 自动——会话结束时触发 |

## 战斗层级

`--combat` 第一个参数指定威胁等级：

| 层级 | 命令 | 典型场景 | opacity |
|------|------|---------|---------|
| `skirmish` | `--combat skirmish` | 1-2 只弱敌、街头冲突、驱赶野兽 | 0.35 |
| `battle` | `--combat battle` | 正式战斗、多只敌人、势均力敌 | 0.40 |
| `boss` | `--combat boss` | 首领战、史诗威胁、剧情高潮 | 0.50 |
| `ambush` | `--combat ambush` | 伏击、突袭、猝不及防的遭遇 | 0.45 |

DM 根据 `bestiary.md` 中怪物的威胁程度和遭遇表威胁等级选择层级。若未指定层级，默认 `battle`。

## 氛围（Moods × 叙事节拍）

`--mood` 同时接受 moods 和 narrative beats 的 key——先在 `moods` 中查找，未命中则查 `narrative`。两种类型使用同一命令入口。

### Mood 预设

定义在 `backgrounds.json` → `moods`：

| key | opacity | 使用时机 |
|-----|---------|---------|
| `safe` | 0.20 | 据点、安全屋、治愈后 |
| `normal` | 0.30 | 正常探索 |
| `tension` | 0.40 | 追踪、潜入、对峙、风暴将至 |
| `danger` | 0.45 | 战斗、陷阱、濒死、崩毁 |
| `tragedy` | 0.15 | NPC 死亡、大失败、世界崩解 |

### 叙事节拍

定义在 `backgrounds.json` → `narrative`：

| key | 使用时机 |
|-----|---------|
| `discovery` | 发现隐藏通道、古门开启、关键线索浮出 |
| `escape` | 逃离崩塌建筑、追兵逼近、限时脱出 |
| `stealth` | 潜行穿过禁区、窃听、不被察觉地移动 |
| `revelation` | 重大真相揭露、世界观翻转、记忆恢复 |
| `aftermath` | 大战过后、灾难现场、寂静的余波 |

### 用法

```
python tools/bg.py --mood danger       # mood
python tools/bg.py --mood discovery    # narrative beat
```

有 `variants` 字段时随机选取一张变体图。无 variats 时仅调整 opacity。

### 自动 Mood 推断

`--action` 完成后，引擎从 `--tags` 推断氛围并自动调用 `bg.py --mood`：

| --tags | → mood | 效果 |
|--------|--------|------|
| `social` | safe | 对话、安全屋 (opacity 0.20) |
| `patrol` | normal | 探索、旅行 (opacity 0.30) |
| `rest` | safe | 休息、治愈 (opacity 0.20) |
| `ritual` | tension | 仪式、对峙 (opacity 0.40) |
| `stealth` | stealth | 潜行、窃听 |
| `danger` | tension | 高风险行动 (opacity 0.40) |
| `tragedy` | tragedy | 代价、失败 (opacity 0.15) |
| `discovery` | discovery | 发现、开启 |
| `escape` | escape | 逃离、脱出 |
| `revelation` | revelation | 真相揭露 |
| `aftermath` | aftermath | 战斗余波 |
| `combat` | — | 跳过（combat.py 接管 bg） |

多个 tag 时取第一个匹配，未知 tag 无操作。`--no-fade` 确保不增加延迟。

## 图像生成

1. `--lookup_location <scene_id>` 获取感官描述
2. 基于感官描述 + 当前时间/天气/氛围，用中文写画面提示词，提取 3-6 个中文关键词作为 `--tags`
3. `python tools/bg.py --submit <scene_id> --prompt "提示词" --tags "关键词1,关键词2,..." --mood <mood>`
4. 下次 `--set` 或 `--combat` 自动收拢生成图并显示

### 玩家反馈协议

新场景图生成后，DM 在叙事中用一句话自然引入，无需显式询问。玩家沉默 = 隐式接受。

DM 监听自然语言反馈，识别意图后静默执行对应工具命令：

| 玩家表达 | DM 静默执行 | 效果 |
|---------|-----------|------|
| "不好看" / "不喜欢" / "换一张" / "重新生成" | `bg.py --skip <scene_id>` | 删图片+meta，prompt 记入 `_rejected.json`，下次自动丰富 negative |
| "收藏" / "很好看" / "喜欢这张" / "存起来" | `bg.py --pin <scene_id>` | 复制图片到 `_shared/backgrounds/`，跨世界观可复用 |
| 沉默 / 中性回应 | 不操作 | 默认保留 |

玩家若在叙事进行中表达图片态度，当前轮结束后再处理。

### 共享图库与自动复用

`--submit` 在调用 API 前先查 `rules/_shared/index.json`——若存在 mood 匹配且 tags 重叠 ≥3 的条目，直接复用共享图片，零费用。`--pin` 同步写入 index。

### 图片替换

玩家可将 `rules/{active_world}/backgrounds/` 或 `rules/_shared/backgrounds/` 中的图片替换为真实照片或概念艺术，文件名与 `backgrounds.json` 一致即可。
