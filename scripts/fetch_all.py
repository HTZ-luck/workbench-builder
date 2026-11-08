# -*- coding: utf-8 -*-
"""统一抓取入口：所有数据源一次跑完，统一时间、统一出口。

这个脚本是 SKILL.md 三条铁律的落地处：
  铁律 7  抓取入口只有一个——不要给单个源单独建定时任务，分班用 --only 跑
  铁律 5  失败不许冲掉好数据——退出码 2 = 有警告但数据还在，让它继续往下跑，
          好把「旧数据」这件事也同步到页面上
  铁律 6  断更必须喊出来——超过 24 小时没换新数的源进 alerts，
          定时任务的汇报第一句必须是它，否则「成功」两个字会把断更盖住

用法：
  python fetch_all.py --work <项目目录>            全部源
  python fetch_all.py --work <项目目录> --only intel   只跑情报班（早上那班）
  python fetch_all.py --work <项目目录> --only intel,feed  只跑指定的几个源

退出码：0 正常 / 2 有警告但数据还在（照常发布）/ 1 真失败
"""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_config(work):
    """读项目自己的 wbconfig.py。没有就明确告诉你去复制模板，不许静默用默认值。"""
    cfg_path = Path(work) / "wbconfig.py"
    if not cfg_path.exists():
        print("找不到 %s" % cfg_path)
        print("把 scripts/wbconfig.example.py 复制到项目根目录改名 wbconfig.py，改完再来")
        return None
    spec = importlib.util.spec_from_file_location("wbconfig", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_step(src, work):
    """一个源里的多条命令串行。
    退出码 2 = 有警告但数据还在（沿用上次），继续往下跑；
    其他非 0 判失败，把 stderr 最后一行带回来（页面要靠它写 staleReason）。"""
    warned = False
    for c in src.get("cmds") or []:
        p = Path(work) / c
        if not p.exists():
            return False, "脚本不存在：%s" % c
        r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", cwd=str(work))
        tail = (r.stdout or "").strip().splitlines()
        print("   " + ("；".join(tail[-2:]) if tail else "(无输出)"))
        if r.returncode == 2:
            warned = True
            continue
        if r.returncode != 0:
            err = (r.stderr or "").strip().splitlines()
            return False, err[-1] if err else "退出码 %d" % r.returncode
    return True, ("沿用上次数据" if warned else "")


def collect_alerts(cfg, work):
    """扫一遍 data/*.json，把「打了 stale 且超过 N 小时没抓到新数」的挑出来。

    为什么要有这个：退出码 2 = 有警告但数据还在，于是照常发布、汇报「成功」，
    用户看到的是一页正常的数据。某数据源登录态掉了、连着两天没拿到新数，
    每天都被判「成功」，直到用户自己发现时间戳不对来问。所以这里单独拎出来。
    """
    alerts = []
    data_dir = Path(work) / "data"
    if not data_dir.exists():
        return alerts
    for p in sorted(data_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or not d.get("stale"):
            continue
        at = str(d.get("staleSince") or d.get("fetchedAt") or "").strip()
        try:
            hrs = (datetime.now() - datetime.strptime(at, "%Y-%m-%d %H:%M")).total_seconds() / 3600
        except Exception:
            hrs = 999
        if hrs < getattr(cfg, "STALE_ALERT_HOURS", 24):
            continue          # 一天内的沿用属正常，不值得报警
        alerts.append({
            "file": p.name,
            "since": at,
            "hours": int(hrs),
            "reason": d.get("staleReason", ""),
            "items": len(d.get("items") or d.get("works") or []),
        })
    return alerts


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
        if i + 1 >= len(argv):
            print("--only 后面要跟班次名（见 wbconfig.py 的 BATCHES），或逗号分隔的源 key")
            return 1
        only = argv[i + 1].strip().lower()

    cfg = load_config(work)
    if cfg is None:
        return 1

    keys = {s["key"] for s in cfg.SOURCES}
    if only:
        picked = [k.strip() for k in only.split(",") if k.strip()]
        unknown = [k for k in picked if k not in keys and k not in cfg.BATCHES]
        if unknown:
            print("不认识的：%s" % "、".join(unknown))
            print("可用班次：%s；可用源：%s" % ("、".join(sorted(cfg.BATCHES)), "、".join(sorted(keys))))
            return 1
        selected = set()
        for k in picked:
            selected.update(cfg.BATCHES.get(k, [k]))
        batch_name = "指定：" + only
    else:
        selected = set(keys)
        batch_name = "全部 %d 个源" % len(keys)

    print("=" * 46)
    print("  统一抓取  %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("  项目目录：%s" % Path(work).resolve())
    print("  本次跑：%s" % batch_name)
    print("=" * 46)

    results = []
    for src in cfg.SOURCES:
        if src["key"] not in selected:
            continue
        print("\n[%s] %s …" % (src["key"], src["name"]))
        ok, msg = run_step(src, work)
        results.append({"key": src["key"], "name": src["name"], "ok": ok, "error": msg})
        print("   → %s" % (("完成 · " + msg) if (ok and msg) else ("完成" if ok else ("失败：" + msg))))

    report = {
        "ranAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "batch": batch_name,
        "ok": all(r["ok"] for r in results),
        "steps": results,
        "alerts": collect_alerts(cfg, work),
    }
    (Path(work) / "data").mkdir(exist_ok=True)
    (Path(work) / "data" / "last_run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    print("\n" + "-" * 46)
    for r in results:
        if r["ok"]:
            print("  √ %s%s" % (r["name"], "（" + r["error"] + "）" if r["error"] else ""))
        else:
            print("  × %s —— %s" % (r["name"], r["error"]))
    print("-" * 46)

    # 超过 N 小时还没换新数的源，必须喊出来——否则「成功」两个字会把断更盖住
    if report["alerts"]:
        print("")
        print("!" * 46)
        print("  数据断更超过 %d 小时，别再当成功看：" % getattr(cfg, "STALE_ALERT_HOURS", 24))
        for a in report["alerts"]:
            print("  - %s 停在 %s（%d 小时前，%d 条）" %
                  (a["file"], a["since"], a["hours"], a["items"]))
            if a["reason"]:
                print("    原因：%s" % a["reason"])
        print("!" * 46)

    print("报告：%s" % (Path(work) / "data" / "last_run.json"))
    bad = [r["name"] for r in results if not r["ok"]]
    if bad:
        return 1
    return 2 if any(r["error"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
