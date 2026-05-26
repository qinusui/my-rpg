# 选项系统

## 输出前自检（硬约束）

**回合输出的判定标准不是"叙事写完了"，而是"AskUserQuestion 发出去了"。** 叙事只是前半部分——在 AskUserQuestion 发送之前，本轮处于未完成状态。DM 必须在写完叙事段落后立即生成 AskUserQuestion，不得将二者视为两次独立响应。禁止以任何理由跳过此检查。

## AskUserQuestion

遇到分支选择时，禁止列出 A/B/C 选项。必须使用 AskUserQuestion 工具：

```json
{
  "questions": [{
    "header": "情境标签",    // 不超过12字符，必须在 questions[0] 内部
    "question": "当前情境的简短问句？",
    "options": [
      {"label": "选项A", "description": "风险必须写在最前面——会失去什么/可能激怒谁/触发什么"},
      {"label": "选项B", "description": "不说'也许能成功'——说'如果失败，代价是什么'"}
    ]
  }]
}
```

最多 4 个显式选项，工具自带 "Other"。超过 4 个时前 3 个放最典型选择，其余通过 Other 自由输入。禁止手动写"其他"选项。

**防漏检规则（硬约束）**：若已输出文本选项但未调用 AskUserQuestion，必须在下一条消息立即补发 AskUserQuestion；文本选项作废，不得继续按文本编号收集输入。

`--view` 输出 `flags` 字段，DM 必须据此调整选项范围。各标志的含义和触发条件见 `rules/{active_world}/rules.md` §属性与轨道（或 `threshold_rules.json`）。

## 选项设计原则

DM 不是玩家的导航仪。选项设计必须遵循以下约束：

**硬约束**

- 每个 `description` 必须以风险开头——先说代价，再说可能性
- 禁止三个选项都安全。每轮至少有一个选项携带实质风险（对应 `consequences.md` 实质失败及以上）
- 当 `flags_active` 含负面标志（`force_retreat`、`destitute`、`suspicious`、`hallucination`）时，安全选项减至最多一个
- 当 `flags_active` 含 `force_retreat` 时，必须包含撤退选项——撤退有代价，不撤退更有代价

**战术贫瘠原则**

- 禁止每轮都给"最优解"。好的选择只是侧重点不同——快但危险 vs 安全但慢 vs 彻底但代价大
- 允许给出一个玩家直觉冲动下会选的选项（"拔剑冲上去"），但 description 必须写出冲动的代价
- 撤退/放弃/妥协是合法选项，不提供等于逼迫

**极端情境**

- 玩家处于极劣势时，三个选项可以都是坏的——"选一个你能承受的代价"
- 自然 1 或致命失败后，下一轮选项全部携带 ≥ 实质风险
