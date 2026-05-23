#!/usr/bin/env python3
"""Build shared background library — 90 images with visual motif categories.

Phase 1: submit all 90 tasks via _do_submit (goes to active world dir)
Phase 2: poll until all complete
Phase 3: migrate images to _shared/backgrounds/ and write backgrounds.json

Usage:
  python tools/build_shared_library.py --dry-run    Preview manifest + registry
  python tools/build_shared_library.py              Full build
  python tools/build_shared_library.py --phase migrate   Only run migration
"""

import json
import os
import sys
import shutil
import time
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bg import _do_submit, _auto_poll, _load_pending, _install_image

STYLE = (
    "dark fantasy concept art, atmospheric ruins shrouded in toxic mist, "
    "muted earth tones with rust accents, painterly brushwork, "
    "somber and haunting mood"
)

# ═══════════════════════════════════════════════════════════════
# 90-image manifest (file_id, category, subcategory, prompt_cn)
# ═══════════════════════════════════════════════════════════════

MANIFEST = [
    # ═══ 一、基础环境：荒野与自然 (01-25) ═══
    ("01_mist_forest",     "locations", "forest",     "迷雾森林深处，古木参天，浓雾弥漫，苔藓覆盖的根系交错，幽暗的散射光穿透树冠"),
    ("02_dead_woods",      "locations", "forest",     "枯萎的焦黑林地，碳化的树干扭曲向天，地面覆盖灰烬，残余的火星在焦土上闪烁"),
    ("03_giant_roots",     "locations", "forest",     "参天巨树的根部，像大教堂的拱顶般向上延伸，根系间透出微弱的荧光，渺小的人物尺度对比"),
    ("04_glow_fungi",      "locations", "forest",     "幽蓝荧光菌类丛林，巨大的发光蘑菇在黑暗中排列，孢子悬浮在空中如星尘"),
    ("05_leaf_path",       "locations", "forest",     "落叶堆积的林间小径，秋色浓郁，阳光透过黄叶缝隙洒在泥土路上，静谧而孤寂"),
    ("06_gobi_plain",      "locations", "wasteland",  "无际的戈壁平原，碎石与枯草铺向地平线，天空低垂，孤零零的枯树立在远方"),
    ("07_bone_field",      "locations", "wasteland",  "铺满骸骨的荒野，巨大肋骨从沙土中伸出如拱门，风吹过骨隙发出低啸"),
    ("08_cracked_lake",    "locations", "wasteland",  "龟裂的干涸湖底，裂纹如蛛网般延伸至天边，盐碱白霜镶在裂缝边缘"),
    ("09_sand_dune",       "locations", "wasteland",  "漫天黄沙的沙丘，风暴在远方酝酿，沙粒在低角度光线下呈现金色曲线"),
    ("10_crater_rim",      "locations", "wasteland",  "巨大的陨石坑边缘，下方是沸腾的暗色玻璃状熔岩，边缘的岩层暴露如年轮"),
    ("11_dark_swamp",      "locations", "water",      "墨色死寂的沼泽，黑色水面倒映枯死的柏树，雾气贴在水面上方半米处"),
    ("12_storm_reef",      "locations", "water",      "暴雨中的海岸礁石，灰色海浪猛烈撞击黑色火山岩，飞溅的水沫混入雨幕"),
    ("13_frozen_lake",     "locations", "water",      "冻结的冰封湖面，冰层下困着气泡和暗色物体轮廓，远处有破碎的冰脊"),
    ("14_underground_river","locations", "water",     "地底暗河的入口，钟乳石如巨齿垂向水面，手电光束消失在无尽的黑暗中"),
    ("15_waterfall_cliff", "locations", "water",      "奔腾的瀑布从断崖倾泻，水雾在阳光下形成双彩虹，下方深潭幽不见底"),
    ("16_snow_ridge",      "locations", "mountain",   "终年积雪的山脊，风吹起的雪粒在阳光下闪烁，裸露的黑色岩石形成锐利剪影"),
    ("17_red_canyon",      "locations", "mountain",   "陡峭的红岩峡谷，岩壁纹理如刀削，谷底河流干涸成一条蜿蜒的暗色痕迹"),
    ("18_stone_stairs",    "locations", "mountain",   "通往云端的石阶，沿峭壁凿出的阶梯消失在雾气中，护栏早已风化坍塌"),
    ("19_lava_flow",       "locations", "mountain",   "喷发后的火山熔岩流，缓慢移动的暗红岩浆吞噬沿途一切，冷却的边缘形成黑色褶皱"),
    ("20_cloud_valley",    "locations", "mountain",   "被云雾遮蔽的山谷，云海如棉絮铺满山谷，只有最高峰穿出云层如孤岛"),
    ("21_aurora_sky",      "locations", "sky",        "极光笼罩的夜空，绿色和紫色的光帘从高空垂下，在雪地投下变幻的彩色倒影"),
    ("22_crimson_dusk",    "locations", "sky",        "血红色的黄昏，暗云如烧伤般铺展半个天空，余晖给所有轮廓镀上暗红边缘"),
    ("23_lead_clouds",     "locations", "sky",        "铅灰色的雷雨云压向地面，闪电沉默地在云团内部闪烁，远处雨幕已开始倾泻"),
    ("24_twin_moons",      "locations", "sky",        "双月同天的异界星空，大小两个月亮一蓝一白悬于星海，地面笼罩在诡异的双色月光中"),
    ("25_void_rift",       "locations", "sky",        "扭曲的虚空裂缝撕裂天空，裂缝边缘空间褶皱可见，异色的光从裂缝中渗出"),
    # ═══ 城镇与遗迹 (26-45) ═══
    ("26_neon_alley",      "locations", "street",     "雨后霓虹映照的巷弄，水洼反射着粉紫蓝三色灯光，蒸汽从下水道格栅升起"),
    ("27_stone_road",      "locations", "street",     "中世纪风格的石板路，卵石被岁月磨得光滑，两侧木筋建筑倾斜相向"),
    ("28_abandoned_road",  "locations", "street",     "满是废弃车辆的干道，锈蚀车壳半埋在沙土中，挡风玻璃反射着荒芜的天空"),
    ("29_overgrown_mall",  "locations", "street",     "被植物覆盖的商业街，藤蔓从破碎橱窗中涌出，树根撑裂了柏油路面"),
    ("30_lantern_market",  "locations", "street",     "挂满灯笼的集市，红光穿透纸灯笼投射在石板地面，摊位上堆满未知货物"),
    ("31_collapsed_cathedral","locations","ruin",     "坍塌的大教堂遗迹，残存的高耸拱顶向天空敞开，阳光从破碎的玫瑰窗倾泻"),
    ("32_rust_steel",      "locations", "ruin",       "锈迹斑斑的钢铁架构，废弃工厂的骨架在夕阳下呈现红棕剪影，螺栓四散"),
    ("33_sunken_city",     "locations", "ruin",       "沉入水底的城市废墟，楼宇轮廓在昏暗水下模糊可见，水藻在破碎窗户间飘荡"),
    ("34_sand_tower",      "locations", "ruin",       "被风沙掩埋的半截高塔，塔身斜插入沙丘，裸露部分的窗口仍有幽光"),
    ("35_broken_statues",  "locations", "ruin",       "破碎的巨型石像阵，半张脸埋在土里的石制巨首，空洞的眼窝仰望天空"),
    ("36_cliff_lighthouse","locations", "exterior",   "悬崖边的孤独灯塔，海浪在下方撞击，灯塔旋转的光束穿透海上浓雾"),
    ("37_fortress_gate",   "locations", "exterior",   "戒备森严的要塞大门，厚重的铁闸门密布铆钉，城墙上火把摇曳"),
    ("38_floating_island", "locations", "exterior",   "漂浮在空中的破碎孤岛，大块岩石违反重力悬于云端，岛底根系垂下"),
    ("39_buried_lab",      "locations", "exterior",   "半掩在土里的生化实验室，混凝土外壳开裂暴露内部管线，警示标志仍隐约可见"),
    ("40_decayed_manor",   "locations", "exterior",   "破败的乡村庄园，窗户像空洞的眼眶，枯藤爬满门廊，风掀起破损的窗帘"),
    ("41_open_mine",       "locations", "industrial", "废弃的露天矿场，巨大的螺旋车道通向坑底，底部积水在黑暗中反光"),
    ("42_rust_station",    "locations", "industrial", "锈蚀的火车站台，钟表停在某个时刻，铁轨消失在杂草丛中"),
    ("43_ancient_altar",   "locations", "industrial", "古老的祭祀祭坛，石制祭台布满干涸的暗色液痕，环绕的烛台早已熄灭"),
    ("44_satellite_dish",  "locations", "industrial", "巨大的卫星天线残骸，抛物面倾斜指向地面而非天空，周围野草比人还高"),
    ("45_broken_bridge",   "locations", "industrial", "断裂的跨海大桥，悬索斜挂在半空，桥面在某处戛然而止，下方海浪翻涌"),
    # ═══ 室内与地底 (46-60) ═══
    ("46_dim_tavern",      "locations", "interior",   "昏暗的酒馆柜台，酒杯倒映着壁炉的暖光，角落的阴影比别处更深"),
    ("47_old_library",     "locations", "interior",   "堆满旧书的图书馆一角，通天高的书架从地面延伸到拱顶，浮尘在光柱中飘浮"),
    ("48_leaky_apartment", "locations", "interior",   "漏雨的破旧公寓房间，水珠从天花板裂缝滴落进铁桶，墙纸大片剥落"),
    ("49_dusty_banquet",   "locations", "interior",   "豪华但落满灰尘的宴会厅，水晶吊灯歪斜挂着，餐桌上仍摆着未完成的盛宴"),
    ("50_alchemy_lab",     "locations", "interior",   "摆满试剂瓶的炼金实验室，五颜六色的液体在玻璃管中沸腾，蒸馏器滴答作响"),
    ("51_underground_pipes","locations","interior",   "纵横交错的地下管道，阀门和压力表布满墙面的迷宫，积水在管壁凝结滴落"),
    ("52_stone_tomb",      "locations", "interior",   "幽闭的石棺墓室，石棺沿两侧延伸至黑暗中，壁灯的火苗微弱跳动"),
    ("53_scrap_warehouse", "locations", "interior",   "堆满废铁的仓库，金属构件一直堆到天花板，狭窄通道仅容一人侧身通过"),
    ("54_interrogation",   "locations", "interior",   "只有一盏孤灯的审讯室，铁椅固定在水泥地上，墙上有模糊的抓痕"),
    ("55_giant_gears",     "locations", "interior",   "运作中的巨型齿轮组，齿轮啮合碾过画面，机油和水汽混合成雾气"),
    ("56_energy_conduits", "locations", "interior",   "充满能量管线的机房，幽蓝冷光沿管线流动，过载的变压器迸发电弧"),
    ("57_rune_chamber",    "locations", "interior",   "刻满符文的传送阵大厅，地面凹槽中符文以某种节奏明灭，天花板高不可见"),
    ("58_cryo_pods",       "locations", "interior",   "低温休眠舱陈列室，成排的玻璃罩内空无一人，少数覆盖着厚霜看不清内部"),
    ("59_giant_cage",      "locations", "interior",   "囚禁巨大生物的铁笼，笼栏粗如树干，地面有巨大的爪痕，角落里传出低沉呼吸"),
    ("60_bone_corridor",   "locations", "interior",   "无尽延伸的白骨长廊，墙壁全由骨骼堆砌，在暗光中向前无限延伸"),
    # ═══ 二、叙事节拍：战斗 (61-70) ═══
    ("61_spark_clash",     "narrative", "combat_narr","刀剑交错的火星特写慢镜头，兵器在空中碰撞，每一颗火星都清晰可见"),
    ("62_shell_casings",   "narrative", "combat_narr","满地的空弹壳与硝烟，弹壳在水泥地上散落如星，烟雾在低角度逆光中缓缓上升"),
    ("63_peek_cover",      "narrative", "combat_narr","视角从倒塌的掩体后向外窥视，前景是破碎的砖石，远处模糊的威胁正在靠近"),
    ("64_broken_shield",   "narrative", "combat_narr","破碎的盾牌斜插在泥土里，断箭和撕破的布条挂在边缘，雨水模糊了盾面纹章"),
    ("65_blood_banner",    "narrative", "combat_narr","被鲜血染红的旗帜在风中挣扎，旗面只剩残破的一半，旗杆倾斜即将倒下"),
    ("66_target_lock",     "narrative", "combat_narr","瞄准镜十字线里的模糊人影逆光站立，呼吸凝结成的白雾在镜片边缘浮现"),
    ("67_burning_camp",    "narrative", "combat_narr","正在燃烧的营帐，火焰吞噬帆布泛出橙红，燃烧的灰烬在夜空中升腾"),
    ("68_cracked_glass",   "narrative", "combat_narr","龟裂的防弹玻璃特写，弹孔如星芒般辐射开裂，玻璃另一侧的世界在裂纹中变形"),
    ("69_broken_supplies", "narrative", "combat_narr","满地破碎的药水瓶与翻倒的补给箱，液体从碎片间流出，绷带散落在血渍中"),
    ("70_army_silhouette", "narrative", "combat_narr","远处地平线上的行军剪影，无数长矛或枪管勾勒出锯齿状轮廓，背景是燃烧的天际线"),
    # ═══ 叙事节拍：探索 (71-80) ═══
    ("71_campfire",        "narrative", "expl_narr",  "篝火旁跃动的火焰特写，火星螺旋上升，火焰在夜晚的深蓝背景中显得格外温暖"),
    ("72_desk_map",        "narrative", "expl_narr",  "摊开在案头的泛黄地图，羽毛笔斜放在一侧，烛泪滴在地图关键标记上"),
    ("73_locked_gate",     "narrative", "expl_narr",  "紧闭的挂锁铁门特写，粗重的锁链缠绕门闩，铁锈和蛛网覆盖锁孔"),
    ("74_light_into_dark", "narrative", "expl_narr",  "伸向黑暗的唯一光源，火把或手电的光束吞噬于前方无尽的黑暗中，只照亮半米"),
    ("75_dirty_compass",   "narrative", "expl_narr",  "沾满泥土的指南针躺在掌心，玻璃面有裂纹，指针犹豫不决地微微颤动"),
    ("76_empty_chest",     "narrative", "expl_narr",  "被打开的空空如也的宝箱，盖子斜开，内部只有蛛网——但箱底有一道暗门痕迹"),
    ("77_microscope",      "narrative", "expl_narr",  "显微镜下的变异细胞，异常增大的细胞核在目镜视野中微微脉动，染剂呈现诡异的紫色"),
    ("78_gold_vault",      "narrative", "expl_narr",  "堆满金币却透着诡异的秘库，金币散落一地但没有任何虫鼠，死寂中只有金币反射的光芒"),
    ("79_blood_note",      "narrative", "expl_narr",  "一张写满警告的血字纸条，字迹潦草且逐渐增大，最后几个字拖出血痕"),
    ("80_footprints",      "narrative", "expl_narr",  "视角跟随一串脚印延伸向远方，雪地或沙地上的足迹通向地平线上一个微小的人影"),
    # ═══ 三、抽象情绪：状态与氛围 (81-90) ═══
    ("81_black_spread",    "moods",     "oppression", "逐渐蔓延的黑色物质，像柏油般缓慢吞噬白色地面，边缘有微弱的反光"),
    ("82_choking_haze",    "moods",     "oppression", "令人窒息的浓重灰霾，可见度不足十米，远方建筑的轮廓在霾中只剩下模糊形状"),
    ("83_peeping_eyes",    "moods",     "oppression", "无数窥视的瞳孔在黑暗中睁开，大小不一的眼睛占据整个画面，只有瞳孔没有面容"),
    ("84_god_rays",        "moods",     "divine",     "穿透云层的耶稣光，丁达尔效应形成数道金色光柱洒向地面，照亮一片孤立的区域"),
    ("85_white_feathers",  "moods",     "divine",     "漫天飞舞的白色羽毛在虚空中缓缓飘落，背景是柔和的乳白光，羽毛投下淡淡阴影"),
    ("86_pure_void",       "moods",     "divine",     "纯白无瑕的虚无空间，没有地平线和参照物，只有极淡的阴影暗示着某种纯净的存在"),
    ("87_kaleidoscope",    "moods",     "chaos",      "扭曲的万花筒色彩，几何碎片在空间中无序旋转碰撞，色彩过于鲜艳以至于刺眼"),
    ("88_time_shards",     "moods",     "chaos",      "破碎的时空碎片，每个碎片中是不同的时间片段——孩童、老人、建筑、废墟同时出现"),
    ("89_black_lava",      "moods",     "chaos",      "沸腾的黑色岩浆，暗红裂纹在冷却的黑色外壳下蔓延，浓稠的岩浆沿裂缝渗出"),
    ("90_dark_abyss",      "moods",     "end",        "彻底陷入黑暗的深渊，画面几乎全黑，只有极深处有一丝即将熄灭的微弱光点"),
]

# ═══════════════════════════════════════════════════════════════
# Category → registry mapping
# ═══════════════════════════════════════════════════════════════

COMBAT_MAP = {
    "skirmish": "61_spark_clash",
    "battle":   "70_army_silhouette",
    "boss":     "66_target_lock",
    "ambush":   "69_broken_supplies",
}

NARRATIVE_MAP = {
    "discovery":  "71_campfire",
    "escape":     "64_broken_shield",
    "stealth":    "74_light_into_dark",
    "revelation": "72_desk_map",
    "aftermath":  "65_blood_banner",
}

MOOD_MAP = {
    "safe":     ["84_god_rays", "86_pure_void"],
    "normal":   ["85_white_feathers", "88_time_shards"],
    "tension":  ["82_choking_haze", "87_kaleidoscope"],
    "danger":   ["81_black_spread", "83_peeping_eyes"],
    "tragedy":  ["89_black_lava", "90_dark_abyss"],
}

MOOD_OPACITY = {"safe": 0.2, "normal": 0.3, "tension": 0.4, "danger": 0.45, "tragedy": 0.15}

MOOD_LABELS = {
    "safe": "安全区域——背景退后，文字主导",
    "normal": "正常探索——适中的存在感",
    "tension": "紧张——背景逐渐压迫",
    "danger": "危险——高存在感，背景逼近",
    "tragedy": "悲剧/濒死——褪色感，仿佛世界在撤离",
}

NARRATIVE_LABELS = {
    "discovery": "发现——微启的门缝透出第一道光",
    "escape": "逃亡——窄道、暗影、身后逼近的脚步",
    "stealth": "潜行——屏息贴墙，影子是你的盟友",
    "revelation": "揭示——真相如裂空闪电",
    "aftermath": "余波——硝烟散尽，寂静比战斗更沉重",
}

COMBAT_OPACITY = {"skirmish": 0.35, "battle": 0.40, "boss": 0.50, "ambush": 0.45}


def build_registry():
    """Build _shared/backgrounds.json from manifest + maps."""
    reserved = set()
    for v in COMBAT_MAP.values(): reserved.add(v)
    for v in NARRATIVE_MAP.values(): reserved.add(v)
    for variants in MOOD_MAP.values():
        for v in variants: reserved.add(v)

    registry = {
        "_comment": "共享背景图库 — 90张视觉母题分类预制图，跨世界通用",
        "locations": {},
        "combat": {},
        "moods": {},
        "narrative": {},
    }

    for file_id, _, subcat, _ in MANIFEST:
        if file_id in reserved:
            continue
        registry["locations"][file_id] = {"file": f"{file_id}.png", "mood": subcat}

    for tier, file_id in COMBAT_MAP.items():
        registry["combat"][tier] = {
            "file": f"{file_id}.png",
            "opacity": COMBAT_OPACITY[tier],
            "mood": f"战斗 — {tier}",
        }

    for key, file_id in NARRATIVE_MAP.items():
        registry["narrative"][key] = {
            "file": f"{file_id}.png",
            "opacity": 0.35 if key == "stealth" else (0.2 if key == "aftermath" else 0.3),
            "mood": NARRATIVE_LABELS.get(key, f"叙事 — {key}"),
        }

    for key, variants in MOOD_MAP.items():
        registry["moods"][key] = {
            "opacity": MOOD_OPACITY.get(key, 0.3),
            "label": MOOD_LABELS.get(key, ""),
            "variants": [f"{v}.png" for v in variants],
        }

    return registry


# ═══════════════════════════════════════════════════════════════
# Phase: submit all tasks
# ═══════════════════════════════════════════════════════════════

def phase_submit(delay=0.5):
    seen = set()
    all_ids = []
    for file_id, _, _, _ in MANIFEST:
        if file_id not in seen:
            seen.add(file_id)
            all_ids.append(file_id)

    id_to_prompt = {m[0]: m[3] for m in MANIFEST}

    print(f"Submitting {len(all_ids)} tasks...")
    print(f"Style: {STYLE[:80]}...")
    print("=" * 60)

    for i, file_id in enumerate(all_ids):
        prompt_cn = id_to_prompt[file_id]
        full_prompt = f"{prompt_cn}, {STYLE}"
        print(f"[{i+1}/{len(all_ids)}] {file_id}", end=" ")
        result = _do_submit(file_id, full_prompt, style="scene", tags=file_id)
        status = result.get("status", result.get("error", "?"))
        print(f"→ {status}")
        time.sleep(delay)

    print(f"\nSubmitted. Waiting for generation to complete...")
    return all_ids


# ═══════════════════════════════════════════════════════════════
# Phase: poll until all complete
# ═══════════════════════════════════════════════════════════════

def phase_poll(max_cycles=20, wait=30):
    for cycle in range(1, max_cycles + 1):
        time.sleep(wait)
        _auto_poll()
        pending = _load_pending()
        running = sum(1 for t in pending if t["status"] in ("PENDING", "RUNNING"))
        done = sum(1 for t in pending if t["status"] == "DONE")
        failed = sum(1 for t in pending if t["status"] == "FAILED")
        print(f"  Cycle {cycle}: DONE={done} RUNNING={running} FAILED={failed}")
        if running == 0:
            if failed > 0:
                print(f"  WARNING: {failed} tasks failed")
            return True
    print(f"  Timed out after {max_cycles} cycles")
    return False


# ═══════════════════════════════════════════════════════════════
# Phase: migrate images from world dir to _shared
# ═══════════════════════════════════════════════════════════════

def phase_migrate():
    world = _get_active_world()
    world_bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
    shared_bg_dir = os.path.join(ROOT, "rules", "_shared", "backgrounds")
    os.makedirs(shared_bg_dir, exist_ok=True)

    # Only migrate the 90 manifest images
    manifest_ids = set()
    for file_id, _, _, _ in MANIFEST:
        manifest_ids.add(file_id)

    print(f"Migrating {len(manifest_ids)} images from '{world}' to '_shared'...")
    copied = 0
    for file_id in sorted(manifest_ids):
        src = os.path.join(world_bg_dir, f"{file_id}.png")
        dst = os.path.join(shared_bg_dir, f"{file_id}.png")
        if os.path.exists(src):
            shutil.copy2(src, dst)
            copied += 1
        else:
            print(f"  MISSING: {file_id}.png")

    print(f"Copied: {copied}/{len(manifest_ids)}")

    # Write _shared/backgrounds.json
    registry = build_registry()
    shared_json = os.path.join(ROOT, "rules", "_shared", "backgrounds.json")
    with open(shared_json, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    print(f"Registry written: {shared_json}")
    print(f"  locations: {len(registry['locations'])}")
    print(f"  combat: {len(registry['combat'])}")
    print(f"  moods: {len(registry['moods'])}")
    print(f"  narrative: {len(registry['narrative'])}")

    # Clean up: remove manifest entries from world backgrounds.json
    world_json = os.path.join(ROOT, "rules", world, "backgrounds.json")
    if os.path.exists(world_json):
        with open(world_json, "r", encoding="utf-8") as f:
            world_reg = json.load(f)
        for section in ("locations", "combat", "moods", "narrative"):
            sec = world_reg.get(section, {})
            to_remove = [k for k in sec if k in manifest_ids]
            for k in to_remove:
                del sec[k]
        with open(world_json, "w", encoding="utf-8") as f:
            json.dump(world_reg, f, ensure_ascii=False, indent=2)
        print(f"Cleaned {len(to_remove)} entries from {world} backgrounds.json")


def _get_active_world():
    settings_file = os.path.join(ROOT, "rules", "settings.json")
    with open(settings_file, "r", encoding="utf-8") as f:
        return json.load(f).get("active_world", "cloud_chamber")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Build shared background library")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--phase", choices=["submit", "poll", "migrate", "all"], default="all")
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--poll-wait", type=int, default=30)
    args = parser.parse_args()

    if args.dry_run:
        reg = build_registry()
        print(f"Registry preview:")
        print(f"  locations: {len(reg['locations'])}")
        print(f"  combat: {list(reg['combat'].keys())}")
        print(f"  moods: {list(reg['moods'].keys())} ({sum(len(v['variants']) for v in reg['moods'].values())} variants)")
        print(f"  narrative: {list(reg['narrative'].keys())}")
        print(f"\nFile preview (first 5):")
        for m in MANIFEST[:5]:
            print(f"  {m[0]}: {m[3][:60]}...")
        print(f"  ... ({len(MANIFEST)} total)")
        return

    if args.phase in ("submit", "all"):
        phase_submit(args.delay)

    if args.phase in ("poll", "all"):
        print("\nPolling for completion...")
        ok = phase_poll(wait=args.poll_wait)
        if not ok:
            print("Some tasks may still be running. Re-run with --phase poll to continue.")
            return

    if args.phase in ("migrate", "all"):
        print("\nMigrating to shared library...")
        phase_migrate()

    print("\nDone. Shared library built.")


if __name__ == "__main__":
    main()
