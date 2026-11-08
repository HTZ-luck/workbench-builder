# -*- coding: utf-8 -*-
"""工作台配置模板 —— 复制到你的项目根目录，改名 wbconfig.py，然后只改这里。

为什么要有这个文件：导航数量曾在四个脚本加两条定时任务里各写了一份，
改的时候漏了一处，自检拿着旧值卡新页面（SKILL.md 铁律 3：口径必须单一来源）。
现在所有「会被多处引用的数」只在这里定义一次，其他脚本全部 import 它。

复制过去之后要改的只有三样：
  1. SOURCES     —— 你的数据源清单（块 id / json 文件名 / 条目字段 / 抓取脚本）
  2. NAV_EXPECT  + NAV_VIEWS —— 你的导航数量和各视图 id
  3. PUBLISH     —— 接不接自动发布（不接就留 enabled=False）
"""
from pathlib import Path

# ========== 路径 ==========
# 所有脚本都接受 --work 指定项目目录，不指定就用当前目录。
# 约定：项目根目录放 index.html 和 data/（各源抓取出来的 json）。

# ========== 数据源 ==========
# 每个源一个字典。字段说明：
#   key     内部名，分班和 --only 用它
#   name    给人看的名字
#   block   页面里的数据块 id（<script id="xxxData" type="application/json">）
#   file    抓取产出的 json 文件名（放在 <work>/data/ 下）
#   field   条目藏在哪个字段——顶层键会骗人，必须写死（SKILL.md 阶段 3 第 2 条）
#   min     precheck 要求的最少条数；0 = 允许空（没配 Key、源暂挂时不算失败）
#   cmds    这个源要跑的命令（相对项目目录），可以多条串行；空列表 = 只注入不抓
#   batch   属于哪个班次；"all" 是保留字，表示每班都跑
SOURCES = [
    {"key": "intel", "name": "情报速览", "block": "intelData", "file": "intel.json",
     "field": "items", "min": 1, "cmds": ["scripts/fetch_demo_intel.py"], "batch": "intel"},
    {"key": "feed", "name": "行业热点", "block": "feedData", "file": "feed.json",
     "field": "items", "min": 0, "cmds": [], "batch": "intel"},
    {"key": "works", "name": "我的记录", "block": "worksData", "file": "works.json",
     "field": "works", "min": 1, "cmds": [], "batch": "all"},
]

# ========== 分班 ==========
# 班次时间用真实数据定，不拍脑袋：先统计你的数据源实际发布时段，再定早晚班。
# 先统计自己数据源的实际发布时段再定：集中傍晚到夜间就放晚班，
# 按天更新的源放早班捞隔夜内容。
# 这里的 key 是班次名，value 是这一班要跑的源 key 列表。
BATCHES = {
    "intel": ["intel", "feed"],      # 早班：按天更新的源
}

# ========== 页面结构 ==========
NAV_EXPECT = 4                        # 导航按钮数——改了导航就改这一处
NAV_VIEWS = ["today", "intel", "works", "settings"]   # 各视图 id，regress.js 逐个切

# ========== 发布 ==========
# enabled=False：precheck 通过后自己手动部署，脚本不碰发布。
# 接入自动发布后填 node_id（线上页面 id）和 page_dir（发布脚本所在目录）。
PUBLISH = {
    "enabled": False,
    "node_id": "",
    "page_dir": "",
}

# ========== 杂项 ==========
STALE_ALERT_HOURS = 24                # 超过几小时没换新数就进 alerts
EMOJI_OK = False                      # 页面是否允许 emoji（建议 False）
