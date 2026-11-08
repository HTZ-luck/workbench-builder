# -*- coding: utf-8 -*-
r"""把 data/ 下的 json 注入页面数据块——「数据跟着页面一起下发」靠的就是这一步。

每条规则都对应一种明确的失败：
  · 插到 </head> 之前，不是 </body> 之前。init 是立即执行的 IIFE，
    数据块放 body 末尾，首屏三张卡全空。
  · JSON 里的 </ 必须转义成 <\/。条目文本里出现 </script> 会提前结束标签，
    整块数据变语法错误。
  · fetchedAt 存北京时间字符串。页面按 .slice(11,16) 取 HH:MM，
    直接存 UTC 时间戳会显示成差 8 小时的钟点。
  · 0 条不注入。宁可显示旧的并标明，不许显示空的（铁律 5）。

用法：
  python inject_data.py --work <项目目录>            注入全部源
  python inject_data.py --work <项目目录> --only intel   只注入指定的源
"""

import importlib.util
import json
import sys
from pathlib import Path

MARK = '<script id="%s" type="application/json">'


def load_config(work):
    cfg_path = Path(work) / "wbconfig.py"
    if not cfg_path.exists():
        print("找不到 %s，先把 scripts/wbconfig.example.py 复制过去改名 wbconfig.py" % cfg_path)
        return None
    spec = importlib.util.spec_from_file_location("wbconfig", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inject(page, block, data):
    """有就整块替换，没有就插到 </head> 前（兜底位置必须是 </head>，不是 </body>）。"""
    body = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    new = MARK % block + body + "</script>\n"
    s = page.read_text(encoding="utf-8")
    mark = MARK % block
    i = s.find(mark)
    if i >= 0:
        j = s.find("</script>", i)
        if j < 0:
            return None, "数据块 %s 没有闭合的 </script>" % block
        s = s[:i] + new + s[j + len("</script>"):]
        how = "替换"
    else:
        k = s.find("</head>")
        if k < 0:
            return None, "页面里没有 </head>，也没找到数据块 %s" % block
        s = s[:k] + new + s[k:]
        how = "新建（插在 </head> 前）"
    page.write_text(s, encoding="utf-8", newline="")
    return how, None


def main():
    argv = sys.argv[1:]
    work = "."
    if "--work" in argv:
        i = argv.index("--work")
        if i + 1 >= len(argv):
            print("--work 后面要跟项目目录")
            return 1
        work = argv[i + 1]
    only = ""
    if "--only" in argv:
        i = argv.index("--only")
        only = argv[i + 1].strip().lower() if i + 1 < len(argv) else ""

    cfg = load_config(work)
    if cfg is None:
        return 1
    page = Path(work) / "index.html"
    if not page.exists():
        print("找不到页面：%s" % page)
        return 1

    bad = []
    for src in cfg.SOURCES:
        if only and src["key"] != only:
            continue
        f = Path(work) / "data" / src["file"]
        if not f.exists():
            print("× %s：没有 %s（先跑抓取，或从页面现有数据块里导出）" % (src["name"], f))
            bad.append(src["key"])
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print("× %s：%s 不是合法 JSON：%s" % (src["name"], f.name, e))
            bad.append(src["key"])
            continue
        n = len(data.get(src["field"]) or []) if isinstance(data.get(src["field"]), list) else 0
        if n == 0 and src.get("min", 0) > 0:
            print("× %s：0 条，不注入——宁可页面显示旧的并标明，不许显示空的" % src["name"])
            bad.append(src["key"])
            continue
        how, err = inject(page, src["block"], data)
        if err:
            print("× %s：%s" % (src["name"], err))
            bad.append(src["key"])
            continue
        stale = "（stale，页面会显示告警）" if data.get("stale") else ""
        print("√ %-8s %d 条 → #%s（%s）%s" % (src["name"], n, src["block"], how, stale))

    print("-" * 46)
    if bad:
        print("没注入：%s" % "、".join(bad))
        return 1
    print("全部注入完成。接下来跑 precheck.py，通过了再发布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
