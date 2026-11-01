# -*- coding: utf-8 -*-
"""示例项目的配置。这就是「改一处同步 N 处」里的一处。

用法：cd 到项目根目录（本文件所在目录），然后
  python ../../scripts/fetch_all.py --work .            # 抓取（跑演示抓取脚本）
  python ../../scripts/inject_data.py --work .          # json 注入页面
  python ../../scripts/precheck.py   --work .           # 发布前自检
  python ../../scripts/regress.js    --work .           # jsdom 回归（需 jsdom）
"""
from pathlib import Path

SOURCES = [
    {"key": "intel", "name": "情报速览", "block": "intelData", "file": "intel.json",
     "field": "items", "min": 1, "cmds": ["scripts/fetch_demo_intel.py"], "batch": "intel"},
    {"key": "feed", "name": "行业热点", "block": "feedData", "file": "feed.json",
     "field": "items", "min": 0, "cmds": [], "batch": "intel"},
    {"key": "works", "name": "我的记录", "block": "worksData", "file": "works.json",
     "field": "works", "min": 1, "cmds": [], "batch": "all"},
]

BATCHES = {
    "intel": ["intel", "feed"],      # 早班：按天更新的源
}

NAV_EXPECT = 4
NAV_VIEWS = ["today", "intel", "works", "settings"]

PUBLISH = {
    "enabled": False,
    "node_id": "",
    "page_dir": "",
}

STALE_ALERT_HOURS = 24
EMOJI_OK = False
