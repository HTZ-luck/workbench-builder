#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一条命令发布：precheck 通过之后跑这个。

流程（顺序不能改）：
  create_page_transaction -> upload_page_artifact -> commit_page_transaction -> publish_page

上传前必须剥掉发布系统自己加的标记（data-page-node-id / data-pnid-children /
<!--pnid:--> / inject.js），否则下次下载回来的基线里带着一堆脏属性，
比对时会误判成「内容变了」。

没接自动发布（wbconfig.PUBLISH["enabled"] = False）时，这个脚本只告诉你怎么手动部署，
不碰任何线上东西。

用法：python publish.py --work <项目目录> "这次改了什么"
"""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path


def load_config(work):
    cfg_path = Path(work) / "wbconfig.py"
    spec = importlib.util.spec_from_file_location("wbconfig", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(py, page_dir, script, *args):
    cmd = [py, os.path.join(page_dir, script)] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (p.stdout or "").strip()


def jget(text, key):
    m = re.search(r'"' + key + r'"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def clean(src):
    src = re.sub(r'\s*data-page-node-id="[^"]*"', "", src)
    src = re.sub(r'\s*data-pnid-children="[^"]*"', "", src)
    src = re.sub(r'<!--pnid:[^>]*-->', "", src)
    src = re.sub(r'<script[^>]*\bid="inject\.js"[^>]*></script>', "", src)
    src = re.sub(r'<script[^>]*src="[^"]*inject\.js"[^>]*></script>', "", src)
    return src


def main():
    argv = sys.argv[1:]
    work = "."
    if "--work" in argv:
        i = argv.index("--work")
        if i + 1 >= len(argv):
            print("--work 后面要跟项目目录")
            return 1
        work = argv[i + 1]
    msg = " ".join(a for a in argv if not a.startswith("--") and a != work) or "更新页面"

    cfg = load_config(work)
    page = Path(work) / "index.html"
    pub = getattr(cfg, "PUBLISH", {})

    if not pub.get("enabled"):
        print("wbconfig.PUBLISH['enabled'] 是 False——本方案不接自动发布。")
        print("手动部署：把 %s" % page.resolve())
        print("上传到你的静态托管（或平台页面发布入口），拿到链接后用手机浏览器打开验证一次。")
        print("验证要点：数据块有数、stale 告警条该在的在该在、窄屏没有横向滚动条。")
        return 0

    if not page.exists():
        print("找不到页面：%s" % page)
        return 1
    node_id = pub.get("node_id") or ""
    page_dir = pub.get("page_dir") or ""
    if not (node_id and page_dir):
        print("PUBLISH 里 node_id / page_dir 没填全，补上再跑")
        return 1

    src = page.read_text(encoding="utf-8")
    out = clean(src)
    tmp = str(page) + ".publish.tmp.html"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    print("本地 %d KB -> 上传 %d KB（剥掉发布标记 %d 处）"
          % (len(src) // 1024, len(out) // 1024, len(src) - len(out)))

    r = run(sys.executable, page_dir, "create_page_transaction.py", "--node-id", node_id)
    tid = jget(r, "transaction_id") or jget(r, "transactionId")
    if not tid:
        print("开事务失败：", r[:400])
        return 1
    print("事务已开：", tid)

    # --path 是产物在页面里的相对路径（必须叫 index.html），--file 是本地文件
    r = run(sys.executable, page_dir, "upload_page_artifact.py", "--transaction-id", tid,
            "--path", "index.html", "--file", tmp)
    if '"error"' in r and "成功" not in r:
        print("上传失败：", r[:400])
        return 1
    print("已上传")

    r = run(sys.executable, page_dir, "commit_page_transaction.py",
            "--node-id", node_id, "--transaction-id", tid, "--message", msg)
    print("提交：", r[:300])

    r = run(sys.executable, page_dir, "publish_page.py", "--node-id", node_id)
    print("发布：", r[:300])

    os.remove(tmp)
    print("\n线上地址：见平台页面链接（壳页面只有几 KB，")
    print("真产物在 CDN 上，核对要拉真产物 grep，不要赌预览）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
