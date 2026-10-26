(() => {
  const form = document.querySelector('#login-form');
  const password = document.querySelector('#password');
  const reveal = document.querySelector('.reveal');
  const submit = document.querySelector('.submit');
  const status = document.querySelector('.login-status');
  reveal.hidden = false;
  reveal.addEventListener('click', () => {
    const visible = password.type === 'password';
    password.type = visible ? 'text' : 'password';
    reveal.textContent = visible ? 'Ẩn' : 'Hiện';
    reveal.setAttribute('aria-pressed', String(visible));
    password.focus();
  });
  const caps = document.querySelector('#caps-warning');
  password.addEventListener('keyup', event => { caps.hidden = !event.getModifierState('CapsLock'); });
  password.addEventListener('blur', () => { caps.hidden = true; });
  const reset = () => {
    submit.disabled = false;
    submit.classList.remove('is-loading');
    submit.querySelector('.submit-label').textContent = new URLSearchParams(location.search).get('resume') === '1' ? 'Mở khóa' : 'Đăng nhập';
    form.removeAttribute('aria-busy');
    status.textContent = '';
  };
  let timer;
  form.addEventListener('submit', () => {
    submit.disabled = true;
    submit.classList.add('is-loading');
    submit.querySelector('.submit-label').textContent = 'Đang đăng nhập';
    form.setAttribute('aria-busy', 'true');
    timer = setTimeout(() => { reset(); status.textContent = 'Kết nối hơi chậm. Bạn có thể bấm Đăng nhập để thử lại.'; }, 15000);
  });
  window.addEventListener('pageshow', () => { clearTimeout(timer); reset(); });
  document.querySelector('.error a')?.addEventListener('click', () => { (document.querySelector('#username') || password).focus(); });
})();

(() => {
  if (new URLSearchParams(location.search).get('resume') === '1') {
    document.querySelector('#welcome').textContent = 'Tiếp tục công việc.';
    document.querySelector('.intro').textContent = 'Nhập mật khẩu để mở khóa và tiếp tục công việc.';
    document.querySelector('.submit-label').textContent = 'Mở khóa';
    document.querySelector('.form-note p').textContent = 'Màn hình đang làm vẫn được giữ trong tab này. Đừng đóng hoặc tải lại tab nếu chưa lưu.';
  }
  const panel = document.querySelector('.brand-panel');
  const preferenceKey = 'tdp.login.motion';
  const toggle = document.createElement('button');
  toggle.type = 'button'; toggle.className = 'motion-toggle';
  let enabled = true;
  try { enabled = localStorage.getItem(preferenceKey) !== 'off'; } catch (_) {}
  const applyMotion = () => {
    document.documentElement.dataset.motion = enabled ? 'on' : 'off';
    toggle.textContent = enabled ? 'Tắt hiệu ứng' : 'Bật hiệu ứng';
    toggle.setAttribute('aria-pressed', String(enabled));
    panel.style.setProperty('--photo-x', '0px'); panel.style.setProperty('--photo-y', '0px');
  };
  applyMotion();
  toggle.addEventListener('click', () => {
    enabled = !enabled; applyMotion();
    try { localStorage.setItem(preferenceKey, enabled ? 'on' : 'off'); } catch (_) {}
  });
  document.querySelector('.form-panel').append(toggle);
  let raf;
  panel.addEventListener('pointermove', event => {
    if (!enabled || event.pointerType !== 'mouse') return;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const rect = panel.getBoundingClientRect();
      panel.style.setProperty('--photo-x', `${(event.clientX - rect.left - rect.width / 2) / rect.width * 14}px`);
      panel.style.setProperty('--photo-y', `${(event.clientY - rect.top - rect.height / 2) / rect.height * 10}px`);
    });
  });
  panel.addEventListener('pointerleave', () => {
    cancelAnimationFrame(raf);
    panel.style.setProperty('--photo-x', '0px');panel.style.setProperty('--photo-y', '0px');
  });
})();
