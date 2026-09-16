(() => {
  if (window.__dcWidePeriodClick) return;
  window.__dcWidePeriodClick = true;

  const style = document.createElement('style');
  style.textContent = `
    input[type="date"], input[type="month"]{
      cursor:pointer!important;
    }
    input[type="date"]::-webkit-calendar-picker-indicator,
    input[type="month"]::-webkit-calendar-picker-indicator{
      cursor:pointer!important;
    }
    .field.dc-period-clickable input[type="date"],
    .field.dc-period-clickable input[type="month"]{
      transition:border-color .16s ease, box-shadow .16s ease, background .16s ease;
    }
    .field.dc-period-clickable input[type="date"]:hover,
    .field.dc-period-clickable input[type="month"]:hover{
      border-color:#555!important;
      background:#0d0d0d!important;
    }
    .field.dc-period-clickable input[type="date"]:focus,
    .field.dc-period-clickable input[type="month"]:focus{
      border-color:var(--orange,#ff5a1f)!important;
      box-shadow:0 0 0 2px rgba(255,90,31,.12)!important;
      outline:none!important;
    }
  `;
  document.head.appendChild(style);

  function openPicker(input){
    if (!input || input.disabled || input.readOnly) return;
    try { input.focus({preventScroll:true}); } catch (_) { try { input.focus(); } catch (_) {} }
    try {
      if (typeof input.showPicker === 'function') {
        input.showPicker();
        return;
      }
    } catch (_) {}
  }

  function bind(input){
    if (!input || input.dataset.dcWidePeriodBound === '1') return;
    input.dataset.dcWidePeriodBound = '1';
    input.closest('.field')?.classList.add('dc-period-clickable');
    input.setAttribute('title', input.type === 'month' ? 'Нажмите в любом месте поля, чтобы выбрать месяц' : 'Нажмите в любом месте поля, чтобы выбрать дату');

    // Native Chrome/Edge inputs normally open only from the tiny calendar icon.
    // Calling showPicker from the click handler makes the whole visible rectangle active.
    input.addEventListener('click', () => openPicker(input));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openPicker(input);
      }
    });
  }

  function bindAll(root=document){
    root.querySelectorAll?.('input[type="date"], input[type="month"]').forEach(bind);
  }

  bindAll();
  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === 1) bindAll(node);
      }
    }
  });
  observer.observe(document.body,{childList:true,subtree:true});
})();
