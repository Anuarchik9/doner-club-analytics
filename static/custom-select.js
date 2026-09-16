(() => {
  if (window.__dcCustomSelectV1) return;
  window.__dcCustomSelectV1 = true;

  const style = document.createElement('style');
  style.textContent = `
    .dc-select-native{
      position:absolute!important;
      width:1px!important;
      height:1px!important;
      opacity:0!important;
      pointer-events:none!important;
      overflow:hidden!important;
      clip:rect(0 0 0 0)!important;
    }
    .dc-select-trigger{
      width:100%;
      height:52px;
      border:1px solid #333;
      border-radius:12px;
      background:#0b0b0b;
      color:#fff;
      padding:0 14px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:14px;
      cursor:pointer;
      font:inherit;
      font-size:15px;
      font-weight:800;
      text-align:left;
      transition:border-color .16s ease, box-shadow .16s ease, background .16s ease;
    }
    .dc-select-trigger:hover{border-color:#565656;background:#0e0e0e}
    .dc-select-trigger:focus-visible,
    .dc-select-trigger[aria-expanded="true"]{
      outline:none;
      border-color:var(--orange,#ff5a1f);
      box-shadow:0 0 0 3px rgba(255,90,31,.15);
    }
    .dc-select-trigger:disabled{opacity:.55;cursor:not-allowed}
    .dc-select-trigger-value{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .dc-select-trigger-icon{width:20px;height:20px;flex:0 0 20px;color:#aaa;transition:transform .16s ease,color .16s ease}
    .dc-select-trigger[aria-expanded="true"] .dc-select-trigger-icon{transform:rotate(180deg);color:#ff9b73}

    .dc-select-panel{
      position:fixed;
      z-index:10070;
      display:none;
      width:min(440px,calc(100vw - 24px));
      max-height:min(430px,calc(100vh - 32px));
      overflow:auto;
      padding:8px;
      border:1px solid #3b3129;
      border-radius:18px;
      background:#101010;
      box-shadow:0 26px 80px rgba(0,0,0,.68);
      scrollbar-width:thin;
      scrollbar-color:#4b4b4b transparent;
    }
    .dc-select-panel.open{display:block}
    .dc-select-option{
      width:100%;
      min-height:50px;
      padding:10px 13px;
      border:1px solid transparent;
      border-radius:12px;
      background:transparent;
      color:#efefeb;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      cursor:pointer;
      font:inherit;
      font-size:14px;
      font-weight:760;
      text-align:left;
      transition:background .13s ease,border-color .13s ease,color .13s ease;
    }
    .dc-select-option:hover,
    .dc-select-option:focus-visible{outline:none;background:#191512;border-color:#4e382d;color:#fff}
    .dc-select-option.active{background:rgba(255,90,31,.13);border-color:#74412e;color:#fff}
    .dc-select-option.active::after{content:'✓';color:var(--orange,#ff5a1f);font-size:16px;font-weight:950}
    .dc-select-option:disabled{opacity:.42;cursor:not-allowed}
    .dc-select-empty{padding:14px;color:#888;font-size:12px}

    @media(max-width:600px){
      .dc-select-trigger{height:50px;font-size:14px}
      .dc-select-panel{width:calc(100vw - 16px);padding:7px;border-radius:16px}
      .dc-select-option{min-height:48px;font-size:14px}
    }
  `;
  document.head.appendChild(style);

  let panel = null;
  let activeSelect = null;
  let activeTrigger = null;

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));

  function ensurePanel(){
    if(panel) return panel;
    panel = document.createElement('div');
    panel.className = 'dc-select-panel';
    panel.setAttribute('role','listbox');
    document.body.appendChild(panel);
    return panel;
  }

  function closePanel(){
    if(!panel) return;
    panel.classList.remove('open');
    if(activeTrigger) activeTrigger.setAttribute('aria-expanded','false');
    activeSelect = null;
    activeTrigger = null;
  }

  function positionPanel(){
    if(!panel || !activeTrigger || !panel.classList.contains('open')) return;
    const r = activeTrigger.getBoundingClientRect();
    const width = Math.min(Math.max(r.width, 220), Math.min(440, window.innerWidth - 24));
    panel.style.width = `${width}px`;
    const measured = Math.min(panel.scrollHeight || 260, Math.min(430, window.innerHeight - 32));
    let left = Math.min(Math.max(12, r.left), window.innerWidth - width - 12);
    let top = r.bottom + 8;
    if(top + measured > window.innerHeight - 12 && r.top > measured + 20){
      top = Math.max(12, r.top - measured - 8);
    }
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function selectedText(select){
    const opt = select.options?.[select.selectedIndex];
    return opt ? opt.textContent.trim() : 'Выберите';
  }

  function syncTrigger(select){
    const trigger = select._dcSelectTrigger;
    if(!trigger) return;
    const value = trigger.querySelector('.dc-select-trigger-value');
    if(value) value.textContent = selectedText(select);
    trigger.disabled = !!select.disabled;
  }

  function renderPanel(){
    const box = ensurePanel();
    if(!activeSelect) return;
    const options = Array.from(activeSelect.options || []);
    box.innerHTML = options.length ? options.map((opt,index) => `
      <button type="button" class="dc-select-option${opt.selected?' active':''}" data-index="${index}" ${opt.disabled?'disabled':''} role="option" aria-selected="${opt.selected?'true':'false'}">${esc(opt.textContent.trim())}</button>
    `).join('') : '<div class="dc-select-empty">Нет вариантов</div>';

    box.querySelectorAll('.dc-select-option').forEach(btn => {
      btn.addEventListener('click', () => {
        if(!activeSelect || btn.disabled) return;
        const index = Number(btn.dataset.index);
        if(!Number.isInteger(index) || !activeSelect.options[index]) return;
        activeSelect.selectedIndex = index;
        activeSelect.dispatchEvent(new Event('input',{bubbles:true}));
        activeSelect.dispatchEvent(new Event('change',{bubbles:true}));
        syncTrigger(activeSelect);
        closePanel();
      });
    });
  }

  function openPanel(select,trigger){
    if(select.disabled) return;
    if(activeSelect === select && panel?.classList.contains('open')){
      closePanel();
      return;
    }
    closePanel();
    activeSelect = select;
    activeTrigger = trigger;
    trigger.setAttribute('aria-expanded','true');
    renderPanel();
    ensurePanel().classList.add('open');
    positionPanel();
    requestAnimationFrame(() => {
      panel?.querySelector('.dc-select-option.active')?.scrollIntoView({block:'nearest'});
    });
  }

  function enhance(select){
    if(!select || select.dataset.dcSelectEnhanced === '1') return;
    select.dataset.dcSelectEnhanced = '1';
    select.classList.add('dc-select-native');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'dc-select-trigger';
    trigger.setAttribute('aria-haspopup','listbox');
    trigger.setAttribute('aria-expanded','false');
    trigger.innerHTML = `
      <span class="dc-select-trigger-value"></span>
      <svg class="dc-select-trigger-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 9.5 12 14.5 17 9.5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
    `;
    select.insertAdjacentElement('afterend',trigger);
    select._dcSelectTrigger = trigger;
    syncTrigger(select);

    trigger.addEventListener('click',event => {
      event.preventDefault();
      event.stopPropagation();
      openPanel(select,trigger);
    });

    trigger.addEventListener('keydown',event => {
      if(event.key === 'Escape') closePanel();
      if(event.key === 'ArrowDown' || event.key === 'ArrowUp'){
        event.preventDefault();
        if(!panel?.classList.contains('open')) openPanel(select,trigger);
        const opts = Array.from(panel?.querySelectorAll('.dc-select-option:not(:disabled)') || []);
        if(!opts.length) return;
        const current = document.activeElement;
        let idx = opts.indexOf(current);
        idx = event.key === 'ArrowDown' ? Math.min(opts.length-1, idx+1) : Math.max(0, idx<0?opts.length-1:idx-1);
        opts[idx]?.focus();
      }
    });

    select.addEventListener('change',() => syncTrigger(select));
    select.addEventListener('input',() => syncTrigger(select));

    const obs = new MutationObserver(() => {
      syncTrigger(select);
      if(activeSelect === select && panel?.classList.contains('open')){
        renderPanel();
        positionPanel();
      }
    });
    obs.observe(select,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','selected','label']});
  }

  function bindAll(root=document){
    root.querySelectorAll?.('.field select').forEach(enhance);
  }

  bindAll();
  new MutationObserver(mutations => {
    for(const mutation of mutations){
      for(const node of mutation.addedNodes){
        if(node.nodeType === 1) bindAll(node);
      }
    }
  }).observe(document.body,{childList:true,subtree:true});

  document.addEventListener('click',event => {
    if(!event.target.closest('.dc-select-panel,.dc-select-trigger')) closePanel();
  },true);
  document.addEventListener('keydown',event => { if(event.key === 'Escape') closePanel(); });
  window.addEventListener('resize',positionPanel);
  window.addEventListener('scroll',positionPanel,true);
})();
