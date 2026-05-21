# 历次修正案例

> DM 重复犯的规范错误存档。CLAUDE.md 只留规则，反例沉到此文件。

---

## 案例记录

<!-- 格式：日期 + 错误描述 + 修正内容 -->

### 2026-05-21: AskUserQuestion header 位置错误

**错误**：DM 将 `header` 放在 AskUserQuestion 顶层，而非 `questions[0]` 内部。

**正确格式**：
```json
{
  "questions": [{
    "header": "情境标签",
    "question": "...",
    "options": [...]
  }]
}
```

**修正**：CLAUDE.md §3 重写调用格式为 JSON 示例，标注 header 必须内嵌。

### 2026-05-21: 选项数超过 4 上限

**错误**：角色创建时 DM 列出超过 4 个选项，或手动添加"其他"选项。

**规则**：AskUserQuestion 自带 "Other" 选项。最多 4 个显式选项时：前 3 个放最典型选择，禁止手动写第 4 个"其他"，超出部分通过 Other 自由输入。

**修正**：CLAUDE.md §3 + docs/character_creation.md 均加入选项上限规则。
