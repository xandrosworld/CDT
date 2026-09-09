// Run after npm run build:worksheet. Optional PLAYWRIGHT_MODULE overrides module resolution.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const staticRoot = path.resolve(__dirname, 'static');
const server = http.createServer((req, res) => {
  if (req.url === '/') {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    return res.end('<link rel="stylesheet" href="/worksheet-bundle/worksheet.css"><script src="/table-search.js"></script><script src="/worksheet-bundle/worksheet.js"></script>');
  }
  const file = path.resolve(staticRoot, '.' + req.url.split('?')[0]);
  if (!file.startsWith(staticRoot + path.sep) || !fs.existsSync(file)) { res.statusCode = 404; return res.end(); }
  res.setHeader('Content-Type', file.endsWith('.css') ? 'text/css' : 'application/javascript');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'], viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const errors = [], writes = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (!['GET','HEAD'].includes(r.method())) writes.push(r.url()); });
  try {
    await page.goto(base);
    await page.evaluate(async () => {
      const cells = {
        0: { 0: { v: 'CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT', t: 1 } },
        1: { 0: { v: '00123', t: 1 }, 1: { v: 'Thịt heo', t: 1 }, 2: { v: 0.08, t: 2, s: { n: { pattern: '0%' } } } },
        2: { 0: { v: '00002', t: 1 }, 1: { v: 'Tên có "ngoặc"\nxuống dòng', t: 1 }, 2: { v: -12.5, t: 2 } }
      };
      const sheet = id => ({ id, name: id, rowCount: 5, columnCount: 3, defaultRowHeight: 28, defaultColumnWidth: 180,
        cellData: cells, mergeData: [{ startRow: 0, endRow: 0, startColumn: 0, endColumn: 2 }] });
      await window.TDPWorksheet.open({ title: 'Copy regression', editable: false,
        workbookData: { id: 'fixture', name: 'Copy', sheetOrder: ['First','Second'], sheets: { First: sheet('First'), Second: sheet('Second') } } });
    });
    await page.locator('.tdp-sheet-status').filter({ hasText: 'Chỉ xem' }).waitFor();
    await page.waitForTimeout(500);
    const canvas = page.locator('canvas[id^="univer-sheet-main"]').first();
    const box = await canvas.boundingBox();
    // Name box selects an exact range without depending on canvas text rendering.
    const nameBox = page.locator('.tdp-sheet-shell input').last();
    const select = async range => { await nameBox.fill(range); await nameBox.press('Enter'); };
    const copyButton = async () => {
      await page.getByRole('button', { name: 'Sao chép ô đã chọn', exact: true }).click();
      await page.locator('.tdp-sheet-status').filter({ hasText: 'Đã sao chép' }).waitFor();
      return (await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g, '\n');
    };
    await page.mouse.click(box.x + 100, box.y + 40);
    await page.keyboard.press('Control+c');
    await page.waitForTimeout(300);
    assert.match(await page.evaluate(() => navigator.clipboard.readText()), /CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT/);
    assert.match(await copyButton(), /CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT/);
    await select('A2');
    assert.equal(await copyButton(), '00123');
    await select('A2:C3');
    assert.equal(await copyButton(), '00123\tThịt heo\t8%\n00002\t"Tên có ""ngoặc""\nxuống dòng"\t-12.5');
    // Keyboard copy of a selected range must work without granting edit access.
    await select('A2:C2');
    await page.keyboard.press('Control+c');
    await page.waitForTimeout(250);
    assert.equal((await page.evaluate(() => navigator.clipboard.readText())).trim(), '00123\tThịt heo\t8%');
    await select('A2');
    await page.keyboard.type('changed');
    await page.keyboard.press('Delete');
    await page.getByText('ok', { exact: true }).click();
    assert.equal(await copyButton(), '00123');
    await page.evaluate(() => navigator.clipboard.writeText('overwrite'));
    await select('A2');
    await page.keyboard.press('Control+v');
    await page.waitForTimeout(200);
    await page.getByText('ok', { exact: true }).click();
    assert.equal(await copyButton(), '00123');
    await page.getByText('Second', { exact: true }).click();
    await select('C2');
    assert.equal(await copyButton(), '8%');
    await page.getByRole('button', { name: 'Đóng bảng', exact: true }).click();
    await page.locator('.tdp-sheet-shell').waitFor({ state: 'detached' });
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    console.log('PASS: keyboard/button copy, merged cells, ranges, tax format, leading zeros, multiline text, sheet switch; editing/paste remain blocked, no writes.');
  } finally { await browser.close(); server.close(); }
})().catch(e => { console.error(e); server.close(); process.exitCode = 1; });
