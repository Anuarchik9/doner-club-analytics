(() => {
  if (window.__dcPointMultiSelect) return;
  window.__dcPointMultiSelect = true;
  if (!location.pathname.endsWith('/dashboard-v2.html')) return;

  const SEP = '||';
  const select = document.getElementById('point');
  if (!select) return;

  const style = document.createElement('style');
  style.textContent = `
    .dc-point-native{position:absolute!important;width:1px!important;height:1px!important;opacity:0!important;pointer-events:none!important;clip:rect(0 0 0 0)!important}
    .dc-point-trigger{width:100%;height:52px;border:1px solid #333;border-radius:12px;background:#0b0b0b;color:#fff;padding:0 14px;display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;font:inherit;font-size:15px;font-weight:800;text-align:left;transition:border-color .15s ease,box-shadow .15s ease,background .15s ease}
    .dc-point-trigger:hover{border-color:#555;background:#0e0e0e}.dc-point-trigger[aria-expanded="true"]{border-color:var(--orange,#ff5a1f);box-shadow:0 0 0 3px rgba(255,90,31,.14)}
    .dc-point-trigger-value{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dc-point-trigger svg{width:20px;height:20px;flex:0 0 20px;color:#aaa;transition:transform .15s ease}.dc-point-trigger[aria-expanded="true"] svg{transform:rotate(180deg);color:#ff9b73}
    .dc-point-panel{position:fixed;z-index:10120;display:none;width:min(470px,calc(100vw - 24px));max-height:min(520px,calc(100vh - 28px));overflow:auto;padding:10px;border:1px solid #3b3129;border-radius:18px;background:#101010;box-shadow:0 28px 90px rgba(0,0,0,.72)}.dc-point-panel.open{display:block}
    .dc-point-panel-head{padding:7px 9px 10px;border-bottom:1px solid #252525;margin-bottom:5px}.dc-point-panel-head b{display:block;font-size:13px}.dc-point-panel-head span{display:block;color:#82827d;font-size:10px;line-height:1.4;margin-top:3px}
    .dc-point-option{width:100%;min-height:52px;padding:9px 11px;border:1px solid transparent;border-radius:12px;background:transparent;color:#efefeb;display:flex;align-items:center;gap:12px;cursor:pointer;font:inherit;font-size:14px;font-weight:760;text-align:left}.dc-point-option:hover{background:#191512;border-color:#4e382d}.dc-point-option.selected{background:rgba(255,90,31,.11);border-color:#5b3528}
    .dc-point-check{width:20px;height:20px;flex:0 0 20px;border:1.5px solid #555;border-radius:6px;background:#0a0a0a;display:grid;place-items:center;color:#fff;font-size:13px;font-weight:950}.dc-point-option.selected .dc-point-check{border-color:var(--orange,#ff5a1f);background:var(--orange,#ff5a1f)}.dc-point-option.selected .dc-point-check::after{content:'✓'}
    .dc-point-option-text{min-width:0;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dc-point-badge{font-size:9px;color:#ffad88;border:1px solid #5e382a;border-radius:999px;padding:4px 7px;white-space:nowrap}
    .dc-point-panel-foot{position:sticky;bottom:-10px;margin:7px -2px -2px;padding:10px 2px 2px;background:linear-gradient(180deg,rgba(16,16,16,0),#101010 25%)}.dc-point-done{width:100%;height:43px;border:0;border-radius:12px;background:var(--orange,#ff5a1f);color:#fff;font:inherit;font-weight:900;cursor:pointer}
    @media(max-width:600px){.dc-point-trigger{height:50px;font-size:14px}.dc-point-panel{width:calc(100vw - 16px);max-height:calc(100dvh - 30px);padding:8px;border-radius:16px}.dc-point-option{min-height:50px}}
  `;
  document.head.appendChild(style);

  let panel = null;
  let trigger = null;
  let selected = new Set();
  let syncing = false;

  const pretty = text => {
    const value = String(text || '').trim();
    const low = value.toLowerCase();
    if (low.includes('республика') || low.includes('republic')) return 'Республика';
    return value;
  };
  const technical = text => {
    const low = String(text || '').trim().toLowerCase();
    return low.includes('основное подразделение') || low === 'основное подразделение';
  };
  const realOptions = () => Array.from(select.options).filter(o => !o.dataset.dcMultiSynthetic && !technical(o.textContent));

  function cleanupNativeOptions(){
    syncing = true;
    try {
      Array.from(select.options).forEach(option => {
        if (option.dataset.dcMultiSynthetic) return;
        if (technical(option.textContent)) {
          option.remove();
          return;
        }
        const nicer = pretty(option.textContent);
        if (nicer && option.textContent !== nicer) option.textContent = nicer;
      });
    } finally { syncing = false; }
  }

  function labels(){
    const byValue = new Map(realOptions().map(o => [o.value, pretty(o.textContent)]));
    return Array.from(selected).map(v => byValue.get(v) || pretty(v));
  }

  function summaryText(){
    const list = labels();
    if (!list.length) return 'Выберите точку';
    if (list.length <= 2) return list.join(' + ');
    return `Выбрано ${list.length}: ${list.slice(0,2).join(', ')}…`;
  }

  function ensureSelection(){
    cleanupNativeOptions();
    const options = realOptions();
    const available = new Set(options.map(o => o.value));
    selected = new Set(Array.from(selected).filter(v => available.has(v)));
    if (!selected.size) {
      const nativeSelected = options.find(o => o.selected) || options.find(o => String(o.value).toLowerCase() === 'arai') || options[0];
      if (nativeSelected) selected.add(nativeSelected.value);
    }
  }

  function syncNative(dispatch = true){
    ensureSelection();
    syncing = true;
    try {
      Array.from(select.querySelectorAll('option[data-dc-multi-synthetic]')).forEach(o => o.remove());
      const values = Array.from(selected);
      Array.from(select.options).forEach(o => { o.selected = values.length === 1 && o.value === values[0]; });
      if (values.length > 1) {
        const option = document.createElement('option');
        option.dataset.dcMultiSynthetic = '1';
        option.value = values.join(SEP);
        option.textContent = summaryText();
        option.selected = true;
        select.appendChild(option);
      } else if (values.length === 1) {
        select.value = values[0];
      }
    } finally { syncing = false; }
    if (trigger) trigger.querySelector('.dc-point-trigger-value').textContent = summaryText();
    if (dispatch) {
      select.dispatchEvent(new Event('input', {bubbles:true}));
      select.dispatchEvent(new Event('change', {bubbles:true}));
    }
    window.dispatchEvent(new CustomEvent('dc:points-changed', {detail:{values:Array.from(selected), labels:labels()}}));
  }

  function renderPanel(){
    if (!panel) return;
    const current = new Set(selected);
    panel.innerHTML = `
      <div class="dc-point-panel-head"><b>Выберите точки</b><span>Можно отметить одну или несколько точек — показатели будут объединены.</span></div>
      ${realOptions().map(option => {
        const active = current.has(option.value);
        const label = pretty(option.textContent);
        const republic = label === 'Республика';
        return `<button type="button" class="dc-point-option${active?' selected':''}" data-value="${String(option.value).replace(/&/g,'&amp;').replace(/"/g,'&quot;')}" aria-pressed="${active?'true':'false'}"><span class="dc-point-check"></span><span class="dc-point-option-text">${label.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</span>${republic?'<span class="dc-point-badge">новая точка</span>':''}</button>`;
      }).join('')}
      <div class="dc-point-panel-foot"><button type="button" class="dc-point-done">Готово</button></div>`;

    panel.querySelectorAll('.dc-point-option').forEach(button => {
      button.addEventListener('click', () => {
        const value = button.dataset.value;
        if (!value) return;
        if (selected.has(value)) {
          if (selected.size === 1) return;
          selected.delete(value);
        } else {
          selected.add(value);
        }
        syncNative(true);
        renderPanel();
        positionPanel();
      });
    });
    panel.querySelector('.dc-point-done')?.addEventListener('click', closePanel);
  }

  function positionPanel(){
    if (!panel || !trigger || !panel.classList.contains('open')) return;
    const r = trigger.getBoundingClientRect();
    const width = Math.min(Math.max(r.width, 280), Math.min(470, window.innerWidth - 24));
    panel.style.width = `${width}px`;
    const h = Math.min(panel.scrollHeight || 360, window.innerHeight - 28);
    let left = Math.min(Math.max(12, r.left), window.innerWidth - width - 12);
    let top = r.bottom + 8;
    if (top + h > window.innerHeight - 12 && r.top > h + 20) top = Math.max(12, r.top - h - 8);
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function openPanel(){
    if (!panel || !trigger) return;
    ensureSelection();
    renderPanel();
    panel.classList.add('open');
    trigger.setAttribute('aria-expanded','true');
    positionPanel();
  }
  function closePanel(){
    panel?.classList.remove('open');
    trigger?.setAttribute('aria-expanded','false');
  }

  function enhance(){
    if (select.dataset.dcPointMultiEnhanced === '1') return;
    if (!realOptions().length) return;
    select.dataset.dcPointMultiEnhanced = '1';

    // If the generic custom-select already enhanced this field, retire only its
    // trigger. The native select remains the compatibility source for old code.
    if (select._dcSelectTrigger) {
      try { select._dcSelectTrigger.remove(); } catch (_) {}
      select._dcSelectTrigger = null;
    }
    const siblingGeneric = select.nextElementSibling;
    if (siblingGeneric?.classList?.contains('dc-select-trigger')) siblingGeneric.remove();

    select.classList.add('dc-point-native','dc-select-native');
    ensureSelection();

    trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'dc-point-trigger';
    trigger.setAttribute('aria-haspopup','dialog');
    trigger.setAttribute('aria-expanded','false');
    trigger.innerHTML = `<span class="dc-point-trigger-value"></span><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 9.5 12 14.5 17 9.5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    select.insertAdjacentElement('afterend', trigger);

    panel = document.createElement('div');
    panel.className = 'dc-point-panel';
    panel.setAttribute('role','dialog');
    document.body.appendChild(panel);

    trigger.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      panel.classList.contains('open') ? closePanel() : openPanel();
    });
    trigger.querySelector('.dc-point-trigger-value').textContent = summaryText();
    syncNative(false);
  }

  const optionObserver = new MutationObserver(mutations => {
    if (syncing) return;
    const meaningful = mutations.some(mutation => {
      const nodes = [...(mutation.addedNodes || []), ...(mutation.removedNodes || [])];
      if (nodes.length) {
        return nodes.some(node => !(node.nodeType === 1 && node.dataset?.dcMultiSynthetic === '1'));
      }
      return mutation.type === 'characterData';
    });
    if (!meaningful) return;
    cleanupNativeOptions();
    if (select.dataset.dcPointMultiEnhanced !== '1') enhance();
    else {
      ensureSelection();
      syncNative(false);
      if (panel?.classList.contains('open')) renderPanel();
    }
  });
  optionObserver.observe(select,{childList:true,subtree:true,characterData:true});

  window.DCPointSelection = {
    values: () => Array.from(selected),
    labels,
    includesRepublic: () => labels().some(x => String(x).toLowerCase().includes('республика')),
    spec: () => Array.from(selected).join(SEP),
  };

  document.addEventListener('click', event => {
    if (!event.target.closest('.dc-point-panel,.dc-point-trigger')) closePanel();
  }, true);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closePanel(); });
  window.addEventListener('resize',positionPanel);
  window.addEventListener('scroll',positionPanel,true);

  cleanupNativeOptions();
  enhance();
  setTimeout(enhance,150);
  setTimeout(enhance,600);
})();
