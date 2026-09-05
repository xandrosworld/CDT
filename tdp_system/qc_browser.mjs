import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const appDir = resolve(import.meta.dirname);
const root = resolve(appDir, "..");
const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const chromePort = Number(process.env.TDP_QC_CHROME_PORT || "19341");
const appPort = Number(process.env.TDP_QC_APP_PORT || "18773");
const profile = mkdtempSync(join(tmpdir(), "tdp-real-qc-"));
const qcDb = join(profile, "qc_browser.sqlite3");
for (const suffix of ["", "-wal", "-shm"]) {
  try { rmSync(qcDb + suffix, { force: true }); } catch {}
}

const server = spawn("python", ["server.py", "--no-browser"], {
  cwd: appDir,
  env: {
    ...process.env,
    TDP_DB_PATH: qcDb,
    TDP_DATA_DIR: join(profile, "data"),
    TDP_EXPORT_DIR: join(profile, "exports"),
    TDP_PORT: String(appPort),
    TDP_ALLOW_LAN: "0",
    MSMI_API_BASE_URL: "http://127.0.0.1:9",
    MSMI_API_TOKEN: "qc-placeholder",
    MINVOICE_API_BASE_URL: "http://127.0.0.1:9",
    MINVOICE_USERNAME: "qc-placeholder",
    MINVOICE_PASSWORD: "qc-placeholder",
    MINVOICE_UNIT_CODE: "VP",
    PYTHONUTF8: "1",
  },
  windowsHide: true,
  stdio: "ignore",
});

const wait = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
const stage = (name) => console.error("[QC_BROWSER] " + name);
async function waitApp() {
  for (let i = 0; i < 300; i++) {
    try {
      const result = await fetch("http://127.0.0.1:" + appPort + "/health");
      if (result.ok) return;
    } catch {}
    await wait(100);
  }
  throw new Error("Máy chủ không khởi động");
}

let browser;
try {
  await waitApp();
  const source = readFileSync(join(root, "Tách212223.xlsx"));
  const form = new FormData();
  form.append("work_date", "2026-08-28");
  form.append("file", new Blob([source]), "Tách212223.xlsx");
  const analyzedResponse = await fetch("http://127.0.0.1:" + appPort + "/api/import/analyze", { method: "POST", body: form });
  const analyzed = await analyzedResponse.json();
  if (!analyzedResponse.ok || !analyzed.ok || !Array.isArray(analyzed.sheets)) {
    throw new Error("Không phân tích được file QC: status=" + analyzedResponse.status +
      " code=" + String(analyzed.error_code || analyzed.code || ""));
  }
  const importedResponse = await fetch("http://127.0.0.1:" + appPort + "/api/import/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token: analyzed.token,
      sheets: analyzed.sheets.filter((item) => !analyzed.strictDaily || Boolean(item.confirmAvailable)).map((item) => item.name),
      work_date: analyzed.detectedWorkDate || "2026-08-28",
      state_hash: analyzed.stateHash,
    }),
  });
  const imported = await importedResponse.json();
  if (!imported.ok || !Array.isArray(imported.orders) || imported.orders.length !== 408) {
    throw new Error("Nhập file trình duyệt không đúng: ok=" + Boolean(imported.ok) +
      " count=" + (Array.isArray(imported.orders) ? imported.orders.length : -1) +
      " code=" + String(imported.error_code || "") +
      " error=" + String(imported.error || ""));
  }
  stage("initial_import_ok");

  browser = spawn(chromePath, [
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=" + chromePort, "--user-data-dir=" + profile,
    "--window-size=1440,1000", "about:blank",
  ], { windowsHide: true, stdio: "ignore" });

  async function chromeJson(path) {
    for (let i = 0; i < 80; i++) {
      try { return await (await fetch("http://127.0.0.1:" + chromePort + path)).json(); }
      catch { await wait(100); }
    }
    throw new Error("Không kết nối được Chrome");
  }
  const targets = await chromeJson("/json/list");
  const target = targets.find((item) => item.type === "page") || targets[0];
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolvePromise, reject) => {
    ws.addEventListener("open", resolvePromise, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  let seq = 0;
  const pending = new Map();
  const errors = [];
  const httpErrors = [];
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const pendingItem = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) pendingItem.reject(new Error(message.error.message)); else pendingItem.resolve(message.result);
    }
    if (message.method === "Runtime.exceptionThrown") {
      const details = message.params.exceptionDetails;
      errors.push(details.exception?.description || details.text || "Runtime exception");
    }
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error" &&
        !message.params.entry.text.startsWith("Failed to load resource:")) {
      errors.push(message.params.entry.text);
    }
    if (message.method === "Network.responseReceived" && message.params.response.status >= 400) {
      try {
        const failedUrl = new URL(message.params.response.url);
        if (failedUrl.hostname === "127.0.0.1" && Number(failedUrl.port) === appPort) {
          httpErrors.push(message.params.response.status + " " + failedUrl.pathname);
        }
      } catch {}
    }
  });
  function send(method, params = {}) {
    const id = ++seq;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolvePromise, reject) => pending.set(id, { resolve: resolvePromise, reject }));
  }
  async function evaluate(expression) {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  }
  function assert(value, message) { if (!value) throw new Error(message); }
  async function waitForText(text, loops = 100) {
    for (let i = 0; i < loops; i++) {
      if (await evaluate("document.body.innerText.includes(" + JSON.stringify(text) + ")")) return true;
      await wait(100);
    }
    return false;
  }

  await send("Runtime.enable");
  await send("Log.enable");
  await send("Network.enable");
  await send("Page.enable");
  await send("DOM.enable");
  await send("Page.navigate", { url: "http://127.0.0.1:" + appPort });
  for (let i = 0; i < 80; i++) {
    await wait(100);
    if (await evaluate("document.readyState === 'complete' && document.body.innerText.includes('408 dòng')")) break;
  }
  assert((await evaluate("document.title")).includes("Thành Đạt Phát"), "Sai tiêu đề");
  const requiredViews = [
    "home", "orders", "purchases", "deliveries", "quotes", "reports", "documents",
    "inventory", "msmi", "kitchen", "payroll", "printing", "settings",
  ];
  assert(await evaluate("JSON.stringify(Array.from(document.querySelectorAll('.nav-item')).map(x=>x.dataset.view))") === JSON.stringify(requiredViews), "Thiếu hoặc sai thứ tự menu hợp đồng");
  assert(await evaluate("document.body.innerText.includes('408 dòng')"), "Trang chủ không hiện đúng số dòng");

  const checks = [
    ["orders", "27 cảnh báo cần xác nhận"],
    ["purchases", "Không làm thay đổi đơn khách"],
    ["deliveries", "Dùng số thực giao"],
    ["reports", "Ghi nhận thu khách hàng"],
    ["documents", "Các file của ngày"],
    ["inventory", "Nạp Excel tồn đầu kỳ"],
    ["msmi", "Nguồn: mSMI · chỉ tải về"],
    ["kitchen", "Nạp file định mức và đặt hàng"],
    ["payroll", "Nạp file chấm công"],
    ["printing", "3. In một nút"],
    ["settings", "Những việc phần mềm tự làm và không tự làm"],
  ];
  for (const [view, text] of checks) {
    await evaluate("document.querySelector('[data-view=\"" + view + "\"]').click()");
    assert(await waitForText(text), "Sai màn hình " + view + ": thiếu " + text);
    const languageAndLayout = await evaluate(`(()=>{
      const bodyText=document.body.innerText;
      const banned=['BẢN VẬN HÀNH THẬT','TĐK–NXT / kho hóa đơn','Xưởng cơm / PO',
        'Tải bản sao lưu SQLite','Ranh giới tích hợp','API M-Invoice hoạt động',
        'The requested URL was not found on the server'];
      const clipped=Array.from(document.querySelectorAll('button:not([hidden]), a.btn:not([hidden])'))
        .filter(node=>node.offsetParent!==null && (node.scrollWidth>node.clientWidth+2 || node.scrollHeight>node.clientHeight+2))
        .map(node=>node.textContent.trim()).filter(Boolean);
      return {banned:banned.filter(text=>bodyText.includes(text)),clipped};
    })()`);
    assert(languageAndLayout.banned.length === 0,
      "Màn hình " + view + " còn chữ kỹ thuật/demo: " + JSON.stringify(languageAndLayout.banned));
    assert(languageAndLayout.clipped.length === 0,
      "Màn hình " + view + " có nút bị cắt chữ: " + JSON.stringify(languageAndLayout.clipped));
    if (view === "reports") {
      const dateDisplays = await evaluate(`Array.from(document.querySelectorAll('.localized-date-display'))
        .map(input=>input.value).filter(Boolean)`);
      assert(dateDisplays.length >= 2 && dateDisplays.every(value=>/^\d{2}\/\d{2}\/\d{4}$/.test(value)),
        "Ngày trên báo cáo/công nợ chưa hiển thị dd/mm/yyyy: " + JSON.stringify(dateDisplays));
    }
    if (view === "payroll") {
      const payrollUi = await evaluate(`(()=>{const button=document.querySelector('#staffForm button[type="submit"]');
        const month=document.querySelector('#payrollMonth')?.closest('.localized-date-control')?.querySelector('.localized-date-display');
        const style=button?getComputedStyle(button):null;
        return {month:month?.value||'',button:Boolean(button),whiteSpace:style?.whiteSpace||'',height:button?.getBoundingClientRect().height||0,
          overflow:button?button.scrollWidth>button.clientWidth:false}})()`);
      assert(/^\d{2}\/\d{4}$/.test(payrollUi.month), "Tháng lương chưa hiển thị mm/yyyy: " + payrollUi.month);
      assert(payrollUi.button && payrollUi.whiteSpace === "nowrap" && payrollUi.height >= 40 && !payrollUi.overflow,
        "Nút Lưu nhân sự còn vỡ dòng/biến dạng: " + JSON.stringify(payrollUi));
    }
  }
  stage("main_views_ok");
  // The historical fixture references catalog codes supplied by the official
  // opening workbook later in this run.  Before that import, readiness must
  // fail closed with a structured conflict instead of inventing stock/codes.
  const historicalReadinessBeforeOpening = await evaluate(`fetch('/api/outgoing-invoices/readiness/${imported.batch.id}')
    .then(async r=>{const payload=await r.json();return {status:r.status,ok:payload.ok,code:String(payload.code||'')}})`);
  assert(historicalReadinessBeforeOpening.status === 409 &&
      historicalReadinessBeforeOpening.ok === false &&
      historicalReadinessBeforeOpening.code === "unknown_product_code",
    "Phiên lịch sử chưa có tồn đầu không bị chặn có cấu trúc: " +
      JSON.stringify(historicalReadinessBeforeOpening));
  assert(await evaluate("document.querySelector('#documentSettingsForm [name=\"payment_requester\"]').value === 'VŨ THỊ THỤY'"), "Sai người đại diện trên đề nghị thanh toán");
  assert(await evaluate("document.querySelector('#documentSettingsForm [name=\"payment_bank_account\"]').value === '1052787580'"), "Sai tài khoản đề nghị thanh toán");
  assert(await evaluate("document.querySelector('#documentSettingsForm [name=\"payment_bank_name\"]').value.includes('Ngoại Thương Việt Nam')"), "Sai ngân hàng đề nghị thanh toán");
  await evaluate("document.querySelector('#documentSettingsForm button[type=\"submit\"]').click()");
  assert(await waitForText("Đã lưu thông tin đề nghị thanh toán"), "Không lưu được cấu hình đề nghị thanh toán qua giao diện");

  // Supplier grouping rule and multi-period debt controls are exercised through the rendered forms.
  await evaluate("document.querySelector('[data-view=\"purchases\"]').click()");
  assert(await waitForText("Không làm thay đổi đơn khách", 120), "Không nạp được nhu cầu NCC");
  assert(await evaluate("Boolean(document.querySelector('[data-action=\"toggle-supplier-rule\"]'))"), "Thiếu nút gộp/tách NCC trên giao diện");
  await evaluate("document.querySelector('[data-action=\"toggle-supplier-rule\"]').click()");
  assert(await waitForText("Đã gộp đơn nhà cung cấp", 120) || await waitForText("Đã tách đơn nhà cung cấp", 10), "Không lưu được quy tắc gộp/tách nhà cung cấp");

  await evaluate("document.querySelector('[data-view=\"reports\"]').click()");
  assert(await waitForText("Lọc công nợ", 120), "Thiếu bộ lọc công nợ nhiều kỳ");
  await evaluate("(()=>{const f=document.querySelector('#debtPeriodForm');f.from.value='2026-08-01';f.to.value='2026-08-31';f.requestSubmit()})()");
  assert(await waitForText("Điều chỉnh công nợ", 120), "Không xem được công nợ theo khoảng ngày");
  await evaluate("(()=>{const f=document.querySelector('#debtAdjustmentForm');f.adjustment_date.value='2026-08-28';f.party_type.value='contractor';f.party_code.value='HATRAN';f.amount.value='123';f.note.value='Chrome QC';f.requestSubmit()})()");
  assert(await waitForText("Đã lưu điều chỉnh công nợ", 120), "Không lưu được điều chỉnh công nợ qua giao diện");
  const debtFromUi = await evaluate("fetch('/api/debts?from=2026-08-01&to=2026-08-31').then(r=>r.json())");
  assert(debtFromUi.ok && debtFromUi.contractors.HATRAN.period_adjustment === 123, "Điều chỉnh công nợ không vào đúng kỳ");
  const debtExportFromUi = await evaluate("fetch('/api/export/debts?from=2026-08-01&to=2026-08-31').then(async r=>({ok:r.ok,size:(await r.arrayBuffer()).byteLength}))");
  assert(debtExportFromUi.ok && debtExportFromUi.size > 1000, "Không tải được Excel công nợ kỳ");
  stage("debt_ok");

  await evaluate("document.querySelector('[data-view=\"orders\"]').click()");
  await wait(100);
  await evaluate("document.querySelector('[data-action=\"edit-order\"]').click()");
  assert(await evaluate("!document.querySelector('#modalBackdrop').hidden"), "Không mở được form sửa");
  assert(await evaluate("document.querySelector('#orderForm input[name=\"product_code\"]').value.length > 0"), "Form sửa thiếu dữ liệu");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");
  await evaluate("document.querySelector('[data-action=\"paste-orders\"]').click()");
  assert(await evaluate("document.querySelector('#pasteText').placeholder.includes('POT')"), "Không mở được form dán Excel");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");

  await evaluate("document.querySelector('[data-view=\"quotes\"]').click()");
  for (let i = 0; i < 50; i++) {
    await wait(100);
    if (await evaluate("Boolean(document.querySelector('#quoteContractor'))")) break;
  }
  assert(await evaluate("document.body.innerText.includes('Bảng giá HATRAN')"), "Không nạp được bảng giá");
  await evaluate("const s=document.querySelector('#quoteContractor');s.value='GIANHAPTAY';s.dispatchEvent(new Event('change',{bubbles:true}))");
  for (let i = 0; i < 50; i++) {
    await wait(100);
    if (await evaluate("document.body.innerText.includes('không dùng bảng giá nhà thầu')")) break;
  }
  assert(await evaluate("document.body.innerText.includes('không dùng bảng giá nhà thầu')"), "Sai quy tắc giá theo ngày");

  // Real file-picker flow: analyze workbook, default to the completed-order sheet, then import it.
  await evaluate("document.querySelector('[data-view=\"orders\"]').click()");
  const documentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const inputNode = await send("DOM.querySelector", {
    nodeId: documentNode.root.nodeId,
    selector: "#excelInput"
  });
  await send("DOM.setFileInputFiles", {
    files: [join(root, "Em Thành.xlsx")],
    nodeId: inputNode.nodeId
  });
  for (let i = 0; i < 100; i++) {
    await wait(100);
    if (await evaluate("document.querySelector('#modalTitle')?.textContent.includes('Chọn sheet')")) break;
  }
  assert(await evaluate("document.querySelectorAll('.sheet-choice').length >= 1"), "Không nhận diện được sheet đơn trong file tổng");
  await evaluate("(()=>{if(document.querySelectorAll('.sheet-choice input:checked').length===0){const choices=Array.from(document.querySelectorAll('.sheet-choice input:not(:disabled)'));const target=choices.find(x=>x.value.toLowerCase().includes('đơn hàng'))||choices[0];if(target)target.checked=true;}})()");
  assert(await evaluate("document.querySelectorAll('.sheet-choice input:checked').length === 1"), "Luồng QC phải chọn rõ đúng một sheet đơn");
  assert(await evaluate("document.querySelector('.sheet-choice input:checked').value.toLowerCase().includes('đơn hàng')"), "Chọn nhầm sheet đơn cần nhập");
  await evaluate("document.querySelector('#orderForm button[type=\"submit\"]').click()");
  for (let i = 0; i < 150; i++) {
    await wait(100);
    if (await evaluate("document.body.innerText.includes('323 dòng đã') || document.body.innerText.includes('323 dòng lỗi')")) break;
  }
  assert(await evaluate("document.body.innerText.includes('323 dòng')"), "Không nhập đúng sheet đã chọn");
  stage("daily_import_ok");

  // Save an edit and a pasted row through the real forms on this disposable 323-row batch.
  await evaluate("document.querySelector('[data-action=\"edit-order\"]').click()");
  assert(await evaluate("!document.querySelector('#modalBackdrop').hidden"), "Không mở lại được form sửa sau import");
  await evaluate("(()=>{const n=document.querySelector('#orderForm [name=\"note\"]');n.value='Đã sửa qua Chrome QC';document.querySelector('#orderForm').requestSubmit()})()");
  assert(await waitForText("Đã lưu dòng đơn và kiểm tra lại", 120), "Không lưu được dòng đã sửa qua giao diện");
  assert(await waitForText("Đã sửa qua Chrome QC", 120), "Giao diện không hiện lại ghi chú vừa lưu");
  await evaluate("document.querySelector('[data-action=\"paste-orders\"]').click()");
  await evaluate("(()=>{const p=document.querySelector('#pasteText');p.value='POT\\tHành tây\\t1\\tkho\\t14000\\t16000\\tKKKNT';document.querySelector('#orderForm').requestSubmit()})()");
  assert(await waitForText("Đã thêm 1 dòng và tự kiểm tra", 120), "Không dán thêm được dòng phát sinh qua giao diện");
  assert(await evaluate("document.querySelectorAll('tbody tr').length === 324"), "Dòng dán phát sinh không xuất hiện trong lưới");

  // A dated file must select only the matching dated sheet, not aggregate/history sheets.
  const datedDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const datedInputNode = await send("DOM.querySelector", {
    nodeId: datedDocumentNode.root.nodeId,
    selector: "#excelInput"
  });
  await send("DOM.setFileInputFiles", {
    files: [join(root, "_HANDOFF", "EXTERNAL_INPUTS", "Don hàng 29.08.xlsx")],
    nodeId: datedInputNode.nodeId
  });
  for (let i = 0; i < 300; i++) {
    await wait(100);
    if (await evaluate("!document.querySelector('#modalBackdrop').hidden && document.querySelector('#orderForm').innerText.includes('Don hàng 29.08.xlsx')")) break;
  }
  assert(await evaluate("!document.querySelector('#modalBackdrop').hidden && document.querySelector('#orderForm').innerText.includes('Don hàng 29.08.xlsx')"), "Không mở được file ngày 29.08 qua bộ chọn file");
  assert(await evaluate("document.querySelectorAll('.sheet-choice input:checked').length === 1"), "File ngày đang chọn trùng nhiều sheet");
  assert(await evaluate("document.querySelector('.sheet-choice input:checked').value === '29.08'"), "Không tự chọn đúng sheet 29.08");
  assert(await evaluate("document.querySelector('input[name=\"work_date\"]').value === '2026-08-29'"), "Ngày làm việc dự phòng không khớp tên file");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");

  // Real opening-inventory picker flow: preview, explicit confirmation, then idempotent re-import.
  await evaluate("document.querySelector('[data-view=\"inventory\"]').click()");
  assert(await waitForText("Nạp Excel tồn đầu kỳ"), "Không mở được màn hình tồn đầu kỳ");
  await evaluate("const p=document.querySelector('#openingForm [name=\"period\"]');p.value='2026-08';document.querySelector('[data-action=\"choose-opening-workbook\"]').click()");
  const openingDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const openingInputNode = await send("DOM.querySelector", {
    nodeId: openingDocumentNode.root.nodeId,
    selector: "#openingWorkbookInput"
  });
  const openingPath = join(root, "_HANDOFF", "EXTERNAL_INPUTS", "TĐK T8-2026.xlsx thụy.xlsx");
  await send("DOM.setFileInputFiles", { files: [openingPath], nodeId: openingInputNode.nodeId });
  assert(await waitForText("395 dòng nguồn → 334 mã TĐP", 150), "Không xem trước đúng file tồn đầu kỳ thật");
  assert(await evaluate("document.body.innerText.includes('113 mã mới') && document.body.innerText.includes('4 mã tồn âm') && document.body.innerText.includes('0 lỗi')"), "Sai số liệu xem trước tồn đầu kỳ");
  assert(await evaluate("!document.querySelector('[data-action=\"confirm-opening-import\"]').disabled"), "Nút xác nhận tồn đầu kỳ bị khóa sai");
  await evaluate("document.querySelector('[data-action=\"confirm-opening-import\"]').click()");
  assert(await waitForText("Đã nạp 334 mã tồn đầu kỳ · thêm 113 mã hàng mới", 150), "Không xác nhận được tồn đầu kỳ");

  const openingRepeatDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const openingRepeatInput = await send("DOM.querySelector", { nodeId: openingRepeatDocument.root.nodeId, selector: "#openingWorkbookInput" });
  await send("DOM.setFileInputFiles", { files: [openingPath], nodeId: openingRepeatInput.nodeId });
  assert(await waitForText("395 dòng nguồn → 334 mã TĐP", 150), "Không xem trước được lần nạp lại tồn đầu kỳ");
  assert(await evaluate("document.body.innerText.includes('0 mã mới')"), "Nạp lại tồn đầu kỳ vẫn nhận nhầm mã mới");
  await evaluate("document.querySelector('[data-action=\"confirm-opening-import\"]').click()");
  assert(await waitForText("Đã nạp 334 mã tồn đầu kỳ · thêm 0 mã hàng mới", 150), "Nạp lại tồn đầu kỳ không cập nhật an toàn");
  stage("opening_ok");

  // Real kitchen workbook picker flow: 5 plans / 54 items / XCOM and repeat update.
  await evaluate("document.querySelector('[data-view=\"kitchen\"]').click()");
  assert(await waitForText("Nạp file định mức và đặt hàng"), "Không mở được màn hình suất ăn");
  await evaluate("const d=document.querySelector('#kitchenDate');d.value='2026-08-30';d.dispatchEvent(new Event('change',{bubbles:true}))");
  assert(await waitForText("Nạp file định mức và đặt hàng"), "Không đổi được ngày suất ăn");
  const kitchenDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const kitchenInputNode = await send("DOM.querySelector", { nodeId: kitchenDocumentNode.root.nodeId, selector: "#kitchenWorkbookInput" });
  const kitchenPath = join(root, "_HANDOFF", "EXTERNAL_INPUTS", "xưởng cơm.xlsx");
  await send("DOM.setFileInputFiles", { files: [kitchenPath], nodeId: kitchenInputNode.nodeId });
  assert(await waitForText("5 nhóm bếp/ca · 54 nguyên liệu", 150), "Không xem trước đúng file xưởng cơm thật");
  assert(await evaluate("document.body.innerText.includes('0 nhóm lỗi') && document.body.innerText.includes('MAZDA') && document.body.innerText.includes('46 suất tổng')"), "Sai số liệu xem trước xưởng cơm");
  await evaluate("document.querySelector('[data-action=\"confirm-kitchen-import\"]').click()");
  assert(await waitForText("Đã nạp 5 nhóm xưởng cơm và 54 nguyên liệu", 150), "Không xác nhận được file xưởng cơm");

  const kitchenRepeatDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const kitchenRepeatInput = await send("DOM.querySelector", { nodeId: kitchenRepeatDocument.root.nodeId, selector: "#kitchenWorkbookInput" });
  await send("DOM.setFileInputFiles", { files: [kitchenPath], nodeId: kitchenRepeatInput.nodeId });
  assert(await waitForText("5 cập nhật", 150), "Nạp lại xưởng cơm không chuyển sang cập nhật");
  await evaluate("document.querySelector('[data-action=\"confirm-kitchen-import\"]').click()");
  assert(await waitForText("Đã nạp 5 nhóm xưởng cơm và 54 nguyên liệu", 150), "Không xác nhận được lần nạp lại xưởng cơm");
  stage("kitchen_ok");

  // Monthly meal attendance from the customer's real workbook; actual meals stay separate from PO plans.
  const mealAttendanceDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const mealAttendanceInput = await send("DOM.querySelector", { nodeId: mealAttendanceDocument.root.nodeId, selector: "#mealAttendanceInput" });
  const mealAttendancePath = join(root, "bosung.30.8.26", "CHẤM CÔNG+ SUẤT ĂN  2026", "SUẤT ĂN XƯỞNG CƠM 2026", "SUẤT ĂN T8.2026.xlsx");
  await send("DOM.setFileInputFiles", { files: [mealAttendancePath], nodeId: mealAttendanceInput.nodeId });
  assert(await waitForText("205 dòng ngày/bếp/ca", 180), "Không xem trước đúng file chấm suất ăn tháng 8");
  assert(await evaluate("document.body.innerText.includes('28 ngày') && document.body.innerText.includes('6 bếp') && document.body.innerText.includes('Tổng thực ăn 6.020 suất') && document.body.innerText.includes('0 lỗi')"), "Sai số liệu xem trước chấm suất ăn");
  await evaluate("document.querySelector('[data-action=\"confirm-meal-attendance-import\"]').click()");
  assert(await waitForText("Đã nạp 205 dòng chấm suất · thêm 205", 180), "Không xác nhận được chấm suất ăn");
  assert(await waitForText("tổng 6.020 suất thực ăn", 120), "Màn hình không hiển thị tổng suất thực tế sau nhập");

  const repeatMealDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const repeatMealInput = await send("DOM.querySelector", { nodeId: repeatMealDocument.root.nodeId, selector: "#mealAttendanceInput" });
  await send("DOM.setFileInputFiles", { files: [mealAttendancePath], nodeId: repeatMealInput.nodeId });
  assert(await waitForText("205 không đổi", 180), "Nạp lại chấm suất không nhận diện dữ liệu không đổi");
  await evaluate("document.querySelector('[data-action=\"confirm-meal-attendance-import\"]').click()");
  assert(await waitForText("không đổi 205", 180), "Nạp lại chấm suất không chống cộng trùng");
  stage("meal_attendance_ok");

  // Real attendance picker flow and payroll result from the customer's August workbook.
  await evaluate("document.querySelector('[data-view=\"payroll\"]').click()");
  assert(await waitForText("Nạp file chấm công"), "Không mở được màn hình chấm công/lương");
  await evaluate("const m=document.querySelector('#payrollMonth');m.value='2026-08';m.dispatchEvent(new Event('change',{bubbles:true}))");
  assert(await waitForText("Nạp file chấm công"), "Không đổi được kỳ bảng lương");
  const attendanceDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const attendanceInputNode = await send("DOM.querySelector", { nodeId: attendanceDocumentNode.root.nodeId, selector: "#attendanceInput" });
  const attendancePath = join(root, "bosung.30.8.26", "CHẤM CÔNG+ SUẤT ĂN  2026", "CHẤM CÔNG T8.2026.xlsx");
  await send("DOM.setFileInputFiles", { files: [attendancePath], nodeId: attendanceInputNode.nodeId });
  assert(await waitForText("Xem trước chấm công 2026-08", 180), "Không xem trước được file chấm công tháng 8");
  await evaluate("document.querySelector('[data-action=\"confirm-attendance-import\"]').click()");
  assert(await waitForText("TRIEN", 180), "Không nạp được nhân sự từ file chấm công tháng 8");
  assert(await evaluate("document.body.innerText.includes('8.000.000 đ')"), "Thực lĩnh của TRIEN không khớp file khách");
  assert(await evaluate("Boolean(document.querySelector('#attendanceForm')) && Boolean(document.querySelector('#payrollAdjustmentForm'))"), "Thiếu form chấm/sửa công hoặc khoản lương tháng");
  const payrollExportFromUi = await evaluate("fetch('/api/export/payroll?month=2026-08').then(async r=>({ok:r.ok,size:(await r.arrayBuffer()).byteLength}))");
  assert(payrollExportFromUi.ok && payrollExportFromUi.size > 1000, "Không tải được bảng lương tháng");
  stage("payroll_ok");

  // Use a small valid batch for print/outgoing UI.  The 408-row historical
  // fixture intentionally contains a seller/day total over the legal 5m cap,
  // so the production guard must block that fixture instead of being bypassed.
  // Stock must come from the official opening-workbook import above.  Cross-check
  // the canonical quantity endpoint with the moving-average projection; never
  // seed this flow through the retired direct-JSON opening shortcut.
  const operationalSeed = await evaluate(`(async()=>{
    const json=(url,body)=>fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
    const read=url=>fetch(url).then(async r=>({httpStatus:r.status,payload:await r.json()}));
    const [stockResult,valuationResult]=await Promise.all([
      read('/api/invoice-inventory?as_of=2026-08-31'),
      read('/api/invoice-valuation?from=2026-08-01&to=2026-08-31')
    ]);
    const stock=stockResult.payload||{};
    const valuation=valuationResult.payload||{};
    const valuedByCode=new Map((valuation.items||[]).map(item=>[item.product_code,item]));
    const positiveCount=(stock.items||[]).filter(item=>Number(item.closing_qty)>0).length;
    const valuedCount=(valuation.items||[]).filter(item=>item.valuation_status==='ok' && Number(item.average_unit_cost)>0).length;
    const selected=(stock.items||[]).find(item=>{
      const valued=valuedByCode.get(item.product_code);
      const stockQty=Number(item.closing_qty);
      const valuedQty=Number(valued&&valued.closing_qty);
      return stockQty>=2 && Number.isFinite(stockQty) && valued && valued.valuation_status==='ok' &&
        Number.isFinite(valuedQty) && Math.abs(stockQty-valuedQty)<=0.000001 &&
        Number(valued.average_unit_cost)>0 && String(item.unit||'').trim() &&
        String(item.unit||'').trim().toLocaleLowerCase('vi')===String(valued.unit||'').trim().toLocaleLowerCase('vi');
    });
    if(!stock.ok || stock.read_only!==true || !valuation.ok || valuation.read_only!==true ||
       !valuation.opening_period || !selected){
      return {canonicalStockOk:false,orderOk:false,approvedOk:false,reason:'canonical_candidate_missing',
        stockHttpStatus:stockResult.httpStatus,valuationHttpStatus:valuationResult.httpStatus,
        stockCount:(stock.items||[]).length,positiveCount,valuationCount:(valuation.items||[]).length,valuedCount,
        stockCode:String(stock.error_code||stock.code||''),valuationCode:String(valuation.error_code||valuation.code||'')};
    }
    const valued=valuedByCode.get(selected.product_code);
    const qty=Math.min(2,Number(selected.closing_qty));
    const buyPrice=Math.max(1,Math.round(Number(valued.average_unit_cost)));
    const batch=await json('/api/batches',{work_date:'2026-08-31'});
    if(!batch.ok || !batch.batch){
      return {canonicalStockOk:true,orderOk:false,approvedOk:false,reason:'batch_create_failed',
        code:String(batch.error_code||batch.code||'')};
    }
    const order=await json('/api/orders',{batch_id:batch.batch.id,contractor:'HATRAN',kitchen:'POT',product_code:selected.product_code,qty,actual_received:qty,actual_delivered:qty,unit:selected.unit,supplier:'kho',buy_price:buyPrice,sell_price:buyPrice+1000,tax:'KKKNT'});
    if(!order.ok){
      return {batchId:batch.batch.id,canonicalStockOk:true,orderOk:false,approvedOk:false,
        reason:'order_create_failed',code:String(order.error_code||order.code||'')};
    }
    const approved=await json('/api/batches/'+batch.batch.id+'/approve',{});
    return {batchId:batch.batch.id,canonicalStockOk:true,orderOk:true,approvedOk:approved.ok,
      reason:approved.ok?'':'batch_approve_failed',code:String(approved.error_code||approved.code||'')};
  })()`);
  assert(operationalSeed.canonicalStockOk && operationalSeed.orderOk && operationalSeed.approvedOk,
    "Không tạo được phiên QC vận hành từ tồn canonical đã nạp chính thức: " + JSON.stringify(operationalSeed));
  stage("operational_seed_ok");
  await send("Page.navigate", { url: "http://127.0.0.1:" + appPort });
  for (let i = 0; i < 120; i++) {
    await wait(100);
    if (await evaluate("Boolean(document.querySelector('#batchSelect option[value=\"" + operationalSeed.batchId + "\"]'))")) break;
  }
  await evaluate("(()=>{const selectedBatch=document.querySelector('#batchSelect');selectedBatch.value='" + operationalSeed.batchId + "';selectedBatch.dispatchEvent(new Event('change',{bubbles:true}))})()");
  assert(await waitForText("1 dòng", 120), "Không nạp được phiên QC vận hành một dòng");
  assert(Number(await evaluate("document.querySelector('#batchSelect').value")) === operationalSeed.batchId,
    "Giao diện không giữ đúng phiên QC vận hành");
  const activeBatchId = operationalSeed.batchId;
  await evaluate("document.querySelector('[data-view=\"printing\"]').click()");
  assert(await waitForText("1. Chuẩn bị"), "Không mở được màn hình duyệt/in");
  await evaluate("document.querySelector('[data-action=\"prepare-print\"]').click()");
  const preparedPrint = await waitForText("Đã chuẩn bị bộ chứng từ; cần duyệt trước khi in", 150);
  assert(preparedPrint, "Không chuẩn bị được bộ in qua giao diện: " +
    String(await evaluate("document.querySelector('#toast')?.textContent || ''")));
  stage("print_prepare_ok");
  stage("print_approve_probe_start");
  assert(await evaluate("Boolean(document.querySelector('[data-action=\"approve-print\"]:not([disabled])'))"),
    "Nút duyệt bộ in chưa sẵn sàng sau bước chuẩn bị");
  stage("print_approve_click_start");
  await evaluate("window.confirm=()=>true;document.querySelector('[data-action=\"approve-print\"]').click()");
  stage("print_approve_click_returned");
  const approvedPrint = await waitForText("Đã duyệt bộ chứng từ in", 120);
  assert(approvedPrint, "Không duyệt được bộ in qua giao diện: " +
    String(await evaluate("document.querySelector('#toast')?.textContent || ''")));
  stage("print_approve_ok");
  assert(await evaluate("document.querySelectorAll('tbody tr').length === 2 && Array.from(document.querySelectorAll('tbody tr')).every(r=>r.innerText.includes('Đã duyệt'))"), "Hàng đợi in không có đúng 2 bộ PDF đã duyệt");
  const printDryRun = await evaluate("fetch('/api/print/run/" + activeBatchId + "',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dry_run:true})}).then(r=>r.json())");
  assert(printDryRun.ok && printDryRun.dry_run && printDryRun.jobs === 2, "Dry-run in không đạt 2 bộ PDF");
  stage("print_dry_run_ok");

  // The same disposable one-line batch drives the full outgoing-draft UI.
  const outgoingSeed = operationalSeed;
  assert(Number(await evaluate("document.querySelector('#batchSelect').value")) === outgoingSeed.batchId,
    "Phiên QC đầu ra bị đổi sau dry-run in");
  await evaluate("document.querySelector('[data-view=\"documents\"]').click()");
  assert(await waitForText("Dự thảo hóa đơn đầu ra", 120), "Thiếu khu vực trạng thái hóa đơn đầu ra");
  await evaluate("document.querySelector('[data-action=\"create-outgoing-drafts\"]').click()");
  const outgoingCreated = await waitForText("Ghi nhận hóa đơn đã phát hành", 120);
  assert(outgoingCreated, "Không tạo/hiển thị được dự thảo đầu ra qua giao diện: " +
    String(await evaluate("document.querySelector('#toast')?.textContent || ''")));
  await evaluate("window.confirm=()=>true;document.querySelector('[data-action=\"cancel-outgoing-draft\"]').click()");
  assert(await waitForText("Đã hủy dự thảo và nhả tồn khả dụng", 120), "Không hủy/nhả tồn dự thảo qua giao diện");
  assert(await waitForText("Đã hủy", 120), "Trạng thái hủy không hiển thị lại");
  await evaluate("document.querySelector('[data-action=\"create-outgoing-drafts\"]').click()");
  assert(await waitForText("Ghi nhận hóa đơn đã phát hành", 120), "Không tạo lại được dự thảo đã hủy");

  // Locking a local issued record requires a complete immutable buyer/company
  // snapshot.  Exercise the real buyer form in dry-run mode; this never writes
  // to M-Invoice and only saves the disposable QC buyer profile locally.
  const buyerDryRunStarted = await evaluate(`(()=>{
    const form=document.querySelector('.minvoiceDraftForm');
    if(!form)return false;
    form.querySelector('[name="series"]').value='1C26TDP';
    form.querySelector('[name="display_name"]').value='QC Browser';
    form.querySelector('[name="legal_name"]').value='CONG TY QC BROWSER';
    form.querySelector('[name="tax_code"]').value='0100000000';
    form.querySelector('[name="address"]').value='Dia chi QC tam';
    form.querySelector('[name="email"]').value='';
    form.requestSubmit(form.querySelector('button[value="dry"]'));
    return true;
  })()`);
  assert(buyerDryRunStarted, "Thiếu form hồ sơ người mua cho dự thảo QC");
  assert(await waitForText("Dữ liệu M-Invoice hợp lệ · tổng", 120),
    "Không lưu/kiểm tra được hồ sơ người mua QC ở chế độ không ghi M-Invoice: " +
      String(await evaluate("document.querySelector('#toast')?.textContent || ''")));

  // Capture both the canonical stock and the effective local hold immediately
  // before confirmation.  Local confirmation may lock the draft, but must not
  // post an output into the canonical invoice ledger or release this hold.
  const localConfirmBefore = await evaluate(`(async()=>{
    const [canonical,readiness,drafts]=await Promise.all([
      fetch('/api/invoice-inventory?as_of=2026-08-31').then(r=>r.json()),
      fetch('/api/outgoing-invoices/readiness/${outgoingSeed.batchId}').then(r=>r.json()),
      fetch('/api/outgoing-invoices').then(r=>r.json())
    ]);
    const draft=(drafts.items||[]).find(item=>item.batch_id===${outgoingSeed.batchId} && item.status==='draft');
    const row=(readiness.rows||[])[0];
    window.__qcCanonicalBeforeLocalConfirm=JSON.stringify((canonical.items||[])
      .map(item=>[String(item.product_code||''),Number(item.closing_qty)])
      .sort((a,b)=>a[0].localeCompare(b[0])));
    window.__qcAvailableBeforeLocalConfirm=Number(row&&row.available_before);
    return {ok:canonical.ok&&readiness.ok&&drafts.ok&&Boolean(draft)&&readiness.rows.length===1&&
      Number(row.drafted_qty)===2&&Number(row.issued_qty)===0&&
      Number.isFinite(window.__qcAvailableBeforeLocalConfirm),draftId:Number(draft&&draft.id)};
  })()`);
  assert(localConfirmBefore.ok && localConfirmBefore.draftId > 0,
    "Không xác lập được tồn canonical/hold trước khi khóa dự thảo cục bộ");
  const localConfirmClicked = await evaluate(`(()=>{
    window.prompt=(()=>{const values=['9000001','C26MYY','2026-08-31'];return ()=>values.shift()||'';})();
    const button=document.querySelector('[data-action="confirm-outgoing-issued"][data-id="${localConfirmBefore.draftId}"]');
    if(!button)return false;
    button.click();
    return true;
  })()`);
  assert(localConfirmClicked, "Không tìm thấy nút khóa dự thảo cục bộ cần kiểm tra");
  const localConfirmToast = "Đã ghi nhận hóa đơn phát hành · hàng trong kho vẫn được giữ để chờ đối soát M-Invoice";
  assert(await waitForText(localConfirmToast, 120),
    "Không khóa được dự thảo cục bộ theo contract mới: " +
      String(await evaluate("document.querySelector('#toast')?.textContent || ''")));
  assert(await waitForText("Đã phát hành", 120), "Trạng thái phát hành không hiển thị lại");
  const localConfirmAfter = await evaluate(`(async()=>{
    const [canonical,readiness,drafts]=await Promise.all([
      fetch('/api/invoice-inventory?as_of=2026-08-31').then(r=>r.json()),
      fetch('/api/outgoing-invoices/readiness/${outgoingSeed.batchId}').then(r=>r.json()),
      fetch('/api/outgoing-invoices').then(r=>r.json())
    ]);
    const draft=(drafts.items||[]).find(item=>Number(item.id)===${localConfirmBefore.draftId});
    const row=(readiness.rows||[])[0];
    const canonicalNow=JSON.stringify((canonical.items||[])
      .map(item=>[String(item.product_code||''),Number(item.closing_qty)])
      .sort((a,b)=>a[0].localeCompare(b[0])));
    return {apisOk:canonical.ok&&readiness.ok&&drafts.ok,draftLocked:draft&&draft.status==='issued',
      canonicalUnchanged:canonicalNow===window.__qcCanonicalBeforeLocalConfirm,
      holdUnchanged:Number.isFinite(Number(row&&row.available_before))&&
        Math.abs(Number(row.available_before)-window.__qcAvailableBeforeLocalConfirm)<=0.000001,
      allocationMoved:readiness.rows.length===1&&Number(row.drafted_qty)===0&&Number(row.issued_qty)===2};
  })()`);
  assert(localConfirmAfter.apisOk && localConfirmAfter.draftLocked &&
      localConfirmAfter.canonicalUnchanged && localConfirmAfter.holdUnchanged &&
      localConfirmAfter.allocationMoved,
    "Khóa cục bộ đã làm sai tồn/hold hoặc trạng thái phân bổ: " + JSON.stringify(localConfirmAfter));
  stage("outgoing_draft_ok");

  // Once the official opening workbook has supplied the catalog/stock basis,
  // the exact historical readiness route that failed closed above must recover.
  const historicalReadinessAfterOpening = await evaluate(`fetch('/api/outgoing-invoices/readiness/${imported.batch.id}')
    .then(async r=>{const payload=await r.json();return {status:r.status,ok:payload.ok,code:String(payload.code||'')}})`);
  assert(historicalReadinessAfterOpening.status === 200 && historicalReadinessAfterOpening.ok === true,
    "Phiên lịch sử không phục hồi readiness sau khi nạp tồn đầu chính thức: " +
      JSON.stringify(historicalReadinessAfterOpening));
  const allowedHistoricalReadinessError = "409 /api/outgoing-invoices/readiness/" + imported.batch.id;
  const unexpectedHttpErrors = httpErrors.filter((item) => item !== allowedHistoricalReadinessError);
  const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  writeFileSync(join(profile, "qc_browser.png"), Buffer.from(shot.data, "base64"));
  assert(errors.length === 0 && unexpectedHttpErrors.length === 0,
    "Lỗi trình duyệt: " + errors.join(" | ") + " · HTTP: " + unexpectedHttpErrors.join(" | "));
  console.log(JSON.stringify({
    ok: true,
    importedOrders: imported.orders.length,
    selectedSheetOrders: 323,
    editAndPasteFlow: "saved edit / added one row in real forms",
    datedSheetAutoSelected: "29.08",
    errorRows: imported.summary.totals.errors,
    warningRows: imported.summary.totals.warnings,
    screens: requiredViews.length,
    openingWorkbook: "395 rows / 334 codes / repeat update",
    kitchenWorkbook: "5 plans / 54 items / repeat update",
    mealAttendanceWorkbook: "205 daily kitchen/shift rows / 6,020 meals / repeat safe",
    attendanceWorkbook: "August legacy payroll / TRIEN 8,000,000 VND",
    paymentRequestSettings: "validated without printing business values",
    printApproval: "2 approved PDF bundles / dry-run",
    supplierRuleUi: "toggle and persist",
    debtPeriodUi: "range / adjustment / Excel export",
    payrollUi: "manual forms / Excel export",
    historicalReadinessGuard: historicalReadinessBeforeOpening.code,
    outgoingUi: "draft / cancel-release / recreate / local lock keeps hold and canonical stock unchanged",
    browserErrors: errors.length
  }, null, 2));
  ws.close();
} finally {
  if (browser) browser.kill();
  server.kill();
  await wait(300);
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
  for (const suffix of ["", "-wal", "-shm"]) {
    try { rmSync(qcDb + suffix, { force: true }); } catch {}
  }
}
