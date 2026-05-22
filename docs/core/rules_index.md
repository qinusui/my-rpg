# 核心规则索引（Core + Overlay）

> 本文件定义规则加载边界：先读核心规则，再读世界覆写。

## 加载顺序

1. 读取本索引，确认核心规则入口
2. 读取核心规则文档（`docs/`）
3. 读取活跃世界覆写（`rules/{active_world}/rules.md`）
4. 若冲突：世界覆写优先于核心规则

## 核心规则（引擎通用）

- 判定：`docs/d20.md`
- 时间推进与遭遇：`docs/tick_system.md`
- 代价执行：`docs/consequences.md`
- 目标生命周期：`docs/goals.md`
- 结局系统：`docs/endings.md`
- 战斗流程：`docs/combat.md`
- 叙事输出：`docs/narrative_output.md`
- 知识防火墙：`docs/knowledge_firewall.md`
- NPC 关系：`docs/npc_relationships.md`

## 世界覆写（World Overlay）

`rules/{active_world}/rules.md` 只承载以下内容：

1. 世界属性映射与阈值表
2. 世界专属机制
3. 世界叙事约束与模板
4. 与核心规则冲突时的覆写声明

## 迁移原则（第一轮）

- 只抽“流程骨架”，不抽“世界机制”
- 不改脚本命令与参数接口
- 世界专属机制保留在各世界文件内
- 文档去重优先使用引用，不做大规模重写
