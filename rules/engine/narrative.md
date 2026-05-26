# 叙事规则

## 叙事沉淀规则

现编细节满足以下任一条件时，立即写入世界文件（不等会话结束）：

- 玩家主动询问过的细节
- NPC 明确说出口的事实
- 玩家的行动造成的物理改变
- 影响势力关系的事件

其余细节不沉淀，只活在本次叙事里。

写入时在条目末尾标注来源：`[来源：session_{日期}]`

## 叙事输出

> 完整规则 → `docs/narrative_output.md`

核心约束：
- 工具调用（静默）→ 叙事 + AskUserQuestion（同一响应，原子输出）
- **回合输出 = 叙事段落 + AskUserQuestion，二者在同一条消息中完成，禁止拆分为两次响应。叙事写完直接接 AskUserQuestion，中间不插入"回合完成"的判断。**
- **禁止在叙事输出开始后调用任何工具**
- 当 `narrative.implicit_description` 为 `true` 时：不说数值、不说术语、不说回合
- 必须在每次叙事正文结尾追加两个空行，再进入 AskUserQuestion
- **叙事段落的最后一个元素永远是 AskUserQuestion 块，禁止以纯叙事句子结尾。不给出选项的叙事视为未完成。**<!-- 修正：DM 多次以纯叙事收尾不给选项 -->
- 引入 NPC 或场景前先查：`python tools/state_mgr.py --lookup_npc "名"` / `--lookup_location "地"`
- 表格必须通过 box.py：`printf "列1\t列2\n值1\t值2\n" | python tools/box.py`

## 叙事风格

从 `config.json` 读取 `narrative.style`，加载对应风格规范：

| 值 | 风格 | 文件 |
|------|------|------|
| `noir_urban` | 暗色都市（Disco Elysium 风） | `docs/styles/noir_urban.md` |
| `epic` | 古典史诗（Tolkien/龙枪风） | `docs/styles/epic.md` |
| `hardboiled` | 黑色电影（Raymond Chandler 风） | `docs/styles/hardboiled.md` |
| `brutal` | 残酷现实（Abercrombie 风） | `docs/styles/brutal.md` |

DM 在每段叙事输出前通读对应风格文件的"五条手法"和"禁止出现"，按该风格的语气和节奏写作。
