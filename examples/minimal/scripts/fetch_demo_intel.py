# -*- coding: utf-8 -*-
"""演示抓取脚本：示范一个「守规矩」的抓取器长什么样，不连任何真实接口。

它演示的契约（你写自己的抓取脚本时照这个来）：
  1. 写 json 到 data/intel.json，带 fetchedAt（北京时间字符串，不是 UTC 时间戳）
  2. 抓不到就绝不覆盖——沿用上次数据，打上 stale 三件套，退出码 2
  3. 外部内容先剥 emoji 再入库，否则页面自检过不了
  4. 弹掉所有 *roxy* 环境变量——运行环境的代理隧道时好时坏，会让好好的接口报 502
  5. JSON 序列化时 </ 转义——条目文本里出现 </script> 会提前结束数据块标签

用法：
  python fetch_demo_intel.py          正常抓（生成 6 条演示数据）
  python fetch_demo_intel.py --fail   模拟抓取失败：看它怎么沿用旧数据 + 打 stale
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "intel.json"
PAGE = Path(__file__).resolve().parent.parent / "index.html"

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3\u2190-\u21FF\u2B1C-\u2B55]"
)

POOL = [
    ("星球", "工具", "有人用 AI 把老小区改造方案做成可交互 3D，甲方当场拍板"),
    ("星球", "变现", "设计院开始收「AI 出图 + 人工改图」的打包价，单价降了三成"),
    ("热点", "行业", "多家家居品牌把软装方案页搬到线上，客户能自己换材质看效果"),
    ("星球", "工具", "一款批量去水印的工具被封了，替代方案是本地跑开源脚本"),
    ("热点", "踩坑", "AI 生成的平面图层名全是中文，导入 CAD 直接乱码"),
    ("星球", "选题", "「设计师转行做 AI 工具测评」这条赛道的商单报价涨了"),
]


def bj_now():
    return datetime.now(timezone(timedelta(hours=8)))


def strip_emoji(s):
    return re.sub(r"\s+", " ", EMOJI.sub("", s)).strip()


def load_prev():
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except Exception:
        return None


def keep_prev(reason):
    """沿用上一次成功的数据，把「旧」这件事写进 json——页面靠它渲染告警条。"""
    prev = load_prev()
    if prev is None:
        print("   没有可沿用的旧数据，也不写空文件（宁可没有，不许是空的）")
        return 1
    prev["stale"] = True
    prev["staleSince"] = bj_now().strftime("%Y-%m-%d %H:%M")
    prev["staleReason"] = reason
    DATA.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("   抓取失败：沿用上次 %d 条，已打 stale（原因：%s）" % (len(prev.get("items") or []), reason))
    return 2          # 退出码 2 = 有警告但数据还在，让统一入口继续往下跑


def main():
    if "--fail" in sys.argv:
        return keep_prev("演示：模拟抓取失败（--fail）")

    # 弹掉代理变量：运行环境的代理隧道时好时坏，会让好好的接口报 502
    for k in list(os.environ):
        if "roxy" in k.lower():
            os.environ.pop(k)

    today = bj_now().strftime("%Y-%m-%d %H:%M")
    items = []
    for i, (src, tag, title) in enumerate(POOL[:6]):
        items.append({
            "src": src, "tag": tag,
            "at": bj_now().strftime("%m-%d ") + "%02d:%02d" % (8 + i // 2, 10 + i * 7 % 50),
            "title": strip_emoji(title),
            "url": "https://example.com/intel/%d" % (i + 1),
        })
    if not items:
        return keep_prev("演示：返回 0 条")

    data = {"fetchedAt": today, "items": items}
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("   抓到 %d 条 → 已写 %s（fetchedAt %s）" % (len(items), DATA.name, today))
    print("   下一步：python ../../scripts/inject_data.py --work .")
    return 0


if __name__ == "__main__":
    sys.exit(main())
