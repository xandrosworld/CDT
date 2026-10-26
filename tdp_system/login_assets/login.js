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
    submit.querySelector('.submit-label').textContent = 'Đăng nhập';
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
  document.querySelector('.error a')?.addEventListener('click', () => { document.querySelector('#username').focus(); });
})();
