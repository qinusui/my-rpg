# NPC 关系

NPC 与玩家的关系是轻量追踪系统。和进度钟一样：DM 判断"这个时刻足够重要"，然后升级。

---

## 命令

```
python tools/state_mgr.py --affinity "海拉"                              # 查询单个
python tools/state_mgr.py --affinity                                     # 列出全部
python tools/state_mgr.py --affinity "海拉" close --milestone "..."       # 升级
python tools/state_mgr.py --affinity "海拉" cold --milestone "..."        # 降级
```

`--view` 自动包含 `affinities` 摘要。

---

## 关系等级（8 档——禁止展示给玩家）

| 等级 | 含义 | NPC 行为变化 | 变化条件 |
|------|------|-------------|---------|
| `hostile` | 敌对 | 可能主动攻击、破坏计划、散布谣言、拒绝一切互动 | 严重背叛、伤害 NPC 珍视之人 |
| `wary` | 戒备 | 拒绝帮助，对话简短带敌意，可能跟踪或监视 | 背叛、威胁、触及 NPC 核心禁忌 |
| `cold` | 冷淡 | 态度疏远，不主动互动，回答敷衍。交易加价 | 轻微失信、让 NPC 失望 |
| `stranger` | 陌生人（默认） | 只说公开信息，保持距离 | 初始状态 |
| `acquaintance` | 相识 | 记住名字和偏好，轻度互动 | 一次有意义的互动 |
| `friend` | 朋友 | 主动帮助，透露轻度保留信息，提及个人话题 | 两次以上重要互动，或一次重大帮助 |
| `close` | 亲密 | 几乎无保留，可透露 cognition 块未写的深层秘密 | 多次深度互动 + 叙事里程碑 |
| `intimate` | 羁绊 | 仅限浪漫线——命运深度缠绕，可影响结局 | 明确的浪漫确认 |

**禁止跳级**：关系必须逐级变化（正向和负向均如此）。每次变化必须伴随一个具体的叙事里程碑。

---

## 敌对关系特殊规则

- `hostile` NPC 不出现在 AskUserQuestion 选项中（除非作为威胁）
- `hostile` NPC 可能在玩家长休时推进自己的敌对计划——DM 可为其创建独立的进度钟
- 从 `hostile` 回升到 `wary` 需要重大和解事件
- 降至 `hostile` 前 DM 必须确认：此 NPC 确实有动机和能力对抗玩家

---

## 关系与认知的联动

| 等级 | 可透露内容 |
|------|-----------|
| hostile | 拒绝交流——NPC 可能主动散布关于玩家的虚假信息 |
| wary | 仅限 `knows` 中的公开信息，态度负面 |
| cold | `knows` 中的公开信息，语气冷淡疏远 |
| stranger | `knows` 中的公开信息 |
| acquaintance | `knows` + 部分 `believes_wrongly` |
| friend | `knows` + `believes_wrongly` + 部分 `conceals` |
| close | 几乎无保留——`conceals` 大部分可透露 |
| intimate | 完全信任——NPC 的决策会考虑玩家利益 |

---

## 关系与选项的联动

- `hostile` → 可出现"警惕——XXX 可能在暗中行动"
- `wary` → 可出现"XXX 似乎不太信任你"
- `friend` 级以上 → 可出现"去问问 XXX 的看法"
- `close` 级以上 → 可出现"把后背交给 XXX"
- `intimate` → 可出现"和 XXX 一起面对"

---

## 云室核心 NPC 执行法

适用于云室核心 NPC（`high_priest / old_scholar / plinth_scout / gray_elder / water_seeker`）。

- 关系变化后，必须改变后续行为，而不只是改标签：
  - 信息精度（模糊提示 / 可验证线索 / 关键细节）
  - 风险倾向（保守回避 / 交易合作 / 共同承担）
  - 合作边界（拒绝 / 限定合作 / 深度协作）
- 每次 `--affinity ... --milestone "..."` 的 milestone 必须写明“事件 + 为什么影响信任”，禁止空泛描述（如“聊得不错”）。
- 关系降级必须在叙事中产生后果：回避、误导、延迟、公开切割，至少出现其一。
- 禁止跳级规则不变；关系对 cognition 可见度门槛不变。

### 里程碑书写模板（建议）

`事件：...；玩家行为：...；NPC判断：...；关系变化原因：...`

### 关键对话记录快版（当场可落 dm_log）

`话题：...；关系档位：...→本轮倾向：...；表层台词：...；潜台词：...；动作：...；后续里程碑候选：...`

如需完整人格约束与高压反应，返回 `rules/cloud_chamber/npc_persona_protocol.md` 执行通用顺序。

---

## 浪漫线

`world_constants.json` 中部分 NPC 有 `"romanceable": true` 标记：

- 表示该 NPC 的性格和叙事设定中有情感发展的空间
- 浪漫不是"攻略"——它是深厚友谊的自然延伸。`friend` → `close` → `intimate` 必须由玩家主动推动
- 不是每个 `romanceable` NPC 都必须发展浪漫——由玩家选择，DM 响应

### 禁止事项

- 禁止 DM 主动推进浪漫线——玩家不表达兴趣，就不升级到 `close`/`intimate`
- 禁止将关系等级数值化展示——"好感度 +5" → 应该说"她看你的眼神比之前柔软了"
- 禁止用关系系统强制玩家——`intimate` 不是"绑定"
- 禁止将 NPC 简化为"可攻略对象"

---

## 关系下降参考

| 程度 | 降级 | 触发 |
|------|------|------|
| 轻度 | 1 级 | 失约、隐瞒、立场分歧 |
| 中度 | 2 级 | 食言、利用 NPC 信任牟利 |
| 重度 | 直降至 hostile/wary | 背叛、伤害 NPC 珍视之人 |

降级时必须写入 dm_log。
