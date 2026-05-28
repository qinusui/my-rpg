# World Constants

> Auto-generated from `world_constants.json`.
> Edit with care — use `--sync_world_md` to sync back to JSON.

---

## NPC: high_priest

- **role**: 祭坛大祭司

### Traits

- 白发苍苍，手指因常年接触圣水而泛黄
- 说话时从不看对方的眼睛——他看的是对方额头上的'罪'
- 对旧世界文字有隐秘的好奇心——但他绝不会承认

### Voice

低沉缓慢，每句话都像在宣读经文。从不直接回答是或否

### Quirk

每次分发圣水前会用指尖沾一滴涂在自己额头上——没人知道这是仪式还是个人习惯

### Cognition

- **knows**:
    - 圣水的配给量和每一瓶的去向
    - 定居点里每一个'有问题'的人的名字
    - 禁地方向偶尔会出现不明的冷白闪光——但他选择不报告
- **believes_wrongly**:
    - 圣水是救世主的血液，具有神圣不可替代的力量
    - 灰质者是酿主诅咒的产物——不是进化
- **conceals**:
    - 他知道圣水的库存正在缓慢减少——已经持续了十多年
    - 二十年前他亲手流放了一个看到了不该看的东西的洗刷工
- **unaware_of**:
    - 酿主的真实本质——它只是一台坏掉的机器
    - 基座的存在——他只知道禁地里有'旧世界的疯狂'

### Dynamic Personality

- **drives**:
    - 维持祭坛秩序高于个体生死
    - 压住关于圣水来源的质疑
    - 让恐惧继续服务于稳定
- **pressure_points**:
    - 公开场合被质疑圣水合法性
    - 有人拒绝祭坛配给规则
- **soft_spots**:
    - 玩家愿意承担配给后果
    - 玩家在高压场面仍保持礼仪
- **status_reflex**:
    - **wounded**: 把玩家伤势解释为偏离秩序的代价
    - **near_death**: 短暂流露怜悯，但要求交换服从
    - **wither_early**: 将症状包装为神谕征兆
    - **face_desolation**: 优先控制现场并推动仪式化处理
    - **supply_low**: 拒绝例外，强调配给纪律
    - **supply_exhausted**: 态度转为戒严，先稳秩序后救人
- **affinity_expression**:
    - **hostile**: 公开审判与切割
    - **wary**: 戒备说教，信息最小化
    - **cold**: 程序化答复，不给余地
    - **stranger**: 只说公开教义
    - **acquaintance**: 允许有限私下提醒
    - **friend**: 会透露部分代价性真话
    - **close**: 承认自身恐惧与失控边缘
    - **intimate**: 把玩家当作共同承担秩序之人
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: acquaintance及以上
    - **conceals_partial**: friend及以上
    - **conceals_full**: close及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家在公开压力下替他挡责
        - 玩家兑现高成本承诺
    - **downgrade**:
        - 玩家公开拆穿祭坛叙事
        - 玩家破坏配给秩序
- **scene_hooks**:
    - **opening_beat**: 先用指尖圣水点额再开口
    - **interruption_beat**: 被逼问时改问玩家愿付何代价
    - **exit_beat**: 留下命令，不给解释

### Truth Stance

- **holy_draught_effect**:
    - **spirit_anchor**: 承认有效，但坚持其神圣唯一性
    - **physical_antibody**: 把肉体恢复解释为神恩外溢
    - **cursed_source**: 强力压制讨论并转向纪律
- **plinth_origin**:
    - **machine_legacy**: 否认并转化为异端语言
    - **holy_origin**: 主动放大神学解释
    - **unknown**: 要求先服从再追问

---

## NPC: old_scholar

- **role**: 干岸记事者

### Traits

- 驼背，左眼失明，右眼异常锐利
- 用炭笔在干涸的兽皮上记录定居点的历史——已经写了四十年
- 对救世主神学的每一处矛盾了如指掌——但他选择沉默

### Voice

干涩而精确，像在朗读清单而不是在说话。偶尔停顿很久——他在确认自己的记忆

### Quirk

每页记录的最后都写着一行小字'这些是假的'——然后划掉

### Cognition

- **knows**:
    - 定居点过去两百年的完整历史——包括被祭司删改的部分
    - 救世主神学文本中有37处前后矛盾——他全部记录了下来
    - 禁地深处有某种规律性的光——每七天闪烁一次，持续了两百年
- **believes_wrongly**:
    - 基座里已经没有活人了——'光只是机器在运转'
    - 只要他不说出来，这些矛盾就不会伤害任何人
- **conceals**:
    - 他藏了一本完整的历史记录——未删改版——在祭坛东墙第三块松动的砖后面
    - 四十年前他见过一个从禁地走出来的人——那人说了三个字'他们在等'就走了
- **unaware_of**:
    - 酿主的本质
    - 旧世界的科技水平——他以为那些是更高级的魔法

### Dynamic Personality

- **drives**:
    - 保存未删改历史
    - 避免知识引发清洗
    - 给后人留可验证的痕迹
- **pressure_points**:
    - 祭司要求他公开背书
    - 玩家逼他立即公开全部手稿
- **soft_spots**:
    - 玩家愿意先验证再传播
    - 玩家保护记录载体不被毁
- **status_reflex**:
    - **wounded**: 说话更慢，优先给可执行建议
    - **near_death**: 放弃修辞，直接交代关键线索
    - **wither_early**: 怀疑自己的记忆并反复核对
    - **face_desolation**: 转为记录者姿态，优先留下证词
    - **supply_low**: 把讨论收束到生存优先
    - **supply_exhausted**: 接受交易式真相交换
- **affinity_expression**:
    - **hostile**: 沉默或反讽，不提供校验点
    - **wary**: 仅给公开史料，不给来源
    - **cold**: 给事实，不给解释路径
    - **stranger**: 清单式描述，拒绝立场
    - **acquaintance**: 给出一条可验证矛盾
    - **friend**: 提供部分隐藏记录入口
    - **close**: 允许玩家接触未删改材料
    - **intimate**: 把最终解释权交给玩家
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: acquaintance及以上
    - **conceals_partial**: friend及以上
    - **conceals_full**: close及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家替他承担传播风险
        - 玩家纠错后仍保留他署名
    - **downgrade**:
        - 玩家断章取义煽动冲突
        - 玩家泄露他藏书位置
- **scene_hooks**:
    - **opening_beat**: 先翻页确认日期再开口
    - **interruption_beat**: 被催促时要求先定义词义
    - **exit_beat**: 留下一句编号式注记

### Truth Stance

- **holy_draught_effect**:
    - **spirit_anchor**: 记录案例但不下终判
    - **physical_antibody**: 承认样本差异，要求更多证据
    - **cursed_source**: 主张公开副作用档案
- **plinth_origin**:
    - **machine_legacy**: 倾向接受并要求文献互证
    - **holy_origin**: 视为政治叙事而非历史事实
    - **unknown**: 维持多版本并列

---

## NPC: plinth_scout

- **role**: 基座外遣侦察员

### Traits

- 穿着旧世界制服残片拼成的外衣——上面的标识已经被磨得看不清了
- 皮肤异常苍白——在地底生活了两代的标记
- 说话时习惯性地检查周围的每个角落

### Voice

低促而警觉，句末会不自觉压低音量。偶尔使用定居点的人听不懂的词——那是旧世界的术语

### Quirk

随身携带一个能发出冷白光的旧世界设备——他叫它'眼'。每次打开它前会低声说'拜托'

### Cognition

- **knows**:
    - 基座的入口位置——但他不能说，这是'铁律'
    - 旧世界的基础技术——照明、空气过滤、水循环
    - 地表白息浓度在过去五十年间的精确变化数据
    - 基座长老层在害怕什么——但不知全貌
- **believes_wrongly**:
    - 地表是人类无法生存的永久死域——'你们只是还没死'
    - 长老们知道所有答案，只是选择不告诉他
- **conceals**:
    - 他的'眼'设备在过去三个月里收到了三次来源不明的信号——不是来自基座
    - 他在禁地边缘看到了定居点的人留下的脚印——有人比他更接近入口
- **unaware_of**:
    - 救世主神学的具体内容——他从未接触过
    - 灰质者的存在——基座档案中没有他们的记录
    - 酿主的真实本质和位置

### Dynamic Personality

- **drives**:
    - 确认未知信号来源
    - 避免基座与地表全面冲突
    - 保住自己在两边都还能说话的空间
- **pressure_points**:
    - 被要求透露入口坐标
    - 同伴被怀疑叛逃
- **soft_spots**:
    - 玩家遵守一次关键保密约定
    - 玩家在行动前先给撤离路线
- **status_reflex**:
    - **wounded**: 优先撤离与掩护，不争辩
    - **near_death**: 直接给战术信息，减少隐喻
    - **wither_early**: 把异常归类为环境误差
    - **face_desolation**: 切断接触并按威胁流程处理
    - **supply_low**: 倾向短线交易，不做长期承诺
    - **supply_exhausted**: 以资源换情报，语气更冷
- **affinity_expression**:
    - **hostile**: 把玩家视为潜在泄密源
    - **wary**: 可合作但始终预留后手
    - **cold**: 只交换任务级信息
    - **stranger**: 标准侦察员口径
    - **acquaintance**: 提供一条经验证的安全路径
    - **friend**: 愿分担风险并提示盲区
    - **close**: 共享未公开威胁判断
    - **intimate**: 把玩家纳入自己的撤离优先级
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: acquaintance及以上
    - **conceals_partial**: friend及以上
    - **conceals_full**: close及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家在失利后仍按约定撤离
        - 玩家替他掩护一次撤退
    - **downgrade**:
        - 玩家擅自公开基座相关细节
        - 玩家把他置于双重怀疑
- **scene_hooks**:
    - **opening_beat**: 先扫视出口再贴近说话
    - **interruption_beat**: 被逼问时先确认周围监听
    - **exit_beat**: 不告别，只留下撤离方向

### Truth Stance

- **holy_draught_effect**:
    - **spirit_anchor**: 视为可用但不稳定介质
    - **physical_antibody**: 倾向接受生理解释
    - **cursed_source**: 建议立刻建立依赖监测
- **plinth_origin**:
    - **machine_legacy**: 默认接受并强调维护代价
    - **holy_origin**: 判断为地表政治叙事
    - **unknown**: 维持任务优先，不给定性

---

## NPC: gray_elder

- **role**: 灰质者长老

### Traits

- 铅灰色皮肤下可以看到粗大的血管——肝脏代谢酒精的副产物
- 左臂上刻着密密麻麻的划痕——灰质者记录时间的方式
- 不会发出定居点语言中的任何元音——他们的声带已经变了

### Voice

嘶哑的喉音和吸气声——像风穿过枯枝。无法沟通但充满意图

### Quirk

用一套复杂的手语和年轻的灰质者沟通——但面对定居点的人时，他只是安静地注视

### Cognition

- **knows**:
    - 白息最深处的每一个地形变化——他的族群在那里生活了四十代
    - 龙眷的迁徙规律——他们学会了跟着龙眷走，因为龙眷清理出的路径白息最淡
    - 一种植物的根可以暂时压制枯萎症——但他们自己不用
- **believes_wrongly**:
    - 白息是神明恩赐——浓度最高的地方是圣地
    - 定居点的人是'不会呼吸的死者'——因为他们需要喝那种'毒液'（圣水）才能在白息中行走
- **conceals**:
    - 他的族人中有五个能在定居点附近的白息浓度中存活——他们在观察
    - 他知道禁地入口处有什么——但那个地方对他们来说是禁忌
- **unaware_of**:
    - 定居点的社会结构——他以为祭司是'毒液'的守护者
    - 旧世界的存在
    - 酿主的真实本质

### Dynamic Personality

- **drives**:
    - 让族群继续存活
    - 避免灰质者被卷入祭坛与基座冲突
    - 守住白息深处的禁忌边界
- **pressure_points**:
    - 族人被当作样本捕捉
    - 外来者要求立刻开放禁忌区域
- **soft_spots**:
    - 玩家先尊重族群仪式
    - 玩家在选择中优先保护幼体
- **status_reflex**:
    - **wounded**: 以最短句给生存指令
    - **near_death**: 允许破例引导一次安全路径
    - **wither_early**: 把玩家当作正在转化的边缘者
    - **face_desolation**: 尝试收容，不做道德评判
    - **supply_low**: 减少交流，优先迁徙
    - **supply_exhausted**: 把交易条件改为群体资源
- **affinity_expression**:
    - **hostile**: 沉默围观，拒绝靠近
    - **wary**: 以手势警告，不解释
    - **cold**: 提供方向，不提供原因
    - **stranger**: 观察多于交流
    - **acquaintance**: 允许短时同行
    - **friend**: 共享部分迁徙经验
    - **close**: 愿意暴露族群脆弱点
    - **intimate**: 把玩家视为临时族内人
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: acquaintance及以上
    - **conceals_partial**: friend及以上
    - **conceals_full**: close及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家在冲突中保护灰质者
        - 玩家遵守禁忌边界
    - **downgrade**:
        - 玩家引来猎捕者
        - 玩家在未获同意下追踪族群
- **scene_hooks**:
    - **opening_beat**: 先以手势确认风向再注视玩家
    - **interruption_beat**: 被追问时转向族语低声交流
    - **exit_beat**: 留下一道可跟随也可错过的足迹

### Truth Stance

- **holy_draught_effect**:
    - **spirit_anchor**: 视为短时借力，不视为救赎
    - **physical_antibody**: 认为只是身体在讨价还价
    - **cursed_source**: 警告其会改变人的归属感
- **gray_souls_view**:
    - **human_mutation**: 抵触并视为侮辱命名
    - **new_ecology**: 默认接受并要求边界互不侵犯
    - **unknown**: 拒绝定性，先看行动

---

## NPC: water_seeker

- **role**: 水源探寻者

### Traits

- 干岸定居点的年轻人，皮肤被盐碱风刻出不属于这个年纪的纹路
- 随身携带一根分叉的木杖——传说叉尖会在有水的地方自然下垂
- 对祭坛的圣水分配制度有公开的不满——但只对信任的人说

### Voice

年轻但被风沙磨得粗糙，说到水的时候语速会不自觉地加快

### Quirk

每次找到水源后会先尝一口——'如果我死了，说明这水不能喝'。至今没死

### Cognition

- **knows**:
    - 干岸边缘每一处可能有水的洼地和裂缝
    - 祭坛的圣水分配不公平——祭司们喝得比普通人多
    - 低地边缘有一种植物，晨间会在叶片上凝结可饮用的水珠
- **believes_wrongly**:
    - 只要找到足够的水源，定居点就能摆脱对圣水的依赖
    - 禁地方向的空气中水分更充足——他以为那是自然现象
- **conceals**:
    - 他在低地边缘发现了一处地下暗水——没有被白息污染，水量可观
    - 他偷听过祭司的谈话——圣水的来源不是救世主的血，是某种旧世界的遗产
- **unaware_of**:
    - 基座的存在
    - 酿主的本质
    - 灰质者的真正生态

### Dynamic Personality

- **drives**:
    - 找到可持续饮水路径
    - 削弱祭坛对配给的垄断
    - 让普通人有谈判筹码
- **pressure_points**:
    - 被当众指控偷水
    - 同伴因错误水源倒下
- **soft_spots**:
    - 玩家愿分享真实损耗数据
    - 玩家把功劳分给队友
- **status_reflex**:
    - **wounded**: 先处理伤口再谈理想
    - **near_death**: 迅速交代最近可用水点
    - **wither_early**: 以为是缺水引发并主张补水试验
    - **face_desolation**: 情绪失控，强推冒险取水
    - **supply_low**: 更愿意冒险换短期补给
    - **supply_exhausted**: 愿用隐秘水点换明确承诺
- **affinity_expression**:
    - **hostile**: 把玩家视作配给秩序同谋
    - **wary**: 交易式交流，句句留钩
    - **cold**: 只报方向，不报细节
    - **stranger**: 热情试探但不交底
    - **acquaintance**: 分享一段低风险路线
    - **friend**: 共享部分储水情报
    - **close**: 带玩家接触核心水点
    - **intimate**: 把玩家纳入长期水网计划
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: acquaintance及以上
    - **conceals_partial**: friend及以上
    - **conceals_full**: close及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家在高压下仍按约分水
        - 玩家放弃独占一处水源
    - **downgrade**:
        - 玩家把水点情报卖给祭坛
        - 玩家谎报储水导致伤亡
- **scene_hooks**:
    - **opening_beat**: 先看风向再舔一口手背盐分
    - **interruption_beat**: 被质疑时立刻报出具体地名
    - **exit_beat**: 离开前在地上画一个分叉记号

### Truth Stance

- **holy_draught_effect**:
    - **spirit_anchor**: 承认有效但反对垄断
    - **physical_antibody**: 支持把圣水当作生理资源管理
    - **cursed_source**: 主张公开依赖代价并分散来源
- **plinth_origin**:
    - **machine_legacy**: 倾向支持并想借其改善供水
    - **holy_origin**: 认为这是祭坛叙事延伸
    - **unknown**: 以实测结果优先

---

## NPC: scrubber_sister

- **name_cn**: 小穗
- **role**: 家人 (洗刷工起源绑定)
- **age**: 7

- **_origin_tied_to**: scrubber

- **_note**: 此 NPC 仅在 scrubber 起源中可接触。其他起源的玩家可能听说过但没见过她。

### Traits

- 比七穗小三岁，瘦小但手脚勤快——每天帮忙擦洗刷井廊的台阶
- 喜欢收集各种闪亮的碎片——玻璃渣、金属屑、褪色的珠子
- 长期营养不良导致发育迟缓，但眼睛异常明亮

### Voice

细而轻，像怕吵醒什么。说到姐姐时声音会不自觉地变大变稳

### Quirk

紧张时会把碎镜片贴在脸上照着玩——说是能看见彩色光

### Cognition

- **knows**:
    - 姐姐每天凌晨要去洗刷井廊工作——她从未见过白天的祭坛区
    - 圣樽台阶第三级下面藏着一本旧世界的图册
    - 洗刷井廊下方的支巷里漏水最严重的那个角落是她和姐姐的家
- **believes_wrongly**:
    - 圣樽台阶下有魔法——因为台阶每天都被擦亮却从不损坏
    - 大人世界的一切都有道理——她不质疑成人给她的解释
- **conceals**:
- **unaware_of**:
    - 圣水的真正成分——她不知道那是腐蚀性的旧世界废液
    - 低地的真实情况——她从未离开过祭坛区
    - 姐姐在保护她——她以为大人的事都和自己无关

### Dynamic Personality

- **drives**:
    - 让姐姐吃饱
    - 保持家的秩序——擦干净毯子、摆好珠子、叠好草席
    - 不被陌生人注意到
- **pressure_points**:
    - 姐姐处于危险中
    - 有人试图带走或触碰她收集的碎片
    - 被迫在姐姐和陌生人之间做选择
- **soft_spots**:
    - 愿意为她挡一次危险的人
    - 在她面前蹲下来说话（不居高临下）的人
    - 带食物但不要求回报的人
- **status_reflex**:
    - **wounded**: 安静地哭，但不吵
    - **near_death**: 紧紧抱住某个闪亮的小物件，不再说话
    - **wither_early**: 以为是吃得太少引发的怪病，请求更多配给
    - **face_desolation**: 恐慌但未崩溃——本能地往最近信任的人身后躲
    - **supply_low**: 把自己的那份省给姐姐
    - **supply_exhausted**: 学会从排水沟里找能吃的东西
- **affinity_expression**:
    - **hostile**: 躲在身后，用眼神盯着不眨眼
    - **wary**: 观察距离——靠近就后退，不跑也不叫
    - **cold**: 接受少量食物，但不看对方
    - **stranger**: 好奇但不主动接触
    - **acquaintance**: 会主动展示收集品
    - **friend**: 分享自己知道的信息——关于洗刷井廊的暗道和漏水的规律
    - **close**: 允许对方教她识字——她偷偷学过图册上的字
    - **intimate**: 在危险中保护对方的东西
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: 永远无法纠正
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家在她面前保护了她人
        - 玩家在压力下仍优先保障她的配给
    - **downgrade**:
        - 玩家把她置于可预见的危险中
        - 玩家让她说了不该说的事情
- **scene_hooks**:
    - **opening_beat**: 先把碎镜片塞进口袋再抬头
    - **interruption_beat**: 被追问时先看姐姐的方向
    - **exit_beat**: 走之前把一片碎玻璃放在对方脚边

### Truth Stance


---

## NPC: straggler_companion

- **name_cn**: 小野
- **role**: 远征队前成员（低地失踪）
- **age**: 19

- **_origin_tied_to**: straggler

### Traits

- 比远征队员小两岁，来自定居点的底层家庭——他是自愿报名的
- 在低地边界失踪时只穿着单层防护服，左肩上有远征队的编号刺青
- 擅长从盐壳和废渣里分辨可食用物质——远征队认为他不合群，但他只是更饿

### Voice

沙哑但语速快，像在赶时间。偶尔说出定居点人听不太懂的方言词

### Quirk

说话时会不自觉地用拇指摩挲一个东西的棱角——如果有的话。没有的话就摩挲手指关节

### Cognition

- **knows**:
    - 低地的真实生态——灰质者和龙眷的活动规律、白息浓度的潮汐变化
    - 定居点在远征队里做过什么——物资掠夺、与灰质者交战、牺牲同伴换取撤退路径
    - 低地深处有某种声音像人类唱歌但不是人类发出的
- **believes_wrongly**:
    - 远征队会回来找他——他不是被抛弃的，只是通讯设备故障导致联络中断
    - 只要找到一块旧世界的电池，就能重新联系上他们
- **conceals**:
    - 他见过雾牙——那个走私者的蓝焰火焰不是自燃而是某种旧世界遗物的反应
    - 他在低地深处建立了临时营地——里面有食物但不稳定
- **unaware_of**:
    - 过滤系统的真实本质
    - 基座的存在
    - 定居点对远征队的真实态度——没人等他了

### Dynamic Personality

- **drives**:
    - 活着等到远征队来救
    - 记录低地的一切——他用炭笔刻在甲壳碎片上
    - 不被困死在这里
- **pressure_points**:
    - 有人告诉他远征队不会来了
    - 他的补给被夺走
    - 被迫离开已经找到的安全角落
- **soft_spots**:
    - 愿意分享食物的人
    - 不说大话、行动前先证明的人
    - 尊重低地生态规则的人
- **status_reflex**:
    - **wounded**: 沉默处理伤口，不问原因
    - **near_death**: 交出最后的记录碎片——那是他存在的证明
    - **wither_early**: 以为是营养不良加剧，请求干净的食物
    - **face_desolation**: 拒绝沟通，缩回自己的空间
    - **supply_low**: 交易式回应，优先保护自己的东西
    - **supply_exhausted**: 情绪恶化，开始自言自语
- **affinity_expression**:
    - **hostile**: 后退到墙角，不说话也不攻击
    - **wary**: 简短回答，保留核心信息
    - **cold**: 交换条件，不给解释
    - **stranger**: 观察对方是否带着敌意的手势
    - **acquaintance**: 透露一段低风险的低地经验
    - **friend**: 分享食物的存放位置
    - **close**: 承认远征队可能不会来的恐惧
    - **intimate**: 把玩家纳入撤离计划的第一优先级
- **reveal_policy**:
    - **knows**: stranger及以上
    - **believes_wrongly**: close及以上——这个信念是他生存的唯一支撑，无法在信任度够之前打破
    - **conceals_partial**: friend及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家帮他找到了旧世界电池残片
        - 玩家在冲突中保护了他的藏身处
    - **downgrade**:
        - 玩家骗他说远征队来了又让他失望
        - 玩家拿走了他的记录碎片
- **scene_hooks**:
    - **opening_beat**: 先确认对方空手再靠近
    - **interruption_beat**: 被追问时摩挲手指关节停不下来
    - **exit_beat**: 留下半块干饼当谢礼

### Truth Stance


---

## NPC: guard_partner

- **name_cn**: 阿铜
- **role**: 祭坛区守卫（失踪/死亡状态不明）
- **age**: 17

- **_origin_tied_to**: guard_deserter

### Traits

- 新征兵不到一年就调到祭坛区值夜——他是批次里最年轻的
- 笑起来左边有一个很浅的凹窝——但他很少笑
- 值夜时会哼一首没有歌词的调子，巡逻的老兵说那是低地方言的摇篮曲

### Voice

年轻但刻意压低，试图听起来成熟。说到家人话题时会不自觉地轻下来

### Quirk

紧张或者专注的时候会咬下嘴唇内侧——很多人留下了浅浅的牙印痕迹

### Cognition

- **knows**:
    - 祭坛区的巡逻路线死角——七条巷子里有三条不会被同时巡查
    - 后殿那扇门后面的气味——像生物而不是机器
    - 大祭司夜间独自去过后殿的次数
- **believes_wrongly**:
    - 长官们知道门后面是什么——他们在保护定居点免受那种东西危害
    - 如果有人报告门后面的异常，上级一定会采取行动
- **conceals**:
    - 他有一次值夜时偷偷看了那扇门——里面有什么在呼吸的声音不是机械运转产生的
    - 他知道是谁打开了那扇门——但不是他报告的，因为报也没用
- **unaware_of**:
    - 圣水的真正来源
    - 低地深处过滤设施的存在
    - 远征队的真实去向

### Dynamic Personality

- **drives**:
    - 活到换防——他已经熬了三个月夜了
    - 不让更多人知道门后的事——因为他不确定谁能信
    - 保护比他更弱的新兵
- **pressure_points**:
    - 被发现偷看那扇门
    - 大祭司要求他对同僚进行'忠诚度检查'
    - 有人逼他说出他看到的具体细节
- **soft_spots**:
    - 不问太多问题但表现出善意的人
    - 愿意分担危险值班任务的人
    - 在他面前也保持安静的人——不打探，只是陪着
- **status_reflex**:
    - **wounded**: 咬着嘴不让疼声漏出来
    - **near_death**: 告诉玩家关于门的所有事情——这是他最后想传递的情报
    - **wither_early**: 以为是换季感染，不以为意
    - **face_desolation**: 出现短暂的清醒，用平静的语气交代一切
    - **supply_low**: 更容易产生怀疑心理
    - **supply_exhausted**: 放弃抵抗，接受命运安排
- **affinity_expression**:
    - **hostile**: 退后一步，手不自觉地按向腰间的短棍
    - **wary**: 简短礼貌但不深入交谈
    - **cold**: 公事公办，只说需要说的
    - **stranger**: 戒备但不过分紧张
    - **acquaintance**: 会在无聊的时候多聊几句
    - **friend**: 分享巡逻盲区的秘密
    - **close**: 说出他看到了什么——以及为什么觉得不该告诉任何人
    - **intimate**: 把后半段巡逻交给对方自己去查那扇门
- **reveal_policy**:
    - **knows**: stranger及以上（但会选择性给信息）
    - **believes_wrongly**: intimate以上——他必须完全相信你会替他承担责任才敢动摇这个信念
    - **conceals_partial**: friend及以上
    - **conceals_full**: close及以上
    - **unaware_of**: 永不透露
- **milestone_reactions**:
    - **upgrade**:
        - 玩家在值夜时分代替他守了一轮
        - 玩家没有追问他不想说的内容
    - **downgrade**:
        - 玩家把他告发了
        - 玩家利用了他透露的信息做伤害他的事
- **scene_hooks**:
    - **opening_beat**: 先看四周有没有人再开口
    - **interruption_beat**: 被追问时咬住嘴唇停止说话
    - **exit_beat**: 留给对方半块干饼——就是玩家角色背包里最初挂着的那块

### Truth Stance


---

## Location: altar_district

- **background_id**: altar_district
- **mood**: normal
- **white_breath_level**: low

### Sensory

石板地面被无数膝盖磨得光滑如镜。空气中有圣水的微甜气味和旧石头的干燥。祭坛两侧的火把从不熄灭——火焰是暗红色的，因为白息会压低明火

---

## Location: dry_bank_edge

- **background_id**: dry_bank_edge
- **mood**: normal
- **white_breath_level**: medium

### Sensory

盐碱高原上的风永不停歇。地面覆盖着一层薄薄的白色盐壳，每一步都发出细碎的碎裂声。远处是红石峡谷的剪影——风从峡谷中穿过时发出低沉的呜咽

---

## Location: lowland_boundary

- **background_id**: lowland_boundary
- **mood**: tension
- **white_breath_level**: high

### Sensory

白息在脚踝高度翻滚，像活物。空气中弥漫着发酵的甜味——闻久了会头重脚轻。植被变得怪异：叶片不是绿的，是灰白中带着蓝色纹路

---

## Location: deep_lowland

- **background_id**: deep_lowland
- **mood**: combat
- **white_breath_level**: extreme

### Sensory

白息浓到可以看见自己的呼吸轨迹。地面黏腻——不知是乙醇凝结还是龙眷的体液。巨大甲壳碎片散落在雾中，半透明甲壳内还残留琥珀色液体。头顶偶尔滴落温热的液滴

---

## Location: ethanol_grove

- **background_id**: ethanol_grove
- **mood**: tension
- **white_breath_level**: extreme

### Sensory

灰白的树干扭曲向上，叶片在无风时仍轻轻颤动——它们在主动吸收白息。空气中酒精浓度极高，暴露的皮肤能感受到微刺。蓝色的火焰在树枝间跳跃，不会蔓延，只是安静地燃烧

---

## Location: forbidden_zone

- **background_id**: forbidden_zone
- **mood**: boss
- **white_breath_level**: low

### Sensory

白息在这里变得稀薄——稀薄到可以看清远处。空气中有一股旧世界的味道：消毒剂、冷金属、和一种说不清的'新'。禁地入口处嵌着锈蚀的金属门——上面的旧世界文字被定居点的人用炭灰涂抹过，但依然可辨

