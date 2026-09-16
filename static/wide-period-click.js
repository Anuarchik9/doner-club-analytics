(() => {
  if (window.__dcWidePeriodClick) return;
  window.__dcWidePeriodClick = true;

  const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const MONTHS_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'];
  const pad = n => String(n).padStart(2,'0');

  const style = document.createElement('style');
  style.textContent = `
    .field.dc-whole-click{cursor:pointer}
    .field.dc-whole-click select,
    .field.dc-whole-click input[type="date"]{
      cursor:pointer!important;
      transition:border-color .16s ease,box-shadow .16s ease,background .16s ease;
    }
    .field.dc-whole-click:hover select,
    .field.dc-whole-click:hover input[type="date"]{
      border-color:#555!important;
      background:#0d0d0d!important;
    }
    .field.dc-whole-click:focus-within select,
    .field.dc-whole-click:focus-within input[type="date"]{
      border-color:var(--orange,#ff5a1f)!important;
      box-shadow:0 0 0 2px rgba(255,90,31,.12)!important;
      outline:none!important;
    }

    /* Native month input stays as the data source, but the user sees our larger picker. */
    input.dc-month-native{
      position:absolute!important;
      width:1px!important;
      height:1px!important;
      opacity:0!important;
      pointer-events:none!important;
      overflow:hidden!important;
      clip:rect(0 0 0 0)!important;
    }
    .dc-month-trigger{
      width:100%;height:52px;border:1px solid #333;border-radius:12px;
      background:#0b0b0b;color:#fff;padding:0 14px;display:flex;align-items:center;
      justify-content:space-between;gap:14px;cursor:pointer;font:inherit;font-size:15px;font-weight:760;
      text-align:left;transition:border-color .16s ease,box-shadow .16s ease,background .16s ease;
    }
    .dc-month-trigger:hover{border-color:#565656;background:#0d0d0d}
    .dc-month-trigger:focus-visible,.dc-month-trigger[aria-expanded="true"]{
      outline:none;border-color:var(--orange,#ff5a1f);box-shadow:0 0 0 3px rgba(255,90,31,.15)
    }
    .dc-month-trigger-main{display:flex;align-items:baseline;gap:10px;min-width:0}
    .dc-month-trigger-month{font-size:16px;font-weight:850;color:#fff}
    .dc-month-trigger-year{font-size:15px;font-weight:800;color:#d9d9d4}
    .dc-month-trigger-arrow{font-size:19px;color:#aaa;line-height:1;transform:translateY(-1px)}

    .dc-month-panel{
      position:fixed;z-index:10050;width:min(460px,calc(100vw - 24px));
      border:1px solid #3a3028;border-radius:22px;background:#101010;
      box-shadow:0 26px 80px rgba(0,0,0,.66);padding:20px;display:none;
    }
    .dc-month-panel.open{display:block}
    .dc-month-panel-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px}
    .dc-month-panel-title small{display:block;color:#8e8e88;font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px}
    .dc-month-panel-title strong{font-size:29px;line-height:1;font-weight:950;letter-spacing:-.035em}
    .dc-month-nav{display:flex;gap:8px}
    .dc-month-nav button{width:44px;height:44px;border:1px solid #333;border-radius:13px;background:#171717;color:#fff;font-size:25px;cursor:pointer}
    .dc-month-nav button:hover{border-color:var(--orange,#ff5a1f);background:#1b1512;color:#ff9e78}
    .dc-month-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
    .dc-month-btn{
      min-height:62px;border:1px solid #2f2f2f;border-radius:15px;background:#151515;color:#efefea;
      font:inherit;font-size:14px;font-weight:850;cursor:pointer;transition:.15s ease;
    }
    .dc-month-btn:hover{transform:translateY(-1px);border-color:#6a4a3a;background:#1a1512}
    .dc-month-btn.current{box-shadow:inset 0 0 0 1px #5a483b}
    .dc-month-btn.active{border-color:var(--orange,#ff5a1f);background:var(--orange,#ff5a1f);color:#fff;box-shadow:0 8px 26px rgba(255,90,31,.22)}
    .dc-month-panel-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:16px;padding-top:15px;border-top:1px solid #292929}
    .dc-month-panel-foot button{min-height:42px;padding:0 14px;border:1px solid #333;border-radius:12px;background:#171717;color:#ddd;font:inherit;font-size:12px;font-weight:800;cursor:pointer}
    .dc-month-panel-foot button:hover{border-color:#5d4639;color:#fff;background:#1b1512}
    .dc-month-helper{color:#777;font-size:10px;line-height:1.35}

    /* Sales + analytics month mode gets one clear month selector instead of two day fields. */
    .dc-sales-month-field{display:none}
    .filters.dc-month-mode .dc-sales-month-field{display:block}
    .filters.dc-month-mode .dc-date-range-field{display:none!important}

    @media(max-width:900px){
      .dc-month-panel{width:min(430px,calc(100vw - 20px));padding:17px}
      .dc-month-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
      .dc-month-btn{min-height:57px}
    }
    @media(max-width:600px){
      .dc-month-panel{width:calc(100vw - 16px);padding:14px;border-radius:18px}
      .dc-month-panel-title strong{font-size:25px}
      .dc-month-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
      .dc-month-btn{min-height:52px;font-size:13px;border-radius:12px}
      .dc-month-nav button{width:40px;height:40px}
      .dc-month-trigger{height:50px}
    }
  `;
  document.head.appendChild(style);

  function focusControl(control){
    try { control.focus({preventScroll:true}); }
    catch (_) { try { control.focus(); } catch (_) {} }
  }

  function openNative(control){
    if(!control || control.disabled || control.readOnly) return;
    focusControl(control);
    try {
      if(typeof control.showPicker === 'function'){
        control.showPicker();
        return;
      }
    } catch (_) {}
    try { control.click(); } catch (_) {}
  }

  function bindWholeField(field){
    if(!field || field.dataset.dcWholeFieldBound === '1') return;
    const control = field.querySelector('select,input[type="date"]');
    if(!control) return;
    field.dataset.dcWholeFieldBound='1';
    field.classList.add('dc-whole-click');

    field.addEventListener('click',event=>{
      if(event.target.closest('.dc-month-trigger,.dc-month-panel,button')) return;
      if(event.target === control) return; // Native click already opens the control.
      event.preventDefault();
      openNative(control);
    });

    control.addEventListener('click',()=>{
      if(control.tagName === 'INPUT' && control.type === 'date') openNative(control);
    });
  }

  // ---------- Custom month picker ----------
  let panel = null;
  let activeInput = null;
  let activeTrigger = null;
  let viewYear = new Date().getFullYear();

  function parseMonth(value){
    const m=/^(\d{4})-(\d{2})$/.exec(String(value||''));
    if(!m) return null;
    return {year:Number(m[1]),month:Number(m[2])-1};
  }

  function monthText(value){
    const p=parseMonth(value);
    return p ? {month:MONTHS[p.month],year:String(p.year)} : {month:'Выберите месяц',year:''};
  }

  function ensurePanel(){
    if(panel) return panel;
    panel=document.createElement('div');
    panel.className='dc-month-panel';
    panel.setAttribute('role','dialog');
    panel.setAttribute('aria-label','Выбор месяца');
    document.body.appendChild(panel);
    return panel;
  }

  function closeMonthPicker(){
    if(!panel) return;
    panel.classList.remove('open');
    if(activeTrigger) activeTrigger.setAttribute('aria-expanded','false');
    activeInput=null;activeTrigger=null;
  }

  function positionPanel(){
    if(!panel || !activeTrigger) return;
    const r=activeTrigger.getBoundingClientRect();
    const width=Math.min(460,window.innerWidth-24);
    let left=Math.min(Math.max(12,r.left),window.innerWidth-width-12);
    let top=r.bottom+10;
    const estimated=390;
    if(top+estimated>window.innerHeight-10 && r.top>estimated+18) top=Math.max(10,r.top-estimated-10);
    panel.style.width=`${width}px`;
    panel.style.left=`${left}px`;
    panel.style.top=`${top}px`;
  }

  function renderPanel(){
    const box=ensurePanel();
    if(!activeInput) return;
    const selected=parseMonth(activeInput.value);
    const now=new Date();
    box.innerHTML=`
      <div class="dc-month-panel-head">
        <div class="dc-month-panel-title"><small>Выбор месяца</small><strong>${viewYear}</strong></div>
        <div class="dc-month-nav">
          <button type="button" data-year="-1" aria-label="Предыдущий год">‹</button>
          <button type="button" data-year="1" aria-label="Следующий год">›</button>
        </div>
      </div>
      <div class="dc-month-grid">
        ${MONTHS_SHORT.map((name,index)=>{
          const active=selected && selected.year===viewYear && selected.month===index;
          const current=now.getFullYear()===viewYear && now.getMonth()===index;
          return `<button type="button" class="dc-month-btn${active?' active':''}${current?' current':''}" data-month="${index}">${name}</button>`;
        }).join('')}
      </div>
      <div class="dc-month-panel-foot">
        <div class="dc-month-helper">Выберите месяц — период применится к текущему фильтру.</div>
        <button type="button" data-current-month>Текущий месяц</button>
      </div>`;

    box.querySelectorAll('[data-year]').forEach(btn=>btn.addEventListener('click',()=>{
      viewYear+=Number(btn.dataset.year||0);renderPanel();positionPanel();
    }));
    box.querySelectorAll('[data-month]').forEach(btn=>btn.addEventListener('click',()=>{
      chooseMonth(viewYear,Number(btn.dataset.month));
    }));
    box.querySelector('[data-current-month]')?.addEventListener('click',()=>{
      const d=new Date();chooseMonth(d.getFullYear(),d.getMonth());
    });
  }

  function updateTrigger(input){
    const trigger=document.querySelector(`.dc-month-trigger[data-for="${CSS.escape(input.id)}"]`);
    if(!trigger) return;
    const t=monthText(input.value);
    trigger.querySelector('.dc-month-trigger-month').textContent=t.month;
    trigger.querySelector('.dc-month-trigger-year').textContent=t.year;
  }

  function chooseMonth(year,month){
    if(!activeInput) return;
    activeInput.value=`${year}-${pad(month+1)}`;
    activeInput.dispatchEvent(new Event('input',{bubbles:true}));
    activeInput.dispatchEvent(new Event('change',{bubbles:true}));
    updateTrigger(activeInput);
    closeMonthPicker();
  }

  function openMonthPicker(input,trigger){
    activeInput=input;activeTrigger=trigger;
    const p=parseMonth(input.value);viewYear=p?.year||new Date().getFullYear();
    trigger.setAttribute('aria-expanded','true');
    renderPanel();
    ensurePanel().classList.add('open');
    positionPanel();
  }

  function enhanceMonthInput(input){
    if(!input || input.dataset.dcMonthEnhanced==='1') return;
    if(!input.id) input.id=`dcMonth_${Math.random().toString(36).slice(2)}`;
    input.dataset.dcMonthEnhanced='1';
    input.classList.add('dc-month-native');

    const trigger=document.createElement('button');
    trigger.type='button';trigger.className='dc-month-trigger';trigger.dataset.for=input.id;
    trigger.setAttribute('aria-expanded','false');
    trigger.innerHTML=`<span class="dc-month-trigger-main"><span class="dc-month-trigger-month"></span><span class="dc-month-trigger-year"></span></span><span class="dc-month-trigger-arrow">⌄</span>`;
    input.insertAdjacentElement('afterend',trigger);
    updateTrigger(input);

    trigger.addEventListener('click',event=>{
      event.preventDefault();event.stopPropagation();
      if(activeInput===input && panel?.classList.contains('open')) closeMonthPicker();
      else openMonthPicker(input,trigger);
    });
    input.addEventListener('change',()=>updateTrigger(input));
  }

  // ---------- Sales/analytics month mode ----------
  function monthEndForSales(year,month){
    const now=new Date();
    const yesterday=new Date(now.getFullYear(),now.getMonth(),now.getDate()-1);
    if(year===now.getFullYear() && month===now.getMonth()){
      if(yesterday.getFullYear()===year && yesterday.getMonth()===month) return yesterday.getDate();
      return 1;
    }
    return new Date(year,month+1,0).getDate();
  }

  function installSalesMonthField(){
    const filters=document.querySelector('.filters');
    const from=document.getElementById('from');
    const to=document.getElementById('to');
    if(!filters||!from||!to||document.getElementById('dcSalesMonth')) return;

    const fromField=from.closest('.field'),toField=to.closest('.field');
    fromField?.classList.add('dc-date-range-field');toField?.classList.add('dc-date-range-field');

    const field=document.createElement('div');
    field.className='field dc-sales-month-field';
    field.innerHTML='<label>Месяц</label><input id="dcSalesMonth" type="month">';
    fromField?.insertAdjacentElement('beforebegin',field);
    const monthInput=field.querySelector('input');
    enhanceMonthInput(monthInput);

    const syncInputFromDates=()=>{
      const m=/^(\d{4})-(\d{2})/.exec(from.value||'');
      if(m){monthInput.value=`${m[1]}-${m[2]}`;updateTrigger(monthInput)}
    };
    syncInputFromDates();

    monthInput.addEventListener('change',()=>{
      const p=parseMonth(monthInput.value);if(!p)return;
      const last=monthEndForSales(p.year,p.month);
      from.value=`${p.year}-${pad(p.month+1)}-01`;
      to.value=`${p.year}-${pad(p.month+1)}-${pad(last)}`;
      from.dispatchEvent(new Event('change',{bubbles:true}));
      to.dispatchEvent(new Event('change',{bubbles:true}));
    });

    const syncMode=()=>{
      const monthBtn=document.querySelector('.report-mode-btn[data-mode="month"]');
      const isMonth=!!monthBtn?.classList.contains('active');
      filters.classList.toggle('dc-month-mode',isMonth);
      if(isMonth) syncInputFromDates();
    };

    document.querySelectorAll('.report-mode-btn').forEach(btn=>btn.addEventListener('click',()=>setTimeout(syncMode,0)));
    from.addEventListener('change',()=>setTimeout(()=>{syncInputFromDates();syncMode()},0));
    to.addEventListener('change',()=>setTimeout(syncMode,0));
    document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(syncMode,0));
    syncMode();
  }

  function bindAll(root=document){
    root.querySelectorAll?.('.field').forEach(bindWholeField);
    root.querySelectorAll?.('input[type="month"]').forEach(enhanceMonthInput);
    installSalesMonthField();
  }

  bindAll();
  const observer=new MutationObserver(()=>bindAll());
  observer.observe(document.body,{childList:true,subtree:true});

  document.addEventListener('click',event=>{
    if(!event.target.closest('.dc-month-panel,.dc-month-trigger')) closeMonthPicker();
  },true);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMonthPicker()});
  window.addEventListener('resize',positionPanel);
  window.addEventListener('scroll',positionPanel,true);
})();
