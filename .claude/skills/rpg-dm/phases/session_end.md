# 会话结束

每次会话结束时执行：

**一键结束**（推荐）：
```
python tools/session_enrich.py --end-session
```
自动串联：`bg.py --reset` → archive → report。

或分步执行：

**第一步** — 恢复终端背景：
```
python tools/bg.py --reset
```

**第二步** — 归档旧数据：
```
python tools/session_enrich.py --archive
```

**第三步** — 验证报告：
```
python tools/session_enrich.py --report
```
报告末尾"需手动处理"下的每一项都必须处理。session_enrich 不再做批量富化——锚点已在叙事中实时写入，此处只验证有无遗漏。

**第四步（可选）** — 导出会话：
```
python tools/session_enrich.py --export-session "龙眠峰哨站解放"
```

**第五步（可选）** — 写入世界知识层（chronicle）：
```
python tools/session_enrich.py --chronicle add_legend '{"content":"...","spread":"low"}'
python tools/session_enrich.py --chronicle add_relic '{"location":"...","description":"...","permanent":true}'
python tools/session_enrich.py --chronicle add_faction_shift '{"faction":"...","change":"...","reason":"hidden"}'
python tools/session_enrich.py --chronicle add_ending victory "..."
python tools/session_enrich.py --chronicle add_broken '{"name":"...","origin":"...","location":"...","state":"...","fragment":"..."}'
```

## 沉淀原则

- 锚点在叙事进行中立即写入，不等会话结束
- 玩家行为是最高真理——选择改变了世界观则文件必须反映
- 仅限 `rules/{active_world}/` 和 state.json——不修改引擎代码和 SKILL.md
- 由少聚多：每次 +1 NPC/地点/物品，十次后有一个完整的世界
- 一次性的氛围描写、无后续影响的背景细节、玩家未感知的内部叙事——不沉淀
- 写入 chronicle 时必须优先沉淀"后续摩擦"而非"终极解释"（例如：戒严升级、口径分裂、补给重分配、关系反噬）
