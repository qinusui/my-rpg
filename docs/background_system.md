# 场景背景系统

终端背景图跟随场景自动切换。`bg_switcher.py` 自动读取 `config.json` 的 `display.background_image`。

## 首次初始化

```
python tools/bg_switcher.py --init
```

仅需执行一次，自动检测 WT settings.json 路径和当前 profile GUID，缓存到 `rules/settings.json`。

## 背景切换触发点

| 触发时机 | 命令 | 说明 |
|---------|------|------|
| 玩家到达新地点 | `python tools/bg_switcher.py --set <location_id>` | 跟随 `--set current_location` 一起执行 |
| 新地点尚无背景图 | `python tools/bg_generator.py --submit <scene_id> --prompt "..." --tags "..." --mood ...` | DM 根据感官描述生成中文提示词+标签 |
| 战斗初始化 | `python tools/bg_switcher.py --combat <skirmish\|battle\|boss\|ambush> --monster <key>` | 查专属战斗图，命中则用，未命中回退通用图 |
| 怪物线索暗示 | `python tools/bg_generator.py --submit combat_<key> --prompt "..." --style combat --tags "..."` | NPC 台词/环境叙事中暗示某怪物即将遭遇时提前提交 |
| 战斗间隙 | `python tools/bg_generator.py --poll` | 收拢已完成的怪物专属战斗图 |
| 战斗结束 | `python tools/bg_switcher.py --set <location_id>` | 切换回当前位置的场景 |
| 情绪切换 | `python tools/bg_switcher.py --mood danger` | 重大揭示、濒死等情绪峰值时使用 |
| 叙事节拍 | `python tools/bg_switcher.py --narrative <discovery\|escape\|stealth\|revelation\|aftermath>` | 戏剧节点切换氛围图 |
| 收拢已生成图片 | `python tools/bg_generator.py --poll` | 每次回合间隙或会话结束时执行 |
| 恢复默认 | `python tools/bg_switcher.py --reset` | **必须**——每次会话结束时执行 |

## 战斗层级

`--combat` 第一个参数指定威胁等级：

| 层级 | 命令 | 典型场景 | opacity |
|------|------|---------|---------|
| `skirmish` | `--combat skirmish` | 1-2 只弱敌、街头冲突、驱赶野兽 | 0.35 |
| `battle` | `--combat battle` | 正式战斗、多只敌人、势均力敌 | 0.40 |
| `boss` | `--combat boss` | 首领战、史诗威胁、剧情高潮 | 0.50 |
| `ambush` | `--combat ambush` | 伏击、突袭、猝不及防的遭遇 | 0.45 |

DM 根据 `bestiary.md` 中怪物的威胁程度和遭遇表 DC 选择层级。若未指定层级，默认 `battle`。

## Mood 氛围

mood 预设定义在 `backgrounds.json` 中：

| mood | opacity | 叙事含义 |
|------|---------|---------|
| `safe` | 0.20 | 据点、安全屋、治愈后 |
| `normal` | 0.30 | 正常探索 |
| `tension` | 0.40 | 追踪、潜入、对峙、风暴将至 |
| `danger` | 0.45 | 战斗、陷阱、濒死、崩毁 |
| `tragedy` | 0.15 | NPC 死亡、大失败、世界崩解 |

`--mood` 切换背景图和透明度。`_shared` 为每种 mood 配置了 3-4 张变体图，`--mood` 会随机选取一张。

## 叙事节拍

`--narrative` 用于跨地点的戏剧节点：

| 节拍 | 命令 | 使用时机 |
|------|------|---------|
| `discovery` | `--narrative discovery` | 发现隐藏通道、古门开启、关键线索浮出 |
| `escape` | `--narrative escape` | 逃离崩塌建筑、追兵逼近、限时脱出 |
| `stealth` | `--narrative stealth` | 潜行穿过禁区、窃听、不被察觉地移动 |
| `revelation` | `--narrative revelation` | 重大真相揭露、世界观翻转、记忆恢复 |
| `aftermath` | `--narrative aftermath` | 大战过后、灾难现场、寂静的余波 |

## 图像生成

### 自动生成流程

1. `--lookup_location <scene_id>` 获取感官描述
2. 基于感官描述 + 当前时间/天气/氛围，用中文写画面提示词，提取 3-6 个中文关键词作为 `--tags`
3. `python tools/bg_generator.py --submit <scene_id> --prompt "提示词" --tags "关键词1,关键词2,..." --mood <mood>`
4. 下次"继续"间隙或会话结束时 `python tools/bg_generator.py --poll` 收拢

### 玩家反馈协议

新场景图生成后，DM 在叙事中用一句话自然引入，无需显式询问。玩家沉默 = 隐式接受。

| 玩家表示 | DM 执行 | 效果 |
|---------|---------|------|
| 不喜欢 / 换一张 | `python tools/bg_generator.py --skip <scene_id>` | 删图片+meta，prompt 记入 `_rejected.json`，下次自动丰富 negative |
| 特别喜欢 / 留着 | `python tools/bg_generator.py --pin <scene_id>` | 复制图片到 `_shared/backgrounds/`，跨世界观可复用 |

### Provider 配置

引擎通过 `tools/image_gen/` 适配层支持任意图像生成后端。`config.json` 中指定：

```json
{
  "image_gen": {
    "provider": "wanx",
    "fallback": null,
    "providers": {
      "wanx": { "api_key": "" }
    }
  }
}
```

接入新服务只需写一个文件 + 改一行配置。详见 `docs/image_provider_spec.md`。

### 共享图库与自动复用

`--submit` 在调用 API 前先查 `rules/_shared/index.json`——若存在 mood 匹配且 tags 重叠 ≥3 的条目，直接复用共享图片，零费用。`--pin` 同步写入 index。

### 陌生感模糊

首次抵达新地点时 `--set` 自动以 0.12 opacity 显示共享回退图。`--poll` 收拢生成图后，DM 重新 `--set <scene_id>`——世界专属图以正常 opacity 淡入。

### 图片替换

玩家可将 `rules/{active_world}/backgrounds/` 或 `rules/_shared/backgrounds/` 中的图片替换为真实照片或概念艺术，文件名与 `backgrounds.json` 一致即可。
