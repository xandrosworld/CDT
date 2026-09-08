/* Keep the same working layout for tables rendered by every module. */
(function () {
  'use strict';
  const content = document.getElementById('content');
  const nav = document.getElementById('nav');
  const arrows = [...document.querySelectorAll('.workspace-nav-scroll')];
  function navigationState() {
    if (arrows.length !== 2) return;
    arrows[0].disabled = nav.scrollLeft < 2;
    arrows[1].disabled = nav.scrollLeft + nav.clientWidth >= nav.scrollWidth - 2;
  }
  arrows.forEach((button, i) => button.addEventListener('click', () => {
    nav.scrollBy({left:(i ? 1 : -1) * nav.clientWidth * .7, behavior:'instant'});
    navigationState();
  }));
  nav.addEventListener('scroll', navigationState, {passive:true});
  new MutationObserver(() => {
    const active = nav.querySelector('.active');
    if (active && nav.scrollWidth > nav.clientWidth) {
      const left = active.offsetLeft - nav.offsetLeft;
      if (left < nav.scrollLeft) nav.scrollLeft = left;
      else if (left + active.offsetWidth > nav.scrollLeft + nav.clientWidth) nav.scrollLeft = left + active.offsetWidth - nav.clientWidth;
    }
    navigationState();
  }).observe(nav,{attributes:true,subtree:true,attributeFilter:['class']});
  let pending;
  function schedule() {
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => {
      navigationState();
      const header = document.querySelector('.topbar');
      const headerBottom = header.getBoundingClientRect().bottom;
      content.querySelectorAll('.table-wrap').forEach(wrap => {
        if (!wrap.getClientRects().length || wrap.closest('.invoice-mapping-fullscreen')) return;
        const top = Math.max(headerBottom, wrap.getBoundingClientRect().top);
        // A table below the fold still gets a useful scrolling area.
        const available = Math.max(220, innerHeight - top - 48);
        wrap.style.setProperty('--table-available-height', Math.round(available) + 'px');
        wrap.querySelectorAll('thead').forEach(head => {
          let offset = 0;
          [...head.rows].forEach(row => {
            [...row.cells].forEach(cell => cell.style.setProperty('--table-heading-top', offset + 'px'));
            offset += row.getBoundingClientRect().height;
          });
        });
      });
    });
  }
  new MutationObserver(records => { if(records.some(r => !r.target.closest?.('.invoice-mapping-cell, #msmiProductOptions, .invoice-lines-card tbody'))) schedule(); }).observe(content,{childList:true,subtree:true});
  window.addEventListener('resize',schedule);
  content.addEventListener('toggle',schedule,true);
  schedule();
}());
