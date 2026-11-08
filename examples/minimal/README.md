# 最小示例 · 怎么用这个目录

这是一个**能直接双击打开**的最小工作台：四个导航、三个数据块、一条完整的
「抓取 → 注入 → 自检 →（发布）」流程。它的每一处写法都对应 `SKILL.md` 里的一条铁律，
注释里写明了是哪条。

```
examples/minimal/
├── index.html                  # 示例页（双击就能看）
├── wbconfig.py                 # 配置：单一事实来源（改导航数只改这一处）
├── interactive_check.js        # 交互检查（playwright）：待办/告警/导出/折叠跨设备/导入
├── data/                       # 三个数据块的 JSON（页面的数据快照）
│   ├── intel.json              #   正常数据：6 条情报
│   ├── feed.json               #   演示 stale：4 条旧数据 + 三件套
│   └── works.json              #   演示中位 vs 均值：8 条记录，含一条 210 的爆款
└── scripts/
    └── fetch_demo_intel.py     # 演示抓取脚本：演示失败时怎么「沿用上次 + 打 stale」
```

## 一、先看页面（30 秒）

用浏览器打开 `index.html`，按这个顺序点：

| 点哪里 | 看什么 | 对应铁律 |
|---|---|---|
| 首屏「今天要处理」 | 有一条**红色**的过期待办 + 「顺延到今天」按钮；勾选、删除、添加都即时生效 | 今天要处理置顶；过期必须标红并给动作 |
| 首屏黄色告警条 | 「行业热点旧到 10-23 21:40 + 为什么 + 怎么修」三件事写全了 | stale 必须写清「旧到什么时候 + 为什么 + 具体修法」 |
| 「情报流」 | 卡片网格（不是长条列表）；角标分来源；筛选条带计数；标题是真链接，卡片本身不给 pointer 手势 | 列表一律卡片网格；长得像链接就必须真能点 |
| 「我的记录」 | 中位 54 vs 均值 67.25；三档计数；红柱（爆款）/ 绿柱（低流量）/ 虚线（中位线） | 分组统计篇均+中位并列，排序用中位；按中位分三档 |
| 「设置」 | 导出 / 导入 / 清空；数据块清单（含 stale 状态）；这个示例在教什么 | 首屏能导出；0 条给「去哪修」的入口 |

**stale 演示**：把 `data/feed.json` 里的 `stale` / `staleSince` / `staleReason` 三个字段删掉，
跑一次注入，刷新页面——黄色告警整条消失。这就是「不 stale 时必须不渲染」。

**响应式**：把浏览器窗口压到 768px 以下，侧栏变成底部导航（带安全区适配），
格子变单列，没有横向滚动条。

## 二、跑完整流程

```bash
cd examples/minimal

# 1. 抓取（演示脚本：随机成功/失败，失败时沿用上次数据并打 stale）
python ../../scripts/fetch_all.py --work .

# 2. 注入：把 data/*.json 写进 index.html 的数据块
python ../../scripts/inject_data.py --work .

# 3. 自检：导航数、数据块、emoji、外链、条数、node --check
python ../../scripts/precheck.py --work .

# 4. jsdom 回归：首屏无错、视图切换、stale iff、morelink 目标、0 条不崩
NODE_PATH=<有jsdom的目录>/node_modules node ../../scripts/regress.js --work .

# 5. playwright 真浏览器：逐视图量横向溢出 + morelink 真点跳转
NODE_PATH=<有playwright的目录>/node_modules node ../../scripts/mobile_check.js --work .

# 6. 交互检查（示例页专属）：待办过期/顺延/角标、stale 双视图告警、
#    导出、折叠状态跨设备、粘贴导入、清空不复活
NODE_PATH=<有playwright的目录>/node_modules node interactive_check.js index.html
```

想让抓取真的失败一次看 stale 行为：

```bash
python scripts/fetch_demo_intel.py --fail     # 退出码 2，沿用上次 + 打 stale
python ../../scripts/inject_data.py --work .  # 注入后刷新页面看告警
```

跑法按上面的顺序：jsdom 回归、溢出检查、交互检查依次过一遍，全绿再往下走。
交互检查最该锁的一条是「清空生效」：示例数据只在内存里铺、没落盘时，
第一个写操作会把种子整批冲掉，且不报错。

## 三、这个目录里没有的东西（故意的）

- **没有发布配置**：`wbconfig.py` 里 `PUBLISH.enabled = False`，跑 `publish.py`
  只会打印手动部署提示。发布是项目自己的事，模板不替你决定。
- **没有 AI 调用**：最小示例不接任何大模型。真实项目要接，按 `SKILL.md` 铁律 9
  做（Key 只进本机 localStorage、必带「AI 生成」徽章、禁编数字）。
- **没有深色主题**：真实项目有 `data-theme` 切换，示例只做浅色，少一样要维护的东西。

## 四、拿它改出自己的第一个工作台

1. 复制整个 `examples/minimal/` 目录，改名。
2. 改 `wbconfig.py`：`NAV_EXPECT` / `NAV_VIEWS` / `SOURCES` / `BATCHES`。
   **导航数量只在这一处改**——真实项目曾因为六处各写一份数字，改了一处漏五处。
3. 改 `index.html`：导航按钮、`refreshAll()` 里的视图分支、对应的 `renderXxx()`。
   数据块 `<script id="xxxData">` 留在 `</head>` 前，内容交给 `inject_data.py`。
4. 用自己的抓取脚本替换 `scripts/fetch_demo_intel.py`，在 `wbconfig.py` 的 `cmds` 里登记。
5. 每加一个视图，同步三处：`NAV_VIEWS`、`refreshAll()` 的分支、导航按钮。
6. 跑第四条命令全绿，再考虑发布。
