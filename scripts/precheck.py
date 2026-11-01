# -*- coding: utf-8 -*-
"""发布前自检：注入完页面、发布之前跑一遍。

只查「页面本身有没有被改坏」和「数据块有没有数」，不查业务对不对。
任何一项不通过就 exit 1，调用方应当停止发布、保留线上旧数据。

检查项（导航数、数据块清单全部从项目的 wbconfig.py 读，不存在第二份口径）：
  1. 导航 .nav 数量 == wbconfig.NAV_EXPECT
  2. 每个数据块 id 齐全且 JSON 合法
  3. 零 emoji（1F300-1FAFF / 2600-27BF；→ 这类箭头不算）
  4. 零 http(s) 静态外链资源（<a href> 的内容链接不算，那是正文不是资源）
  5. 各源条数 >= wbconfig 里配的 min
  6. 主 script 段语法能过 node --check

用法：python precheck.py --work <项目目录>
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def load_config(work):
    cfg_path = Path(work) / "wbconfig.py"
    if not cfg_path.exists():
        print("找不到 %s" % cfg_path)
        return None
    spec = importlib.util.spec_from_file_location("wbconfig", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    argv = sys.argv[1:]
    work = "."
    if "--work" in argv:
        i = argv.index("--work")
        if i + 1 >= len(argv):
            print("--work 后面要跟项目目录")
            return 1
        work = argv[i + 1]
    cfg = load_config(work)
    if cfg is None:
        return 1
    page = Path(work) / "index.html"
    if not page.exists():
        print("找不到页面：%s" % page)
        return 1
    html = page.read_text(encoding="utf-8")
    bad = []

    # 1. 导航（宽松正则：属性顺序会变，严格写法会漏）
    navs = re.findall(r'class="nav[^"]*"[^>]*data-view="([^"]+)"', html)
    if not navs:
        navs = [v for v in re.findall(r'data-view="([^"]+)"', html) if "'" not in v]
    n = len(navs)
    print("%s 导航 data-view：%d 个（期望 %d）" % ("√" if n == cfg.NAV_EXPECT else "×", n, cfg.NAV_EXPECT))
    if n != cfg.NAV_EXPECT:
        bad.append("导航数 %d != %d" % (n, cfg.NAV_EXPECT))
    missing_views = [v for v in cfg.NAV_VIEWS if v not in navs]
    if missing_views:
        print("× 配置里有的视图导航里没有：%s" % "、".join(missing_views))
        bad.append("缺视图 %s" % "、".join(missing_views))

    # 2. 数据块
    data = {}
    for src in cfg.SOURCES:
        b = src["block"]
        m = re.search(r'<script[^>]*id="%s"[^>]*>(.*?)</script>' % b, html, re.S)
        if not m:
            print("× 缺数据块 #%s" % b)
            bad.append("缺 %s" % b)
            data[b] = None
            continue
        try:
            data[b] = json.loads(m.group(1).strip())
        except Exception as e:
            print("× #%s 不是合法 JSON：%s" % (b, e))
            bad.append("%s JSON 坏" % b)
            data[b] = None
    if not any(v is None for v in data.values()):
        print("√ %d 个数据块齐全且 JSON 合法" % len(cfg.SOURCES))

    # 3. emoji
    hits = EMOJI.findall(html)
    print("%s emoji：%d 个" % ("√" if not hits else "×", len(hits)))
    if hits:
        bad.append("emoji %d 个" % len(hits))

    # 4. 静态外链
    ext = re.findall(r'<(?:script|link|img|iframe|source|video|audio)\b[^>]*'
                     r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html, re.I)
    print("%s 静态外链资源：%d 个 %s" % ("√" if not ext else "×", len(ext), ext[:3]))
    if ext:
        bad.append("静态外链 %d 个" % len(ext))

    # 5. 条数（条目字段从配置读，不按顶层键数算）
    for src in cfg.SOURCES:
        b = src["block"]
        v = data.get(b)
        if v is None:
            continue
        f = v.get(src["field"]) if isinstance(v, dict) else None
        c = len(f) if isinstance(f, list) else 0
        need = src.get("min", 0)
        okk = c >= need
        print("%s %-10s %d 条（要求 ≥%d）" % ("√" if okk else "×", b, c, need))
        if not okk:
            bad.append("%s 只有 %d 条" % (b, c))

    # 6. 语法
    # 先剥 HTML 注释再找主脚本段：注释里出现 <script> 字样会把朴素的
    # <script>(.*?)</script> 正则带偏（示例页的注释就踩过——抓出来的是注释文字，
    # node --check 报「之外。Invalid or unexpected token」）。
    # 剥注释只会误伤极少见的「JS 里写着 <!-- 且没有 -->」的页面，真遇到了改用别的手段。
    plain = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    blocks = re.findall(r"<script\b([^>]*)>(.*?)</script>", plain, re.S)
    main_js = None
    for attrs, body in blocks:
        # 数据块（type=application/json）和外链脚本都不是主脚本
        if "json" in attrs.lower() or re.search(r"\bsrc\s*=", attrs, re.I):
            continue
        main_js = body
        break
    if main_js is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(main_js)
            tmp = f.name
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        print("%s 主脚本语法 node --check" % ("√" if r.returncode == 0 else "×"))
        if r.returncode != 0:
            print(r.stderr[:500])
            bad.append("JS 语法错")
        Path(tmp).unlink(missing_ok=True)
    else:
        print("× 没找到主 <script> 段")
        bad.append("缺主 script")

    print("-" * 46)
    if bad:
        print("不通过：%s" % "；".join(bad))
        return 1
    print("全部通过，可以发布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
