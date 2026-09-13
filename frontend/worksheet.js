import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import enUS from '@univerjs/preset-sheets-core/locales/en-US';
import '@univerjs/preset-sheets-core/lib/index.css';
import './worksheet.css';

let opened = null;
const make = (tag, text, cls) => { const el = document.createElement(tag); el.textContent = text || ''; if (cls) el.className = cls; return el; };
const textValue = value => Array.isArray(value) ? value.join(' · ') : value ?? '';
const hasErrors = row => !!(row?.errors?.length || row?.worksheet_error);

async function open(options) {
  if (opened) return;
  const catalog = options.kind === 'catalog';
  const saveUrl = catalog ? '/api/catalog/worksheet' : '/api/orders/worksheet';
  const readUrl = catalog ? saveUrl : saveUrl + '?batch_id=' + options.batchId;
  const responseRows = payload => catalog ? payload.items : payload.orders;
  const responseEditable = payload => catalog || payload.batch.status !== 'approved';
  const origin = document.activeElement;
  const shell = make('div', '', 'tdp-sheet-shell');
  shell.setAttribute('role', 'dialog'); shell.setAttribute('aria-modal', 'true');
  shell.setAttribute('aria-label', options.title);
  const top = make('div', '', 'tdp-sheet-top');
  top.append(make('strong', options.title));
  const status = make('span', 'Đang mở bảng…', 'tdp-sheet-status'); status.setAttribute('role', 'status');
  top.append(status);
  const button = (label, fn) => { const el = make('button', label); el.type = 'button'; el.onclick = fn; top.append(el); return el; };
  const close = button('×', () => shutdown()); close.className = 'tdp-sheet-close'; close.setAttribute('aria-label', 'Đóng bảng');
  shell.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !options.editable && !document.querySelector('dialog[open]')) {
      event.preventDefault(); event.stopPropagation(); shutdown();
    }
  });
  if (options.onImport) { const upload = button('Nạp bản mới', async () => { await shutdown(); if (disposed) options.onImport(); }); top.insertBefore(upload, close); }
  const notice = make('div', catalog ? 'Sửa tên hàng, ĐVT, thuế (KKKNT, KCT, 0%, 5%, 8%, 10%) và tên trên hóa đơn. Enter / Tab để tự lưu. Mã hàng chỉ xem; ĐVT đã sử dụng cần đối chiếu trước khi đổi.' : options.editable ? 'Nhập trực tiếp hoặc dán nhiều ô. Enter / Tab để chuyển ô và tự lưu. Cột tính toán chỉ xem.' : 'Bảng chỉ xem · chọn ô hoặc vùng ô rồi nhấn Ctrl+C (Mac: ⌘C) hoặc bấm Sao chép ô đã chọn.', 'tdp-sheet-notice');
  const normalNotice = notice.textContent;
  const updateNotice = () => { notice.textContent = (catalog ? `${rows.length} mã hàng · ` : options.batchId ?
    `${rows.length} dòng · ${rows.filter(row => row.errors?.length).length} dòng lỗi · ${rows.filter(row => row.warnings?.length).length} dòng cảnh báo. ` : '') + normalNotice; };
  const controls = make('div', '', 'tdp-sheet-controls');
  const actor = make('input'); actor.placeholder = 'Người sửa giá'; actor.setAttribute('aria-label', actor.placeholder); actor.maxLength = 120;
  const reason = make('input'); reason.placeholder = 'Lý do sửa giá'; reason.setAttribute('aria-label', reason.placeholder); reason.maxLength = 500;
  if (options.editable && !catalog) { controls.append(actor, reason); }
  const host = make('div', '', 'tdp-sheet-host');
  shell.append(top, notice, controls, host); document.body.append(shell);
  const previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
  // Inert the underlying application while keeping its filters and scroll position intact.
  const siblings = [...document.body.children].filter(el => el !== shell && !el.inert);
  siblings.forEach(el => el.inert = true);
  opened = { shell };
  let univer, book, api, sheet, subscription, muting = false, timer, pollTimer, polling = false, running = null, failed = null, activeSent = null, disposed = false;
  let rows = (options.rows || []).map(row => ({ ...row }));
  const pending = new Map();
  const columns = options.columns || [];
  const setStatus = (message, error = false) => { status.textContent = message; status.classList.toggle('is-error', error); };
  for (const action of options.downloads || []) {
    const download = button(action.label, async () => {
      download.disabled = true; setStatus('Đang tải file…');
      try { await action.run(); setStatus('Đã tải file theo bộ lọc lúc mở bảng'); }
      catch (error) { setStatus(error.message || 'Chưa tải được file. Bấm tải lại.', true); }
      finally { download.disabled = false; }
    });
    download.className = 'tdp-sheet-download';
    top.insertBefore(download, close);
  }
  if (!options.editable) {
    const copy = button('Sao chép ô đã chọn', async () => {
      try {
        const range = book?.getActiveSheet().getActiveRange();
        if (!range) throw new Error('Chọn ô hoặc vùng ô cần sao chép trước.');
        const quote = value => /[\t\r\n"]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
        const text = range.getDisplayValues().map(row => row.map(quote).join('\t')).join('\n');
        await navigator.clipboard.writeText(text);
        setStatus('Đã sao chép · có thể dán vào Excel hoặc tin nhắn');
      } catch (error) { setStatus('Chưa sao chép được: ' + error.message, true); }
    });
    top.insertBefore(copy, close);
  }
  const cell = (value, col, header = false, row = null) => ({ v: textValue(value), t: typeof value === 'number' ? 2 : 1,
    s: { ff: 'Arial', fs: 11, ht: col.numeric ? 3 : 1, vt: 2,
      bd: { b: { s: 1, cl: { rgb: '#dfe5e8' } }, r: { s: 1, cl: { rgb: '#dfe5e8' } } },
      bg: { rgb: header ? '#e9eef0' : hasErrors(row) ? '#fee2e2' : col.editable && options.editable ? '#ffffff' : '#f4f6f7' },
      cl: { rgb: !header && hasErrors(row) ? '#991b1b' : '#172b3a' },
      // Preserve literal quantity input until our decimal parser runs. The SDK's
      // English number parser otherwise turns the Vietnamese input 0,855 into 855.
      bl: header ? 1 : 0, ...(!header ? { n: { pattern: col.editable && options.editable && !col.money ? '@' :
        col.numeric ? (col.money || Number.isInteger(value) ? '#,##0' : '#,##0.######') : '@' } } : {}) } });
  const search = window.TDPTableSearch({
    scope: 'Trong bảng đang mở · không phân biệt dấu / hoa thường',
    active: () => !disposed && !document.querySelector('dialog[open]'),
    prepare: async () => { await waitForRender(); if (book?.isCellEditing()) await book.endEditingAsync(true); },
    cells: () => {
      if (options.workbookData && book) {
        sheet = book.getActiveSheet();
        const saved = options.workbookData.sheets[sheet.getSheetId()];
        return Object.entries(saved.cellData).flatMap(([r, row]) => Object.entries(row).map(([c, cell]) => ({
          key: `${saved.id}:${r}:${c}`, r: Number(r), c: Number(c),
          values: [cell.v, ...(typeof cell.v === 'number' ? [cell.v.toLocaleString('en-US', {maximumFractionDigits:6}), cell.v.toLocaleString('vi-VN', {maximumFractionDigits:6})] : [])]
        })));
      }
      if (!sheet || !rows.length) return [];
      const raw = sheet.getRange(1, 0, rows.length, columns.length).getRawValues();
      return raw.flatMap((row, r) => columns.map((col, c) => ({ key: `${r}:${c}`, r, c,
        values: [row[c], ...(col.numeric && typeof row[c] === 'number' ? [row[c].toLocaleString('en-US', { maximumFractionDigits: col.money ? 0 : 6 }), row[c].toLocaleString('vi-VN', { maximumFractionDigits: 6 })] : [])] })));
    },
    select: hit => revealCell(hit.r + (options.workbookData ? 0 : 1), hit.c)
  });
  top.insertBefore(search.element, close);
  async function waitForRender() {
    const deadline = Date.now() + 15000;
    while (!disposed && (!api || api.getCurrentLifecycleStage() < api.Enum.LifecycleStages.Rendered)) {
      if (Date.now() > deadline) throw new Error('Bảng chưa sẵn sàng');
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  }
  function revealCell(r, c) {
    sheet.setActiveRange(sheet.getRange(r, c));
    // The SDK's scrollToCell subtracts frozen column *indices*, which misses
    // the target when column widths differ. Scroll by actual unfrozen sizes.
    let offsetX = 0, offsetY = 0;
    for (let i = sheet.getFrozenColumns(); i < c; i++) offsetX += sheet.getColumnWidth(i);
    for (let i = sheet.getFrozenRows(); i < r; i++) offsetY += sheet.getRowHeight(i);
    api.syncExecuteCommand('sheet.operation.set-scroll', {
      unitId: book.getId(), sheetId: sheet.getSheetId(),
      sheetViewStartRow: 0, sheetViewStartColumn: 0, offsetX, offsetY
    });
  }
  function changed() {
    if (muting || disposed || !options.editable) return;
    const matrix = sheet.getRange(1, 0, rows.length, columns.length).getRawValues();
    rows.forEach((row, r) => columns.forEach((col, c) => {
      if (!col.editable) return;
      const value = matrix[r]?.[c] ?? '';
      const original = textValue(row[col.key]);
      const key = `${r}:${c}`;
      const inFlight = activeSent?.cells.find(entry => entry.r === r && entry.c === c);
      if (String(value) === String(original) && !inFlight) pending.delete(key);
      else pending.set(key, { r, c, value });
    }));
    if (pending.size) { setStatus(failed ? 'Lưu lỗi · phần sửa vẫn được giữ' : 'Đang lưu…', !!failed); clearTimeout(timer); timer = setTimeout(flush, 500); }
  }
  function buildRequest() {
    const grouped = new Map();
    for (const entry of pending.values()) {
      const row = rows[entry.r], col = columns[entry.c];
      if (!grouped.has(row.id)) grouped.set(row.id, { id: row.id, revision: row.worksheet_revision, values: {} });
      let value = entry.value;
      if (col.numeric && typeof value === 'string' && value.trim()) {
        // Accept decimal comma for quantities; grouping commas only for monetary input.
        const clean = value.trim().replace(/\s/g, '');
        value = Number(col.money ? clean.replace(/,/g, '') : clean.replace(',', '.'));
        if (!Number.isFinite(value)) throw new Error('Ô số chưa hợp lệ: ' + col.title);
      }
      grouped.get(row.id).values[col.key] = value;
    }
    return { request_id: crypto.randomUUID(), batch_id: options.batchId, actor: actor.value, reason: reason.value, items: [...grouped.values()] };
  }
  async function flush(retry = false) {
    clearTimeout(timer);
    if (running) { await running; if (!failed && pending.size) return flush(); return !failed; }
    if (failed && !retry) return false;
    if (!pending.size && !failed) return true;
    if (!pending.size && failed && !failed.uncertain) {
      failed = null; updateNotice(); setStatus('Đã giữ dữ liệu đang lưu'); return true;
    }
    const previousFailed = failed;
    let sent;
    try { sent = previousFailed?.uncertain ? previousFailed : { body: buildRequest(), cells: [...pending.values()] }; }
    catch (error) { setStatus(error.message, true); return false; }
    failed = null;
    activeSent = sent;
    setStatus('Đang lưu…');
    running = (async () => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);
        let response;
        try { response = await fetch(saveUrl, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sent.body), signal: controller.signal }); }
        catch (error) { sent.uncertain = true; throw error; }
        finally { clearTimeout(timeout); }
        if (response.status >= 500) sent.uncertain = true;
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error(payload.error || 'Không lưu được dữ liệu');
        const current = sheet.getRange(1, 0, rows.length, columns.length).getRawValues();
        const byId = new Map(responseRows(payload).map(row => [row.id, row]));
        // Keep edits made while the request was in flight; only acknowledge sent values.
        const newer = new Map();
        pending.forEach((entry, key) => {
          const saved = sent.cells.find(item => item.r === entry.r && item.c === entry.c);
          if (!saved || String(current[entry.r][entry.c] ?? '') !== String(saved.value)) newer.set(key, { ...entry, value: current[entry.r][entry.c] ?? '' });
        });
        muting = true;
        rows = rows.map(row => byId.get(row.id) || row);
        const acknowledged = {};
        rows.forEach((row, r) => acknowledged[r + 1] = Object.fromEntries(columns.map((col, c) => [c, cell(row[col.key], col, false, row)])));
        newer.forEach(entry => acknowledged[entry.r + 1][entry.c] = cell(entry.value, columns[entry.c], false, rows[entry.r]));
        // Server acknowledgements also refresh protected computed cells. A model mutation
        // avoids routing these trusted values through the user's protected-cell editor.
        api.syncExecuteCommand('sheet.mutation.set-range-values', { unitId: book.getId(), subUnitId: 'data', cellValue: acknowledged });
        muting = false;
        pending.clear(); newer.forEach((value, key) => pending.set(key, value));
        options.onSaved?.(payload);
        updateNotice();
        setStatus(pending.size ? 'Đang lưu…' : 'Đã lưu · ' + new Date().toLocaleTimeString('vi-VN'));
      } catch (error) {
        failed = sent; setStatus('Lưu lỗi: ' + (error.name === 'AbortError' ? 'Kết nối chậm, bấm Thử lưu lại' : error.message), true);
      }
    })();
    await running; running = null; activeSent = null;
    if (!failed && pending.size) return flush();
    return !failed;
  }
  async function shutdown(discard = false) {
    if (disposed) return;
    if (book) await book.endEditingAsync(!discard);
    if (options.editable && !discard) {
      changed();
      if (!await flush(true)) { notice.textContent = 'Chưa đóng vì còn phần sửa chưa lưu. Sửa ô lỗi hoặc bấm Thử lưu lại.'; return; }
    }
    disposed = true; search.dispose(); clearTimeout(timer); clearInterval(pollTimer); subscription?.dispose(); univer?.dispose();
    window.removeEventListener('beforeunload', guard); shell.remove(); siblings.forEach(el => el.inert = false);
    document.body.style.overflow = previousOverflow; opened = null; origin?.focus(); options.onClose?.();
  }
  function guard(event) { if (pending.size || running || failed) { event.preventDefault(); event.returnValue = ''; } }
  window.addEventListener('beforeunload', guard);
  if (options.editable) {
    const retry = make('button', 'Thử lưu lại'); retry.onclick = () => flush(true); controls.append(retry);
    const nextError = make('button', 'Tới dòng lỗi'); let errorRow = -1;
    nextError.onclick = () => { const candidates = rows.map((row, index) => hasErrors(row) ? index : -1).filter(index => index >= 0); errorRow = candidates.find(index => index > errorRow) ?? candidates[0] ?? -1; if (errorRow >= 0) revealCell(errorRow + 1, columns.length - 2); };
    controls.append(nextError);
    const recover = make('button', 'Đọc lại / đối chiếu');
    recover.onclick = async () => {
      await book.endEditingAsync(true); changed();
      if (running) await running;
      if (pending.size || failed) {
        if (!window.confirm('Phần chưa lưu sẽ được tải thành file đối chiếu trước khi mở dữ liệu mới nhất. Tiếp tục?')) return;
        const changes = [...pending.values()].map(entry => ({ dong: rows[entry.r].id,
          cot: columns[entry.c].title, truoc: rows[entry.r][columns[entry.c].key], dang_nhap: entry.value }));
        const url = URL.createObjectURL(new Blob([JSON.stringify({ ngay: options.title, thay_doi_chua_luu: changes }, null, 2)], { type: 'application/json' }));
        const link = make('a'); link.href = url; link.download = 'Phan_sua_chua_luu.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      try {
        const response = await fetch(readUrl);
        const payload = await response.json(); if (!response.ok) throw Error(payload.error || 'Không đọc được dữ liệu');
        options.rows = responseRows(payload); options.editable = responseEditable(payload);
        options.onSaved?.(payload); await shutdown(true); await open(options);
      } catch (error) { setStatus(error.message, true); }
    };
    controls.append(recover);
    actor.onchange = reason.onchange = () => flush(true);
  }
  try {
    ({ univer, univerAPI: api } = createUniver({ locale: LocaleType.EN_US, locales: { [LocaleType.EN_US]: mergeLocales(enUS) },
      presets: [UniverSheetsCorePreset({ container: host, header: true, toolbar: false, formulaBar: true, contextMenu: false,
        footer: { sheetBar: !!options.workbookData, statisticBar: true, menus: false, zoomSlider: true } })] }));
    const cellData = { 0: Object.fromEntries(columns.map((col, c) => [c, cell(col.title, col, true)])) };
    rows.forEach((row, r) => cellData[r + 1] = Object.fromEntries(columns.map((col, c) => [c, cell(row[col.key], col, false, row)])));
    book = api.createWorkbook(options.workbookData ? {...options.workbookData, id:crypto.randomUUID()} : { id: crypto.randomUUID(), name: options.title, sheetOrder: ['data'],
      sheets: { data: { id: 'data', name: 'Dữ liệu', rowCount: Math.max(rows.length + 1, 2), columnCount: columns.length,
        showGridlines: 1, defaultRowHeight: 24, defaultColumnWidth: 120, cellData, columnData: Object.fromEntries(columns.map((col, c) => [c, { w: col.width || 120 }])) } } });
    sheet = book.getActiveSheet();
    if (!options.workbookData) { sheet.setFrozenRows(1); sheet.setFrozenColumns(Math.min(2, columns.length)); }
    // Structural edits would invalidate the stable row-to-record relationship.
    const permitted = new Set(['sheet.command.set-range-values', 'sheet.mutation.set-range-values', 'sheet.command.clear-selection-content']);
    book.onBeforeCommandExecute(command => {
      if (muting) return;
      if (/sheet\.(command|mutation)\.(insert|remove|move|sort|rename|set-name|set-sheet-order|set-range-sort)/.test(command.id)) throw new Error(catalog ? 'Thêm mã qua nút Thêm mã hàng trong Danh mục.' : 'Thay đổi dòng qua chức năng nhập đơn để giữ liên kết chứng từ');
      if (permitted.has(command.id) && !options.editable) throw new Error('Bảng chỉ xem');
    });
    if (!options.editable) {
      const permission = book.getWorkbookPermission();
      await permission.setReadOnly();
      // Viewer mode disables copying by default. Allow copying visible cells
      // explicitly while keeping all edit/structure permissions disabled.
      await permission.setPoint(api.Enum.WorkbookPermissionPoint.CopyContent, true);
    }
    else {
      const ranges = [[0, 0, 1, columns.length], ...columns.flatMap((col, c) => col.editable ? [] : [[1, c, rows.length, 1]])];
      for (const [r, c, nr, nc] of ranges) {
        if (!nr) continue;
        const rule = await sheet.getRange(r, c, nr, nc).getRangePermission().protect({ name: 'Cột chỉ xem', allowViewByOthers: true });
        await rule.setPoint(api.Enum.RangePermissionPoint.Edit, false);
      }
      subscription = api.addEvent(api.Event.SheetValueChanged, changed);
    }
    // Render controllers (including scrolling) are registered after workbook creation.
    // Do not advertise readiness while the SDK is still mounting them.
    await waitForRender();
    if (disposed) return;
    setStatus(options.editable ? 'Đã tải · tự lưu khi sửa ô' : 'Chỉ xem');
    updateNotice();
    if (options.batchId || catalog) pollTimer = setInterval(async () => {
      if (disposed || polling || running || pending.size || failed || book.isCellEditing()) return;
      polling = true;
      try {
        const response = await fetch(readUrl);
        const payload = await response.json();
        if (!response.ok || disposed || running || pending.size || failed || book.isCellEditing()) return;
        const byId = new Map(responseRows(payload).map(row => [row.id, row]));
        const replaced = rows.length !== responseRows(payload).length || rows.some(row => !byId.has(row.id));
        const editable = responseEditable(payload);
        if (replaced || editable !== options.editable) {
          options.rows = responseRows(payload); options.editable = editable;
          await shutdown(); await open(options); return;
        }
        if (rows.some(row => row.worksheet_revision !== byId.get(row.id).worksheet_revision)) {
          rows = rows.map(row => byId.get(row.id));
          const cellValue = {};
          rows.forEach((row, r) => cellValue[r + 1] = Object.fromEntries(columns.map((col, c) => [c, cell(row[col.key], col, false, row)])));
          muting = true;
          api.syncExecuteCommand('sheet.mutation.set-range-values', { unitId: book.getId(), subUnitId: 'data', cellValue });
          muting = false; options.onSaved?.(payload); updateNotice(); setStatus('Đã đồng bộ dữ liệu mới');
        }
      } catch (_) { /* Keep visible data and local edits; the next interval retries. */ }
      finally { polling = false; }
    }, 5000);
    } catch (error) { setStatus('Không mở được bảng: ' + error.message, true); options.editable = false; }
  opened.flush = flush;
}

window.TDPWorksheet = { open, isOpen: () => !!opened };
