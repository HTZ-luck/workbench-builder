# scripts/ 使用说明

这一目录是**模板**：开始新工作台时把它整个复制进你的项目，然后只改 `wbconfig.py`。
`examples/minimal/` 是一份填好的实例，可以直接跑通全套流程。

## 文件清单

| 文件 | 干什么 | 什么时候跑 |
|---|---|---|
| `wbconfig.example.py` | 配置模板。复制到项目根目录改名 `wbconfig.py` | 开工第一件事 |
| `fetch_all.py` | 统一抓取入口。分班跑、失败沿用上次、断更进 alerts | 定时任务里跑 |
| `inject_data.py` | 把 `data/*.json` 注入页面数据块（`</head>` 前） | 抓取之后、自检之前 |
| `precheck.py` | 发布前自检。导航数、数据块、emoji、外链、条数、语法 | 注入之后、发布之前 |
| `publish.py` | 一条命令发布（接自动发布才有用；没接就只教你怎么手动部署） | 自检通过之后 |
| `regress.js` | jsdom 回归骨架。加载无错、视图切换、stale 告警、morelink 目标 | 每次改完页面 |
| `mobile_check.js` | 真浏览器：逐视图量横向溢出 + morelink 真点跳转。**它依赖 playwright，本机没装**；用不了就走 `references/visual-qa.md` 第三节那套 `chrome --headless=new` 探针（本机已验证可用） | 改完样式 / 发布前 |

## 标准流程（一条线走完）

```
改页面 / 改数据源
   ↓
node   scripts/regress.js       --work <项目目录>     # 改了页面先跑回归（jsdom，必须用 node，不是 python）
   ↓
python scripts/fetch_all.py --work <项目目录> --only intel   # 早班：情报源
python scripts/fetch_all.py --work <项目目录>                 # 晚班：全部源
   ↓
python scripts/inject_data.py --work <项目目录>  # json 进页面
   ↓
python scripts/precheck.py   --work <项目目录>   # 不过就停，保留线上旧的
   ↓
node   scripts/mobile_check.js --work <项目目录>  #  真浏览器：溢出量 + 真跳转（见下：本机没装 playwright）
   ↓
# 改了主题 / 皮肤 / 透明度 / 层级才需要，见下一段
python scripts/publish.py    --work <项目目录> "本次改动说明"
```

## 视觉那一道关（改了样式才需要）

前面六步覆盖的是数据和结构，**管不了"看得清不清"**。半透明层叠加之后的实际颜色、
以及「N 套皮肤 × 深浅 × 全部视图」这种组合规模，肉眼和截图都判不了。

这一道关的做法、探针的四个必错点、headless 的三个坑，全部在 `references/visual-qa.md`。
**按那个文件的第二节写你自己的探针**——它依赖项目里皮肤怎么切、视图怎么遍历，架不成通用脚本，
硬套通用版等于在没验证的探针上相信它的结论。

门槛两条：低于 3:1 的对比度条目数为 **0**；**320 / 375 / 414 / 768 / 1280** 五档 `scrollWidth ≤ 视口宽`。
溢出之外还有六条手机上必出事的规则（`overflow-x:clip` 不许写 `hidden`、全大写行高 ≥1.0 等），
见 `references/visual-qa.md` 第七节——它们在肉眼和 `scrollWidth` 上都查不出来。
探针修好之后常会暴露出一批历史遗留的低对比度，那不是这次改坏的，一并修并在改动说明里写出来。

## 脚本之外的两道人工关

这两道没有写成脚本，因为它们是**判断题不是计算题**，写通用脚本只会给出假结论：

1. **定义层：交付前逐条扫遗弃黑名单**（`references/workbench-definition.md` 第六节）。
   最关键的是把首屏按「第 40 天、这一天什么都没记、任务也没跑」渲染一遍——
   如果读起来跟第一天一样，那句话不是钩子，是一句恰好放在页面顶部的装饰。
2. **防重样：交付当天写一条 build-log**（`references/anti-sameness.md` 第三节）。
   五轴坐标 + 这次哪些判断后来被否掉了。**不写，下一份作品一定跟这份长一个样**——
   「别重样」这条规则靠记忆从来没有生效过。

`regress.js` 和 `mobile_check.js` 都要 jsdom / playwright：
`NODE_PATH=<你的node工作区>/node_modules node scripts/regress.js --work <项目目录>`。

退出码：`fetch_all.py` 是 **0 正常 / 2 有警告但数据还在（照常发布）/ 1 真失败**。
`precheck.py` / `inject_data.py` 是 0 通过 / 1 不通过。

## 「改一处要同步 N 处」这个坑，是怎么被 config 干掉的

真实项目里，导航数量写在四个脚本加两条定时任务里，共六份。
改导航漏了一份，自检拿着旧值卡新页面，查了半天以为是页面坏了。
现在：**导航数量只在 `wbconfig.py` 的 `NAV_EXPECT` 出现一次**，
`precheck.py` 读它，`regress.js` 用正则从同一个文件抠它，定时任务的 prompt 里写「以 wbconfig 为准」。

**你仍然要手动同步的只剩两处**（这是设计，不是遗漏）：
1. 页面里真的加/减导航按钮（HTML）
2. 定时任务里的班次时间（`--only intel` 还是全量）——因为这个取决于你的数据源发布时段，
   是业务判断，不该由脚本决定

## 四个从真实事故里捡回来的细节

1. **注入的兜底位置是 `</head>` 前，不是 `</body>` 前。**
   真实项目里某个抓取脚本的兜底分支插到了 `</body>` 前——而 init 是立即执行的 IIFE，
   数据块在 body 末尾，首屏三张卡全空。模板已修正，并且 `precheck.py` 查得到。
2. **JSON 里的 `</` 必须转义。** 条目文本里出现 `</script>` 会提前结束数据块标签，
   整块数据变成语法错误。`inject_data.py` 已处理，你自己写注入时也要处理。
3. **注释里别写 `<script>` 这四个字符。** `precheck.py` 找主脚本段靠正则，
   注释里出现 `<script>` 字样会把匹配带偏（示例页第一版就踩了：抓出来的是注释文字，
   `node --check` 报「之外。Invalid or unexpected token」）。模板已改成先剥注释再找，
   但你的页面里也最好别这么写。
4. **预置的示例数据要当场落盘。** 只在内存里铺种子的话，用户的第一个写操作
   （勾选 / 顺延 / 添加）读到的还是空列表，会把种子整批冲掉——4 条变 1 条，且不报错。
   这跟「失败不许冲掉好数据」是同一条铁律的种子版。

## 没验证过的，如实说

- `publish.py` 的四步事务流程是从一个真实发布体系提炼的（建事务→上传→提交→发布）。
  换到别的发布体系，`PUBLISH.page_dir` 指向的那套脚本接口不一样，要照着改。
- `regress.js` 只覆盖「不靠浏览器布局」的断言。**移动端横向溢出**和**真实跳转**
  要真浏览器补：逐视图量 `document.scrollWidth ≤ 视口宽`，并真点一次 morelink 确认视图真的切过去。
  只看截图看不出来——溢出的是看不见的那几十 px。
  **本机没有 playwright**（`import playwright` 和 `require('playwright')` 都失败），
  所以 `mobile_check.js` 在这里跑不起来。替代做法是 `references/visual-qa.md` 第三节的
  `chrome --headless=new` 注入探针：加载页面 → 注入脚本派发真实鼠标事件 → 读回 DOM。
  真实项目里跑通的就是这一套（对比度 / 溢出 / 截图三个脚本），优先照它写，别依赖 playwright。
- 抓取脚本本身不在这个模板里——每个源的抓法都不一样，照 `examples/minimal/scripts/fetch_demo_intel.py`
  的契约写：写 json、带 fetchedAt、0 条不覆盖、剥 emoji、弹掉代理变量。
- 交互层的坑（待办过期标红、折叠状态跨设备、导入导出）jsdom 和 playwright 脚本都只能验个大概，
  `examples/minimal/interactive_check.js` 是一份针对示例页的交互检查，可以照着写自己项目的。
