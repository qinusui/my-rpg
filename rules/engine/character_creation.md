# 角色创建

> DM 必须已读取 `rules/{active_world}/rules.md` §角色创建。以下为通用约束，具体步骤、数据源、命令由各世界规则文件定义。

触发条件：`--view` 显示 `player_name` 为默认值（`"冒险者"` 或 `"无名者"`——取决于世界观）。

- 每次只问一个问题（AskUserQuestion），严格按 rules.md 中的步骤顺序执行
- 角色创建期间不执行 `--tick`
- 开场叙事按 `rules/{active_world}/rules.md` 中规范执行——原则为硬约束，范例为风格参照，允许在框架内发挥
