# 目标生命周期

目标是玩家定义的结局条件。它有开始、推进、完成、失败——以及完成后的分叉。

---

## 目标创建与誓言

DM 从世界专属 `oaths.md` 中取 1 个固定誓言（随机抽取），再按原创誓言规范即兴创作 2 个，合计 3 个用 AskUserQuestion 展示（不标明哪个来自固定池）。

> 原创誓言的生成框架由各世界 `oaths.md` 定义。云室使用三维度框架（对象层 × 规模层 × 张力层），破碎之冠使用 `character_options.json` 中的固定目标列表。其他世界观可自行定义。

玩家选定目标后，额外执行一步：

**誓言仪式** — 玩家用自己的话说出誓言的措辞。DM 将原话写入目标：

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --set_oath "玩家原话"
```

誓词在关键时刻被引用——目标濒临失败时、终结行动宣告时、目标完成/失败时。不是装饰，是叙事锚点。

---

## 目标时钟推进

`--tick` 自动输出 `goal_clock` 字段（含 `current`/`max`/`trigger_hint`）。DM 每次 tick 后检查，满足触发条件则推进：

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --tick_goal_clock
```

满格时 DM 不自动完成——提示玩家"终结行动的时机已到"，让玩家自己决定何时尝试终结。

---

## 终结行动

玩家可以在任何时刻主动宣告终结。进度填得越满，成功概率越高——但时机由玩家选择，不由系统强制。

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --finale_goal
```

**判定**：掷 1d6 + 进度已填格数 vs DC。

DC 由目标规模决定：
- 个人誓言（找到某人、拿回某物） DC 10
- 地区性誓言（推翻组织、守护一方） DC 14
- 史诗誓言（改变世界格局） DC 18

**三段结果**：
- 超过 DC+3 → 强成功：目标达成，额外收获
- 等于或超过 DC → 弱成功：目标达成，但有代价
- 低于 DC → 失败：进度倒退 1 格 + 灾难事件，目标仍在

**成功后**：DM 调用 `--complete_goal` 执行世界突变（目标定义中的 world_mutation）。弱成功时额外施加一个代价（由 DM 根据情境决定）。

---

## 目标完成

当目标的完成条件在叙事中真实发生时：

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --complete_goal [--goal_location <key>] [--goal_npc <名称>] [--goal_lore <key>]
```

`--complete_goal` 自动从目标定义中读取 `world_mutation`，将成果写入世界：

| 类型 | 参数 | 效果 |
|------|------|------|
| 守护 | `--goal_location` | 标记安全屋，写入 `world_constants.json` |
| 寻找 | `--goal_npc` | NPC 永久已知，写入 `known_npcs` |
| 揭秘 | `--goal_lore` | 文献揭示，写入 `revealed_lore` |
| 还债/自证/复仇 | — | 写入 `_permanent_flags`，跨会话持久 |

然后读取 `character_options.json` 的 `goal_completion_branch`，用 AskUserQuestion 展示分叉：

- question: `goal_completion_branch.question`
- header: `goal_completion_branch.header`
- options: `就此封笔`（结束）和 `继续前行`（新目标）

### 玩家选择"就此封笔"

1. 用目标的 `ending_tag` 编写结局叙事（300-500 字）
2. `python tools/session_enrich.py --export-session "结局：<ending_tag>"`
3. 建议玩家 `python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --init` 开始新冒险

### 玩家选择"继续前行"

1. 根据目标的 `reward` 字段执行属性更新
2. 用 `--set_goal` 选择新目标（DM 再次展示 `goals` 列表，排除已完成/已失败的目标）
3. 叙事上：旧目标的完成打开了更深的缺口——新目标不是"下一个任务"，而是旧路尽头浮现的更大问题

#### 完成不等于解答

- `--complete_goal` 写入 world mutation 后，DM 必须继承至少一个未解摩擦进入下一目标：
  - 资源拉扯（配给、路线、工具、庇护点）
  - 关系拉扯（谁开始不信任你，谁要求你站队）
  - 叙事可信度拉扯（同一真相出现冲突版本）
- 禁止将“继续前行”写成重置式新任务；上一目标的代价必须继续发酵。
- 目标完成可以关闭一个局部矛盾，但必须打开至少一个更深层矛盾。

---

## 目标失败

当失败条件在叙事中真实发生时：

```
python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --fail_goal
```

目标失败不等于游戏结束。规则：

- DM 禁止用叙事软化失败——失败就是失败，直接声明
- 目标标记为 failed，移入 completed_goals（作为伤痕）
- 玩家在无目标状态下继续——空白的目标栏本身就是故事
- 玩家可随时选择新目标（排除已完成/已失败的目标）
- 禁止 DM 提供"重试"或"换个类似目标"——新目标必须是与旧目标不同的选择

永久性的目标失败是叙事的重量来源。和角色死亡一样，它是玩家亲手铸成的历史，不是随机惩罚。失败的目标留在 completed_goals 中作为永久记录。

---

## 过往张力（Background-Goal Tension）

当角色的过往与目标存在内在冲突时（`character_options.json` 中 `tension_with` 匹配），整局游戏持续生效：

- `--view` 自动展示张力段落（过往×目标 + 具体效应）
- `--tick` 自动输出 `tension` 字段，DM 不可忽略
- 张力提供**双向修正**：有利面（如 DC-2）和不利面（如 san 钟 +1），DM 根据情境裁决
- 张力不是惩罚——是角色的内在驱动力

### 示例

| 过往 | 目标 | 效应 |
|------|------|------|
| 逃兵 | 守护一处地方 | 守护检定 DC-2，但若出现背叛迹象→san+1 |
| 贵族后裔 | 还清旧债 | 上流场所 DC-2，下等场所 DC+2——债主的人可能在角落 |
| 学院弃徒 | 破解一个秘密 | 解读古文献 DC-2，但大失败范围扩展到 1-2 |
| 流浪艺人 | 找到一个人 | 每新城镇 D20≥15→听到线索（但可能是假的） |
