/* 交互 + 折叠跨设备 + 导入导出检查（真浏览器，jsdom 替代不了的部分）
   跑法：NODE_PATH=<工作区>/node_modules node interactive_check.js <index.html路径> */
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const file = process.argv[2];
  if (!file) { console.log('用法：node interactive_check.js <index.html>'); process.exit(1); }
  const browser = await chromium.launch();
  let fail = 0;
  const ok = (name, cond, extra) => {
    if (!cond) fail++;
    console.log((cond ? '√ ' : '× ') + name + (extra ? ' -> ' + extra : ''));
  };
  const url = 'file://' + path.resolve(file);

  /* ---------- A. 待办交互 ---------- */
  let page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(url);
  await page.waitForTimeout(150);
  const od = await page.$('.todo.overdue');
  ok('有过期的待办且标红', !!od);
  if (od) {
    const txt = await od.textContent();
    ok('过期行写明「已过期」', /已过期/.test(txt), txt.slice(0, 40));
    await page.click('.todo.overdue [data-act="todoDelay"]');
    await page.waitForTimeout(80);
    ok('顺延之后不再过期', (await page.$('.todo.overdue')) === null);
  }
  const n0 = await page.$$eval('.todo input[type=checkbox]', els => els.length);
  await page.fill('#todoIn', 'playwright 加的一条');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(80);
  const n1 = await page.$$eval('.todo input[type=checkbox]', els => els.length);
  ok('回车添加待办生效', n1 === n0 + 1, n0 + ' -> ' + n1);
  const badge0 = await page.$eval('#bg-today', el => +el.textContent);
  await page.click('.todo input[type=checkbox]');
  await page.waitForTimeout(80);
  const badge = await page.$eval('#bg-today', el => +el.textContent);
  ok('导航角标跟着未完成数走', badge === badge0 - 1, badge0 + ' -> ' + badge);

  /* ---------- D. stale 告警双视图 ---------- */
  const t1 = await page.$eval('.stalebox', el => el.textContent).catch(() => '');
  ok('今日视图有 stale 告警', /行业热点/.test(t1) && /修法/.test(t1), t1.slice(0, 30));
  await page.click('.nav[data-view="intel"]');
  await page.waitForTimeout(80);
  const t2 = await page.$eval('.stalebox', el => el.textContent).catch(() => '');
  ok('情报流视图也有 stale 告警（消费它的视图都要有）', /行业热点/.test(t2));

  /* ---------- C. 导出 ---------- */
  const dl = page.waitForEvent('download', { timeout: 5000 }).catch(() => null);
  await page.click('.nav[data-view="settings"]');
  await page.waitForTimeout(60);
  await page.click('[data-act="export"]');
  const download = await dl;
  ok('导出真的下了文件', !!download && /wb_demo_backup\.json$/.test(download.suggestedFilename()),
    download ? download.suggestedFilename() : '没触发');

  /* ---------- B. 折叠状态跨设备（v57：手机上必须强制展开） ---------- */
  await page.click('#fold');
  await page.waitForTimeout(60);
  const folded = await page.$eval('#side', el => el.classList.contains('collapsed'));
  const lsNav = await page.evaluate(() => localStorage.getItem('wb_demo_nav'));
  ok('桌面折叠生效且写进 localStorage', folded && lsNav === '1');

  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mp = await mctx.newPage();
  await mp.goto(url);
  await mp.waitForTimeout(150);
  const mob = await mp.evaluate(() => {
    const nm = document.querySelector('.nav[data-view="today"] .nm');
    const side = document.querySelector('#side');
    const cs = getComputedStyle(nm);
    const btn = document.querySelector('.nav[data-view="works"]').getBoundingClientRect();
    return { nmDisplay: cs.display, sideBottom: side.getBoundingClientRect().bottom,
             vh: window.innerHeight, btnH: btn.height, btnVisible: btn.width > 0 && btn.height > 0 };
  });
  ok('手机上折叠状态被强制展开（nm 可见）', mob.nmDisplay !== 'none', 'display=' + mob.nmDisplay);
  ok('手机上导航贴在底部安全区', mob.sideBottom > mob.vh - 90 && mob.btnVisible,
    'bottom=' + Math.round(mob.sideBottom) + ' vh=' + mob.vh + ' 按钮高=' + Math.round(mob.btnH));
  await mp.click('.nav[data-view="works"]');
  await mp.waitForTimeout(80);
  const msec = await mp.evaluate(() => {
    const el = document.querySelector('#viewWrap [data-view-sec]');
    return el ? el.getAttribute('data-view-sec') : null;
  });
  ok('手机上点底部导航能切视图', msec === 'works', 'sec=' + msec);

  /* ---------- E. 粘贴导入 ---------- */
  await mp.click('.nav[data-view="settings"]');
  await mp.waitForTimeout(60);
  await mp.fill('#impText', JSON.stringify({ v: 1, app: 'wb_demo', view: 'works',
    todos: [{ id: 'x1', text: '导入进来的待办', due: '2099-01-01', done: false }] }));
  mp.on('dialog', d => d.accept());
  await mp.click('[data-act="importText"]');
  await mp.waitForTimeout(120);
  const imp = await mp.evaluate(() => {
    const a = JSON.parse(localStorage.getItem('wb_demo_todos') || '[]');
    const el = document.querySelector('#viewWrap [data-view-sec]');
    return { n: a.length, first: a[0] ? a[0].text : '', sec: el ? el.getAttribute('data-view-sec') : null };
  });
  ok('粘贴导入替换待办并跳到备份时的视图', imp.n === 1 && imp.first === '导入进来的待办' && imp.sec === 'works',
    JSON.stringify(imp));

  /* ---------- F. 清空：清完刷新不许把示例种子重新铺回来 ---------- */
  await mp.click('.nav[data-view="settings"]');   /* 导入后停在 works，先切回设置 */
  await mp.waitForTimeout(60);
  await mp.click('[data-act="clear"]');
  await mp.waitForTimeout(120);
  const cleared = await mp.evaluate(() => {
    const a = JSON.parse(localStorage.getItem('wb_demo_todos') || '[]');
    return a.length;
  });
  await mp.reload();
  await mp.waitForTimeout(150);
  const afterReload = await mp.evaluate(() =>
    JSON.parse(localStorage.getItem('wb_demo_todos') || '[]').length);
  ok('清空生效（0 条）', cleared === 0 && afterReload === 0, '清后=' + cleared + ' 刷新后=' + afterReload);

  await mctx.close();
  await page.close();
  await browser.close();
  console.log('='.repeat(40));
  if (fail) { console.log('有 ' + fail + ' 项不过'); process.exit(1); }
  console.log('交互、跨设备折叠、导入导出全通过。');
})();
