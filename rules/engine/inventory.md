# 背包交互流程

触发：玩家主动翻背包、NPC 索要、解密/仪式、交易、被迫丢弃、装备选择。

1. 按场景过滤 → `--list_inventory --tag weapon/consumable/armor`（或不过滤）
2. 展示编号列表，将 2-3 件最重要物品作为 AskUserQuestion 选项
3. 玩家选定后执行：消耗品 → `--use_item` + grep items.md 确定效果；装备 → `--set equipped_weapon <id>`；交付/抵押 → 按情境消耗或不消耗
4. 遵循隐性反馈：不说数值，用叙事表达结果
