(function () {
  'use strict';
  function normalize(value) {
    return String(value == null ? '' : value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/\s+/g, ' ').trim();
  }
  window.TDPTableSearch = function (options) {
    var bar = document.createElement('div'); bar.className = 'tdp-table-search';
    var input = document.createElement('input'); input.type = 'search';
    input.placeholder = 'Tìm mã / tên · Ctrl+F'; input.setAttribute('aria-label', 'Tìm trong bảng');
    var result = document.createElement('span'); result.className = 'tdp-search-result';
    result.setAttribute('role', 'status'); result.setAttribute('aria-live', 'polite');
    var position = -1, signature = '', busy = false, disposed = false;
    function button(label, title, action) {
      var el = document.createElement('button'); el.type = 'button'; el.textContent = label;
      el.title = title; el.setAttribute('aria-label', title); el.onclick = action; return el;
    }
    var previous = button('↑', 'Kết quả trước (Shift+Enter)', function () { run(-1); });
    var next = button('↓', 'Kết quả tiếp (Enter)', function () { run(1); });
    var clear = button('×', 'Xóa tìm kiếm (Escape)', reset);
    var scope = document.createElement('small'); scope.textContent = options.scope;
    bar.append(input, previous, next, result, clear, scope);
    function say(text) { if (result.textContent !== text) result.textContent = text; }
    function reset() {
      input.value = ''; signature = ''; position = -1; options.clear?.();
      say('Nhập từ khóa rồi Enter'); input.focus();
    }
    async function focus() {
      if (busy || disposed) return;
      busy = true;
      try { await options.prepare?.(); if (!disposed) { input.focus(); input.select(); } }
      catch (error) { console.error('Table search not ready', error); say('Bảng chưa sẵn sàng, thử lại'); }
      finally { busy = false; }
    }
    async function run(direction) {
      if (busy || disposed) return;
      var needle = normalize(input.value);
      if (!needle) { reset(); return; }
      busy = true;
      try {
        await options.prepare?.();
        if (disposed) return;
        var matches = options.cells().filter(function (cell) { return cell.values.some(function (value) { return normalize(value).includes(needle); }); });
        var currentSignature = needle + JSON.stringify(matches.map(function (cell) { return cell.key; }));
        if (signature !== currentSignature) position = direction < 0 ? 0 : -1;
        signature = currentSignature;
        options.clear?.();
        if (!matches.length) { position = -1; say('Không tìm thấy'); return; }
        position = (position + direction + matches.length) % matches.length;
        await options.select(matches[position]);
        say((position + 1) + ' / ' + matches.length + ' ô khớp');
        input.focus();
      } catch (error) { console.error('Table search failed', error); say('Chưa tìm được, thử lại'); }
      finally { busy = false; }
    }
    input.oninput = function () { signature = ''; position = -1; options.clear?.(); say('Enter để tìm'); };
    bar.addEventListener('keydown', function (event) {
      if (event.isComposing) return;
      if (event.key === 'Enter' && event.target === input) { event.preventDefault(); event.stopPropagation(); run(event.shiftKey ? -1 : 1); }
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); reset(); }
    });
    function shortcut(event) {
      if (disposed || !bar.isConnected || !options.active() || event.isComposing) return;
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'f') {
        event.preventDefault(); event.stopImmediatePropagation(); focus();
      } else if (event.key === 'F3') {
        event.preventDefault(); event.stopImmediatePropagation(); run(event.shiftKey ? -1 : 1);
      }
    }
    document.addEventListener('keydown', shortcut, true);
    say('Nhập từ khóa rồi Enter');
    return { element: bar, input: input, dispose: function () { disposed = true; document.removeEventListener('keydown', shortcut, true); options.clear?.(); } };
  };
})();
