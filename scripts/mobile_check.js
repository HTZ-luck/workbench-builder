/* 移动端溢出 + 真实跳转检查（jsdom 验不了的那部分，跑法同 regress.js）
   跑法：NODE_PATH=<工作区>/node_modules node mobile_check.js --work <项目目录>
   依赖： playwright（chromium）

   判据（两条都是真实项目摔出来的）：
   1. 每个视图 document.documentElement.scrollWidth <= 视口宽。
      只看截图看不出来——溢出的是看不见的那几十 px（v64：390px 下 scrollWidth 到 442）。
   2. morelink 真点一下，视图必须真的切过去。window.open / location 那套在 jsdom 里是假的。

   视图清单从 wbconfig.py 的 NAV_VIEWS 读，口径仍然只有一处。 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const argv = process.argv.slice(2);
let work = '.';
if (argv.includes('--work')) {
  const i = argv.indexOf('--work');
  work = argv[i + 1] || '.';
}
const HTML = path.resolve(work, 'index.html');
const cfgSrc = fs.existsSync(path.resolve(work, 'wbconfig.py'))
  ? fs.readFileSync(path.resolve(work, 'wbconfig.py'), 'utf8') : '';
const views = [...cfgSrc.matchAll(/NAV_VIEWS\s*=\s*\[([^\]]*)\]/g)]
  .flatMap(m => (m[1].match(/"([^"]+)"/g) || []).map(s => s.slice(1, -1)));
if (!views.length) {
  console.log('读不到 wbconfig.py 的 NAV_VIEWS，没法知道要遍历哪些视图');
  process.exit(1);
}

(async () => {
  const browser = await chromium.launch();
  let fail = 0;
  const url = 'file://' + HTML;

  for (const [label, vp] of [['移动 390x844', { width: 390, height: 844 }],
                              ['桌面 1280x800', { width: 1280, height: 800 }]]) {
    const page = await browser.newPage({ viewport: vp });
    await page.goto(url);
    await page.waitForTimeout(150);
    console.log('--- ' + label + ' ---');
    for (const v of views) {
      await page.click('.nav[data-view="' + v + '"]');
      await page.waitForTimeout(60);
      const m = await page.evaluate(() => ({
        sw: document.documentElement.scrollWidth,
        cw: document.documentElement.clientWidth,
        sec: (document.querySelector('#viewWrap [data-view-sec]') || {}).getAttribute
          ? document.querySelector('#viewWrap [data-view-sec]').getAttribute('data-view-sec') : null
      }));
      const overflow = m.sw - m.cw;
      const bad = overflow > 1 || m.sec !== v;
      if (bad) fail++;
      console.log((bad ? '× ' : '√ ') + v.padEnd(9) + ' 文档宽 ' + m.sw + '/' + m.cw
        + (overflow > 1 ? ' 溢出 ' + overflow + 'px' : '')
        + '  视图分区=' + m.sec);
    }
    await page.close();
  }

  /* 真实跳转：点 morelink，视图必须真的切过去 */
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto(url);
  await page.waitForTimeout(150);
  const ml = await page.$('.morelink');
  if (ml) {
    const target = await ml.getAttribute('data-v');
    await ml.click();
    await page.waitForTimeout(120);
    const sec = await page.evaluate(() => {
      const el = document.querySelector('#viewWrap [data-view-sec]');
      return el ? el.getAttribute('data-view-sec') : null;
    });
    const okk = sec === target;
    if (!okk) fail++;
    console.log((okk ? '√ ' : '× ') + 'morelink 真点跳转：点了去「' + target + '」，现在停在 ' + sec);
  } else {
    fail++;
    console.log('× 首屏没找到 morelink');
  }
  await page.close();
  await browser.close();

  console.log('='.repeat(40));
  if (fail) { console.log('有 ' + fail + ' 项不过'); process.exit(1); }
  console.log('移动端无溢出、跳转真实可用。');
})();
