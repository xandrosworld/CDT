const assert = require('node:assert/strict');
const {chromium} = require(process.env.TDP_PLAYWRIGHT_MODULE);
const base = 'http://127.0.0.1:18803';
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.addScriptTag({url:base+'/static/output-stock-web.js'});
    const open = (period = '2026-08') => page.evaluate(period => window.TdpOutputStockWeb({
      from:period+'-01', to:period === '2026-08' ? '2026-08-31' : '2026-09-30', code:'HH-01',
      esc:value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
      api:async (url, opts) => { const r = await fetch(url, opts); const j = await r.json(); if (!r.ok || j.ok === false) throw Error(j.error); return j; },
      onApplied:async () => {}, onExcel:() => { window.excelOpened = true; }
    }), period);
    await open();
    let dialog = page.locator('.output-stock-web');
    await dialog.locator('[name=new_code]').fill('REMAP-B');
    await dialog.locator('[name=qty]').fill('2');
    await dialog.locator('[data-item="REMAP-C"]').click();
    await dialog.locator('[data-item="HH-01"]').click();
    assert.equal(await dialog.locator('[name=new_code]').inputValue(), 'REMAP-B');
    assert.equal(await dialog.locator('[name=qty]').inputValue(), '2');
    await dialog.locator('[data-close]').click();
    await open();
    await dialog.locator('[name=new_code]').waitFor();
    assert.equal(await dialog.locator('[name=qty]').inputValue(), '2');
    await dialog.locator('[data-excel]').click();
    assert.equal(await page.evaluate(() => window.excelOpened), true);
    await dialog.locator('[data-edit] button[type=submit]').click();
    await dialog.locator('[data-confirm]').waitFor();
    assert.equal(await dialog.locator('[data-confirm]').isDisabled(), true);
    await dialog.locator('[name=confirmed]').check();
    await dialog.locator('[data-confirm]').click();
    assert.equal(await page.evaluate(() => document.activeElement.name), 'actor');
    await dialog.locator('[name=actor]').fill('Browser test');
    await dialog.locator('[data-confirm]').click();
    await dialog.locator('[data-history] summary').filter({hasText:'1 dòng'}).waitFor();
    await dialog.locator('[data-history] summary').click();
    assert.match(await dialog.locator('[data-history]').innerText(), /Browser test/);
    assert.match(await dialog.locator('[data-history]').innerText(), /REMAP-B/);
    assert.equal(await dialog.locator('[name=new_code]').inputValue(), '');
    const view = await (await page.request.get(base+'/api/inventory/output-remap/shortages?from=2026-08-01&to=2026-08-31')).json();
    assert.equal(view.items.find(r => r.product_code === 'HH-01').closing_qty, -2);
    assert.equal(view.history.length, 1);
    await page.screenshot({path:'D:/TDP_RAILWAY_PRIVATE/stock-history-browser.png',fullPage:true});
    await dialog.locator('[data-close]').click();
    await open('2026-09');
    await dialog.locator('[data-other-history] summary').click();
    assert.match(await dialog.locator('[data-other-history]').innerText(), /Browser test/);
    assert.match(await dialog.locator('[data-other-history]').innerText(), /2026-08-01/);
    assert.deepEqual(errors, []);
    console.log('PASS: switch/reopen preserves entries; explicit confirmation; history and stock updated once; Excel accessible.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
