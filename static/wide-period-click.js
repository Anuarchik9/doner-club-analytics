(() => {
  if (window.__dcWidePeriodClickV3) return;
  window.__dcWidePeriodClickV3 = true;

  const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const MONTHS_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'];
  const WEEK = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
  const pad = n => String(n).padStart(2,'0');
  const isoDate = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;

  const style = document.createElement('style');
  style.textContent = `
    .field{position:relative}
    .field.dc-whole-click{cursor:pointer}
    .field.dc-whole-click select{cursor:pointer!important;transition:border-color .16s ease,box-shadow .16s ease,background .16s ease}
    .field.dc-whole-click:hover select{border-color:#555!important;background:#0d0d0d!important}
    .field.dc-whole-click:focus-within select{border-color:var(--orange,#ff5a1f)!important;box-shadow:0 0 0 2px rgba(255,90,31,.12)!important;outline:none!important}

    input.dc-native-picker{
      position:absolute!important;width:1px!important;height:1px!important;opacity:0!important;
      pointer-events:none!important;overflow:hidden!important;clip:rect(0 0 0 0)!important;
    }
    .dc-picker-trigger{
      width:100%;height:52px;border:1px solid #333;border-radius:12px;background:#0b0b0b;color:#fff;
      padding:0 14px;display:flex;align-items:center;justify-content:space-between;gap:14px;cursor:pointer;
      font:inherit;font-size:15px;font-weight:760;text-align:left;
      transition:border-color .16s ease,box-shadow .16s ease,background .16s ease;
    }
    .dc-picker-trigger:hover{border-color:#565656;background:#0e0e0e}
    .dc-picker-trigger:focus-visible,.dc-picker-trigger[aria-expanded="true"]{outline:none;border-color:var(--orange,#ff5a1f);box-shadow:0 0 0 3px rgba(255,90,31,.15)}
    .dc-picker-trigger-main{display:flex;align-items:center;gap:9px;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .dc-picker-trigger-value{font-size:15px;font-weight:850;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .dc-picker-trigger-icon{width:20px;height:20px;flex:0 0 20px;color:#aaa}

    .dc-picker-panel{
      position:fixed;z-index:10060;width:min(470px,calc(100vw - 24px));border:1px solid #3b3129;border-radius:22px;
      background:#101010;box-shadow:0 28px 90px rgba(0,0,0,.7);padding:20px;display:none;
    }
    .dc-picker-panel.open{display:block}
    .dc-picker-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px}
    .dc-picker-title small{display:block;color:#8e8e88;font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
    .dc-picker-title strong{font-size:29px;line-height:1;font-weight:950;letter-spacing:-.035em;color:#fff}
    .dc-picker-nav{display:flex;gap:8px}
    .dc-picker-nav button{width:44px;height:44px;border:1px solid #333;border-radius:13px;background:#171717;color:#fff;font-size:25px;cursor:pointer}
    .dc-picker-nav button:hover{border-color:var(--orange,#ff5a1f);background:#1b1512;color:#ff9e78}

    .dc-month-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
    .dc-month-btn{
      min-height:62px;border:1px solid #2f2f2f;border-radius:15px;background:#151515;color:#efefea;
      font:inherit;font-size:14px;font-weight:850;cursor:pointer;transition:.15s ease;
    }
    .dc-month-btn:hover{transform:translateY(-1px);border-color:#6a4a3a;background:#1a1512}
    .dc-month-btn.current{box-shadow:inset 0 0 0 1px #5a483b}
    .dc-month-btn.active{border-color:var(--orange,#ff5a1f);background:var(--orange,#ff5a1f);color:#fff;box-shadow:0 8px 26px rgba(255,90,31,.22)}

    .dc-date-week{display:grid;grid-template-columns:repeat(7,1fr);gap:7px;margin-bottom:7px}
    .dc-date-week span{text-align:center;color:#777;font-size:10px;font-weight:850;text-transform:uppercase;padding:4px 0}
    .dc-date-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:7px}
    .dc-date-btn{
      aspect-ratio:1/1;min-height:46px;border:1px solid #2b2b2b;border-radius:12px;background:#151515;color:#ecece7;
      font:inherit;font-size:13px;font-weight:850;cursor:pointer;transition:.14s ease;position:relative;
    }
    .dc-date-btn:hover{border-color:#6a4a3a;background:#1a1512;transform:translateY(-1px)}
    .dc-date-btn.outside{color:#555;background:#111;border-color:#222}
    .dc-date-btn.today:after{content:"";position:absolute;width:5px;height:5px;border-radius:50%;background:var(--orange,#ff5a1f);left:50%;bottom:5px;transform:translateX(-50%)}
    .dc-date-btn.active{border-color:var(--orange,#ff5a1f);background:var(--orange,#ff5a1f);color:#fff;box-shadow:0 7px 20px rgba(255,90,31,.22)}
    .dc-date-btn.active:after{background:#fff}
    .dc-date-btn:disabled{opacity:.3;cursor:not-allowed;transform:none}

    .dc-picker-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:16px;padding-top:15px;border-top:1px solid #292929}
    .dc-picker-helper{color:#777;font-size:10px;line-height:1.4;max-width:250px}
    .dc-picker-foot-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
    .dc-picker-foot button{min-height:42px;padding:0 14px;border:1px solid #333;border-radius:12px;background:#171717;color:#ddd;font:inherit;font-size:12px;font-weight:800;cursor:pointer}
    .dc-picker-foot button:hover{border-color:#5d4639;color:#fff;background:#1b1512}

    .dc-sales-month-field{display:none}
    .filters.dc-month-mode .dc-sales-month-field{display:block}
    .filters.dc-month-mode .dc-date-range-field{display:none!important}

    @media(max-width:900px){
      .dc-picker-panel{width:min(440px,calc(100vw - 20px));padding:17px}
      .dc-month-btn{min-height:57px}
      .dc-date-btn{min-height:43px}
    }
    @media(max-width:600px){
      .dc-picker-panel{width:calc(100vw - 16px);padding:14px;border-radius:18px}
      .dc-picker-title strong{font-size:25px}
      .dc-month-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
      .dc-month-btn{min-height:52px;font-size:13px;border-radius:12px}
      .dc-date-grid,.dc-date-week{gap:5px}
      .dc-date-btn{min-height:39px;border-radius:10px;font-size:12px}
      .dc-picker-nav button{width:40px;height:40px}
      .dc-picker-trigger{height:50px}
      .dc-picker-foot{align-items:flex-start;flex-direction:column}
      .dc-picker-foot-actions{width:100%;justify-content:flex-start}
    }
  `;
  document.head.appendChild(style);

  function focusControl(control){
    try{control.focus({preventScroll:true})}catch(_){try{control.focus()}catch(__){}}
  }

  function openSelect(control){
    if(!control || control.disabled) return;
    focusControl(control);
    try{
      if(typeof control.showPicker === 'function'){
        control.showPicker();
        return;
      }
    }catch(_){}
    try{control.click()}catch(_){}
  }

  function bindWholeSelect(field){
    if(!field || field.dataset.dcWholeSelectBound==='1') return;
    const select=field.querySelector('select');
    if(!select) return;
    field.dataset.dcWholeSelectBound='1';
    field.classList.add('dc-whole-click');
    field.addEventListener('click',event=>{
      if(event.target===select || event.target.closest('.dc-picker-trigger,.dc-picker-panel,button')) return;
      event.preventDefault();
      openSelect(select);
    });
  }

  let panel=null;
  let activeInput=null;
  let activeTrigger=null;
  let activeKind=null;
  let monthViewYear=new Date().getFullYear();
  let dateView=new Date(new Date().getFullYear(),new Date().getMonth(),1);

  function ensurePanel(){
    if(panel) return panel;
    panel=document.createElement('div');
    panel.className='dc-picker-panel';
    panel.setAttribute('role','dialog');
    document.body.appendChild(panel);
    return panel;
  }

  function closePicker(){
    if(panel) panel.classList.remove('open');
    if(activeTrigger) activeTrigger.setAttribute('aria-expanded','false');
    activeInput=null;activeTrigger=null;activeKind=null;
  }

  function positionPanel(){
    if(!panel || !activeTrigger || !panel.classList.contains('open')) return;
    const r=activeTrigger.getBoundingClientRect();
    const width=Math.min(470,window.innerWidth-24);
    const estimated=activeKind==='date'?500:400;
    let left=Math.min(Math.max(12,r.left),window.innerWidth-width-12);
    let top=r.bottom+10;
    if(top+estimated>window.innerHeight-10 && r.top>estimated+18) top=Math.max(10,r.top-estimated-10);
    panel.style.width=`${width}px`;
    panel.style.left=`${left}px`;
    panel.style.top=`${top}px`;
  }

  function parseMonth(value){
    const m=/^(\d{4})-(\d{2})$/.exec(String(value||''));
    return m?{year:Number(m[1]),month:Number(m[2])-1}:null;
  }
  function parseDate(value){
    const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value||''));
    return m?new Date(Number(m[1]),Number(m[2])-1,Number(m[3])):null;
  }
  function prettyDate(value){
    const d=parseDate(value);
    return d?`${pad(d.getDate())}.${pad(d.getMonth()+1)}.${d.getFullYear()}`:'Выберите дату';
  }
  function prettyMonth(value){
    const p=parseMonth(value);
    return p?`${MONTHS[p.month]} ${p.year}`:'Выберите месяц';
  }

  function triggerFor(input){
    if(!input?.id) return null;
    return document.querySelector(`.dc-picker-trigger[data-for="${CSS.escape(input.id)}"]`);
  }
  function refreshTrigger(input){
    const trigger=triggerFor(input);
    if(!trigger) return;
    trigger.querySelector('.dc-picker-trigger-value').textContent=input.type==='month'?prettyMonth(input.value):prettyDate(input.value);
  }
  function refreshAllTriggers(){
    document.querySelectorAll('input.dc-native-picker').forEach(refreshTrigger);
  }

  function setInputValue(input,value){
    input.value=value;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    refreshTrigger(input);
  }

  function renderMonthPanel(){
    const box=ensurePanel();
    const selected=parseMonth(activeInput?.value);
    const now=new Date();
    box.setAttribute('aria-label','Выбор месяца');
    box.innerHTML=`
      <div class="dc-picker-head">
        <div class="dc-picker-title"><small>Выбор месяца</small><strong>${monthViewYear}</strong></div>
        <div class="dc-picker-nav"><button type="button" data-year="-1" aria-label="Предыдущий год">‹</button><button type="button" data-year="1" aria-label="Следующий год">›</button></div>
      </div>
      <div class="dc-month-grid">
        ${MONTHS_SHORT.map((name,index)=>{
          const isActive=selected&&selected.year===monthViewYear&&selected.month===index;
          const current=now.getFullYear()===monthViewYear&&now.getMonth()===index;
          return `<button type="button" class="dc-month-btn${isActive?' active':''}${current?' current':''}" data-month="${index}">${name}</button>`;
        }).join('')}
      </div>
      <div class="dc-picker-foot"><div class="dc-picker-helper">Выберите месяц — период обновится автоматически.</div><div class="dc-picker-foot-actions"><button type="button" data-current-month>Текущий месяц</button></div></div>`;

    box.querySelectorAll('[data-year]').forEach(btn=>btn.addEventListener('click',()=>{monthViewYear+=Number(btn.dataset.year||0);renderMonthPanel();positionPanel()}));
    box.querySelectorAll('[data-month]').forEach(btn=>btn.addEventListener('click',()=>{
      setInputValue(activeInput,`${monthViewYear}-${pad(Number(btn.dataset.month)+1)}`);
      closePicker();
    }));
    box.querySelector('[data-current-month]')?.addEventListener('click',()=>{
      const d=new Date();setInputValue(activeInput,`${d.getFullYear()}-${pad(d.getMonth()+1)}`);closePicker();
    });
  }

  function dateAllowed(input,value){
    if(input.min && value<input.min) return false;
    if(input.max && value>input.max) return false;
    return true;
  }

  function renderDatePanel(){
    const box=ensurePanel();
    const selected=parseDate(activeInput?.value);
    const now=new Date();
    const y=dateView.getFullYear(),m=dateView.getMonth();
    const first=new Date(y,m,1);
    const startOffset=(first.getDay()+6)%7;
    const gridStart=new Date(y,m,1-startOffset);

    box.setAttribute('aria-label','Выбор даты');
    box.innerHTML=`
      <div class="dc-picker-head">
        <div class="dc-picker-title"><small>Выбор даты</small><strong>${MONTHS[m]} ${y}</strong></div>
        <div class="dc-picker-nav"><button type="button" data-month-nav="-1" aria-label="Предыдущий месяц">‹</button><button type="button" data-month-nav="1" aria-label="Следующий месяц">›</button></div>
      </div>
      <div class="dc-date-week">${WEEK.map(x=>`<span>${x}</span>`).join('')}</div>
      <div class="dc-date-grid">
        ${Array.from({length:42},(_,i)=>{
          const d=new Date(gridStart);d.setDate(gridStart.getDate()+i);
          const value=isoDate(d);
          const outside=d.getMonth()!==m;
          const isToday=value===isoDate(now);
          const isActive=selected&&value===isoDate(selected);
          const allowed=dateAllowed(activeInput,value);
          return `<button type="button" class="dc-date-btn${outside?' outside':''}${isToday?' today':''}${isActive?' active':''}" data-date="${value}" ${allowed?'':'disabled'}>${d.getDate()}</button>`;
        }).join('')}
      </div>
      <div class="dc-picker-foot"><div class="dc-picker-helper">Нажмите на нужный день. Можно выбирать и дни соседнего месяца.</div><div class="dc-picker-foot-actions"><button type="button" data-today>Сегодня</button></div></div>`;

    box.querySelectorAll('[data-month-nav]').forEach(btn=>btn.addEventListener('click',()=>{
      dateView=new Date(y,m+Number(btn.dataset.monthNav||0),1);renderDatePanel();positionPanel();
    }));
    box.querySelectorAll('[data-date]').forEach(btn=>btn.addEventListener('click',()=>{
      if(btn.disabled) return;
      setInputValue(activeInput,btn.dataset.date);
      closePicker();
    }));
    box.querySelector('[data-today]')?.addEventListener('click',()=>{
      const value=isoDate(new Date());
      if(dateAllowed(activeInput,value)){setInputValue(activeInput,value);closePicker();}
    });
  }

  function openPicker(input,trigger){
    activeInput=input;activeTrigger=trigger;activeKind=input.type;
    trigger.setAttribute('aria-expanded','true');
    if(input.type==='month'){
      const p=parseMonth(input.value);monthViewYear=p?.year||new Date().getFullYear();renderMonthPanel();
    }else{
      const d=parseDate(input.value)||new Date();dateView=new Date(d.getFullYear(),d.getMonth(),1);renderDatePanel();
    }
    ensurePanel().classList.add('open');
    positionPanel();
  }

  function enhancePickerInput(input){
    if(!input || input.dataset.dcPickerEnhanced==='1') return;
    if(!input.id) input.id=`dcPicker_${Math.random().toString(36).slice(2)}`;
    input.dataset.dcPickerEnhanced='1';
    input.classList.add('dc-native-picker');
    input.closest('.field')?.classList.add('dc-whole-click');

    const trigger=document.createElement('button');
    trigger.type='button';trigger.className='dc-picker-trigger';trigger.dataset.for=input.id;trigger.setAttribute('aria-expanded','false');
    trigger.innerHTML=`<span class="dc-picker-trigger-main"><span class="dc-picker-trigger-value"></span></span><svg class="dc-picker-trigger-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="15" rx="3" stroke="currentColor" stroke-width="1.6"/><path d="M8 3.5v4M16 3.5v4M3.5 10h17" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;
    input.insertAdjacentElement('afterend',trigger);
    refreshTrigger(input);

    trigger.addEventListener('click',event=>{
      event.preventDefault();event.stopPropagation();
      if(activeInput===input && panel?.classList.contains('open')) closePicker();
      else openPicker(input,trigger);
    });
    input.addEventListener('change',()=>refreshTrigger(input));
    input.addEventListener('input',()=>refreshTrigger(input));

    const field=input.closest('.field');
    if(field && field.dataset.dcWholePickerFieldBound!=='1'){
      field.dataset.dcWholePickerFieldBound='1';
      field.addEventListener('click',event=>{
        if(event.target.closest('.dc-picker-trigger,.dc-picker-panel,button,select')) return;
        event.preventDefault();
        trigger.click();
      });
    }
  }

  function monthEndForSales(year,month){
    const now=new Date();
    const yesterday=new Date(now.getFullYear(),now.getMonth(),now.getDate()-1);
    if(year===now.getFullYear() && month===now.getMonth()){
      if(yesterday.getFullYear()===year&&yesterday.getMonth()===month) return yesterday.getDate();
      return 1;
    }
    return new Date(year,month+1,0).getDate();
  }

  function installSalesMonthField(){
    const filters=document.querySelector('.filters');
    const from=document.getElementById('from');
    const to=document.getElementById('to');
    if(!filters||!from||!to) return;

    const fromField=from.closest('.field'),toField=to.closest('.field');
    fromField?.classList.add('dc-date-range-field');toField?.classList.add('dc-date-range-field');

    let monthInput=document.getElementById('dcSalesMonth');
    if(!monthInput){
      const field=document.createElement('div');
      field.className='field dc-sales-month-field';
      field.innerHTML='<label>Месяц</label><input id="dcSalesMonth" type="month">';
      fromField?.insertAdjacentElement('beforebegin',field);
      monthInput=field.querySelector('input');
      enhancePickerInput(monthInput);

      monthInput.addEventListener('change',()=>{
        const p=parseMonth(monthInput.value);if(!p)return;
        const last=monthEndForSales(p.year,p.month);
        from.value=`${p.year}-${pad(p.month+1)}-01`;
        to.value=`${p.year}-${pad(p.month+1)}-${pad(last)}`;
        from.dispatchEvent(new Event('change',{bubbles:true}));
        to.dispatchEvent(new Event('change',{bubbles:true}));
        refreshTrigger(from);refreshTrigger(to);
      });
    }

    const syncMonthFromDates=()=>{
      const m=/^(\d{4})-(\d{2})/.exec(from.value||'');
      if(m && monthInput.value!==`${m[1]}-${m[2]}`){monthInput.value=`${m[1]}-${m[2]}`;refreshTrigger(monthInput)}
    };

    const syncMode=()=>{
      const monthBtn=document.querySelector('.report-mode-btn[data-mode="month"]');
      const isMonth=!!monthBtn?.classList.contains('active');
      filters.classList.toggle('dc-month-mode',isMonth);
      if(isMonth) syncMonthFromDates();
    };

    document.querySelectorAll('.report-mode-btn').forEach(btn=>{
      if(btn.dataset.dcMonthModeBound==='1') return;
      btn.dataset.dcMonthModeBound='1';
      btn.addEventListener('click',()=>setTimeout(syncMode,0));
      new MutationObserver(syncMode).observe(btn,{attributes:true,attributeFilter:['class']});
    });
    syncMode();
  }

  function boot(root=document){
    root.querySelectorAll?.('.field').forEach(bindWholeSelect);
    root.querySelectorAll?.('input[type="date"],input[type="month"]').forEach(enhancePickerInput);
    installSalesMonthField();
  }

  boot();
  const observer=new MutationObserver(mutations=>{
    let needs=false;
    for(const mutation of mutations){
      if([...mutation.addedNodes].some(n=>n.nodeType===1)){needs=true;break;}
    }
    if(needs) boot();
  });
  observer.observe(document.body,{childList:true,subtree:true});

  document.addEventListener('click',event=>{
    setTimeout(refreshAllTriggers,0);
    if(!event.target.closest('.dc-picker-panel,.dc-picker-trigger')) closePicker();
  },true);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closePicker()});
  window.addEventListener('resize',positionPanel);
  window.addEventListener('scroll',positionPanel,true);
})();
