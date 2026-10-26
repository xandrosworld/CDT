(() => {
  const nativeFetch = window.fetch.bind(window);
  let dialog, frame, resume, unlocked, checking = false;
  let lastInput = 0, lastSent = 0, expiresAt = Date.now() + 18000000;
  let previousFocus;
  const waitingReads = new Map();
  const locked = () => Boolean(dialog?.open);
  function lock() {
    if (locked()) return;
    if (!document.body) { document.addEventListener('DOMContentLoaded', lock, {once:true}); return; }
    previousFocus = document.activeElement;
    dialog = document.createElement('dialog');
    dialog.setAttribute('aria-label', 'Đăng nhập lại để tiếp tục công việc');
    dialog.style.cssText = 'position:fixed;inset:0;width:100vw;height:100dvh;max-width:none;max-height:none;margin:0;padding:0;border:0;background:#fbfcf8;';
    frame = document.createElement('iframe');
    frame.title = 'Đăng nhập lại. Màn hình làm việc vẫn được giữ trong tab này.';
    frame.style.cssText = 'display:block;width:100%;height:100%;border:0;';
    frame.src = '/login?resume=1';
    dialog.append(frame);
    dialog.addEventListener('cancel', event => event.preventDefault());
    document.body.append(dialog);
    unlocked = new Promise(resolve => { resume = resolve; });
    dialog.showModal();
    frame.focus();
  }
  async function check(activity = false) {
    if (checking) return;
    checking = true;
    try {
      const response = await nativeFetch('/api/session/activity', {method:activity ? 'POST' : 'GET', cache:'no-store'});
      if (response.status === 401) { lock(); return; }
      if (!response.ok) return;
      const data = await response.json();
      expiresAt = Date.now() + data.remaining_seconds * 1000;
      if (activity) lastSent = Date.now();
    } catch (_) { /* Network loss must not discard the working page. */ }
    finally { checking = false; }
  }
  const input = event => {
    if (!event.isTrusted || locked()) return;
    // Check expiry before an input can revive an already expired session.
    if (Date.now() >= expiresAt) { check(); return; }
    lastInput = Date.now();
    if (lastInput - lastSent >= 30000) check(true);
  };
  ['pointerdown','keydown','wheel','touchstart'].forEach(name => document.addEventListener(name, input, {capture:true,passive:true}));
  setInterval(() => {
    if (locked()) return;
    if (Date.now() >= expiresAt) check();
    else if (lastInput > lastSent && document.visibilityState === 'visible') check(true);
    else check();
  }, 30000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && !locked()) check(); });
  window.addEventListener('message', async event => {
    if (event.origin !== location.origin || event.source !== frame?.contentWindow || event.data?.type !== 'tdp-session-restored') return;
    const response = await nativeFetch('/api/session/activity', {cache:'no-store'});
    if (!response.ok) return;
    const data = await response.json();
    expiresAt = Date.now() + data.remaining_seconds * 1000;
    lastInput = lastSent = Date.now();
    dialog.close(); dialog.remove(); dialog = null; frame = null;
    resume?.(); previousFocus?.focus();
  });
  window.fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : input, location.href);
    const api = url.origin === location.origin && url.pathname.startsWith('/api/');
    const method = (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (api && locked()) {
      // Reads can wait, but never replay a stock/invoice write automatically.
      if (method !== 'GET' && method !== 'HEAD') throw new Error('Vui lòng đăng nhập lại rồi bấm thực hiện thao tác một lần nữa.');
      // Coalesce background polls while away, so returning does not burst hours of requests.
      const key = method + ' ' + url.href;
      if (!waitingReads.has(key)) {
        waitingReads.set(key, unlocked.then(() => nativeFetch(input, init)).finally(() => waitingReads.delete(key)));
      }
      return (await waitingReads.get(key)).clone();
    }
    const response = await nativeFetch(input, init);
    if (api && response.status === 401) lock();
    return response;
  };
  check();
})();
