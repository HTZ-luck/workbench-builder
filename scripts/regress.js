/* 回归自测骨架：每次改完 index.html 先跑一遍，确认没有「语法对但运行炸」的问题。
   跑法： NODE_PATH=<你的node工作区>/node_modules node regress.js --work <项目目录>
   依赖： jsdom

   这个文件本身就是三条铁律的示范：
     · 视图容器断言写 #viewWrap 不写 #view——写错会静默回退到 body.innerHTML，
       断言等于没验（真实项目踩过）
     · 全部用自己灌的 synthetic 数据，不绑会轮换的真实值——否则数据一换就假失败
     · 跳转类断言只验「目标存在」；window.open 在 jsdom 里是假的，
       真要验跳转必须 playwright 真点一次 */

const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

/* ---- 参数与配置读取（口径仍然只有 wbconfig.py 一处） ---- */
const argv = process.argv.slice(2);
let work = '.';
if (argv.includes('--work')) {
  const i = argv.indexOf('--work');
  work = argv[i + 1] || '.';
}
const HTML = path.resolve(work, 'index.html');
const cfgSrc = fs.existsSync(path.resolve(work, 'wbconfig.py'))
  ? fs.readFileSync(path.resolve(work, 'wbconfig.py'), 'utf8') : '';
function cfgNum(key, dflt) {
  const m = cfgSrc.match(new RegExp(key + '\\s*=\\s*(\\d+)'));
  return m ? +m[1] : dflt;
}
function cfgList(key) {
  const m = cfgSrc.match(new RegExp(key + '\\s*=\\s*\\[([^\\]]*)\\]'));
  return m ? m[1].match(/"([^"]+)"/g)?.map(s => s.slice(1, -1)) || [] : [];
}
const NAV_EXPECT = cfgNum('NAV_EXPECT', 0);
const VIEWS = cfgList('NAV_VIEWS');

let pass = 0, fail = 0;
const errs = [];
function ok(name, cond, extra) {
  if (cond) { pass++; }
  else { fail++; errs.push('FAIL: ' + name + (extra ? ' -> ' + extra : '')); }
}
function eq(name, a, b) { ok(name, a === b, JSON.stringify(a) + ' != ' + JSON.stringify(b)); }

/* ---- 启动一个干净的 jsdom；mut 在脚本执行前改 window ---- */
function boot(mut) {
  const vc = new VirtualConsole();
  const runtimeErrs = [];
  vc.on('jsdomError', e => runtimeErrs.push(e.message));
  vc.on('error', (...a) => runtimeErrs.push(a.join(' ')));
  const dom = new JSDOM(fs.readFileSync(HTML, 'utf8'), {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'https://example.com/',
    virtualConsole: vc,
    beforeParse(w) {
      w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
      w.fetch = () => Promise.reject(new Error('offline-test'));
      w.scrollTo = () => {};
      if (mut) mut(w);
    }
  });
  return { dom, w: dom.window, d: dom.window.document, runtimeErrs };
}

/* 灌 synthetic 数据：在解析前把数据块内容换掉（可一次换多个块）。
   这样断言验的是逻辑，不是今天恰好抓到了什么。
   注意 S4 的 stale 判定必须能把所有块一起换成干净版——
   页面里只要还有另一路是 stale，告警条就还在，那样「不 stale 必须不渲染」永远假失败。 */
function bootWithReplacement(repl) {
  let html = fs.readFileSync(HTML, 'utf8');
  for (const [id, obj] of Object.entries(repl)) {
    html = html.replace(new RegExp('(<script id="' + id + '"[^>]*>)[\\s\\S]*?(</script>)'),
      '$1' + JSON.stringify(obj).replace(/<\//g, '<\\/') + '$2');
  }
  const vc = new VirtualConsole();
  const runtimeErrs = [];
  vc.on('jsdomError', e => runtimeErrs.push(e.message));
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://example.com/',
    virtualConsole: vc,
    beforeParse(w) {
      w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
      w.fetch = () => Promise.reject(new Error('offline-test'));
      w.scrollTo = () => {};
    }
  });
  return { dom, w: dom.window, d: dom.window.document, runtimeErrs };
}
function bootWithData(blockId, obj) { return bootWithReplacement({ [blockId]: obj }); }

function clickNav(d, v) {
  const b = d.querySelector('.nav[data-view="' + v + '"]');
  if (!b) return false;
  b.dispatchEvent(new (b.ownerDocument.defaultView.MouseEvent)('click', { bubbles: true }));
  return true;
}
function dataBlock(d, id) {
  const el = d.getElementById(id);
  if (!el) return null;
  try { return JSON.parse(el.textContent); } catch (e) { return null; }
}

(async function () {
  /* ---------- S1 首屏：加载无错 + 结构完整 ---------- */
  let { w, d, runtimeErrs } = boot();
  await new Promise(r => setTimeout(r, 80));
  ok('首屏加载无 JS 运行时错误', runtimeErrs.length === 0, runtimeErrs[0]);
  eq('导航数量与配置一致', d.querySelectorAll('.nav').length, NAV_EXPECT);
  ok('视图容器是 #viewWrap（不是 #view）', !!d.getElementById('viewWrap'));
  ok('无 emoji', !/[\u{1F300}-\u{1FAFF}\u2600-\u27BF]/u.test(d.body.innerHTML));
  ok('无外链 CDN', !/<(script|link)[^>]+(src|href)=["']https?:/i.test(d.documentElement.outerHTML));
  console.log('S1 done');

  /* ---------- S2 数据块：齐全 + JSON 合法 + fetchedAt 在 ---------- */
  /* 注意 key 上的引号：wbconfig.py 写的是 "block": "xxxData"，正则必须容忍；
     取值要用捕获组，别再 match 第一个引号串（那拿到的是 key 名） */
  const blocks = [...cfgSrc.matchAll(/["']block["']\s*:\s*"([^"]+)"/g)].map(m => m[1]);
  ok('配置里至少有一个数据块', blocks.length > 0);
  for (const b of blocks) {
    const v = dataBlock(d, b);
    ok('数据块 #' + b + ' JSON 合法', v !== null);
    ok('数据块 #' + b + ' 带 fetchedAt', !!(v && v.fetchedAt));
  }
  console.log('S2 done');

  /* ---------- S3 视图切换：每个导航都能切，且切的是 viewWrap ---------- */
  for (const v of VIEWS) {
    const before = d.getElementById('viewWrap').innerHTML.length;
    const clicked = clickNav(d, v);
    ok('导航 ' + v + ' 存在且可点', clicked);
    if (clicked) {
      const sec = d.querySelector('#viewWrap [data-view-sec="' + v + '"]');
      ok('视图 ' + v + ' 有对应分区', !!sec);
    }
  }
  console.log('S3 done');

  /* ---------- S4 stale 告警：有 stale 必须渲染，没 stale 必须不渲染 ---------- */
  const fields = [...cfgSrc.matchAll(/["']field["']\s*:\s*"([^"]+)"/g)].map(m => m[1]);
  if (blocks.length) {
    /* baseline：每个块都换成不带 stale 三件套的干净版 */
    const cleanAll = {};
    for (const b of blocks) {
      const c = Object.assign({}, dataBlock(d, b) || {});
      delete c.stale; delete c.staleSince; delete c.staleReason;
      cleanAll[b] = c;
    }
    let r3 = bootWithReplacement(cleanAll);
    await new Promise(r => setTimeout(r, 80));
    ok('全不 stale 时告警条必须消失', !r3.d.querySelector('.stalebox'));

    /* 只给第一个块打 stale，其余保持干净 */
    const withStale = Object.assign({}, cleanAll);
    withStale[blocks[0]] = Object.assign({}, cleanAll[blocks[0]], {
      stale: true, staleSince: '2026-10-20 08:00', staleReason: '登录态过期（演示）'
    });
    let r2 = bootWithReplacement(withStale);
    await new Promise(r => setTimeout(r, 80));
    ok('stale 时页面渲染告警条', !!r2.d.querySelector('.stalebox'));
  }
  console.log('S4 done');

  /* ---------- S5 morelink：长得像链接就必须有可点的目标 ---------- */
  /* 先切回今日视图：S3 把视图停在最后一个，不是每个视图都有 morelink */
  clickNav(d, 'today');
  const links = [...d.querySelectorAll('.morelink')];
  ok('页面里有 morelink（卡片底部出口）', links.length > 0);
  for (const el of links) {
    const v = el.getAttribute('data-v');
    ok('morelink 指向的视图 ' + v + ' 在配置里', VIEWS.includes(v));
  }
  console.log('S5 done');

  /* ---------- S6 空数据不崩：每个块把自己的条目字段清空都不许炸 ---------- */
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    const f = fields[i] || 'items';
    const base = dataBlock(d, b) || {};
    const empty = Object.assign({}, base);
    empty[f] = [];
    let r4 = bootWithReplacement({ [b]: empty });
    await new Promise(r => setTimeout(r, 80));
    ok('#' + b + ' 0 条不崩', r4.runtimeErrs.length === 0, r4.runtimeErrs[0]);
  }
  console.log('S6 done');

  console.log('\n' + '='.repeat(46));
  console.log('通过 ' + pass + ' 项，失败 ' + fail + ' 项');
  if (fail) { errs.forEach(e => console.log('  ' + e)); process.exit(1); }
  console.log('全绿。注意：移动端溢出量 scrollWidth 和真实跳转，jsdom 验不了，');
  console.log('要用 playwright 遍历全部视图逐个量，必须 ≤ 视口宽。');
})();
