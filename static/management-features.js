(() => {
  if (window.__dcManagementFeatures) return;
  window.__dcManagementFeatures = true;

  const style = document.createElement('style');
  style.textContent = `
    .report-mode-shell{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 12px;flex-wrap:wrap}
    .report-mode-title{color:var(--muted);font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.09em}
    .report-mode-tabs{display:flex;gap:7px;flex-wrap:wrap}
    .report-mode-btn{border:1px solid var(--line);background:#0d0d0d;color:#aaa;border-radius:999px;padding:8px 15px;font:inherit;font-weight:800;cursor:pointer}
    .report-mode-btn.active{border-color:var(--orange);background:var(--soft);color:#fff}
    .receipt-cards{grid-template-columns:repeat(5,1fr)!important}
    .doner-mix-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}
    .meat-cards{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:17px}
    .meat-card{border:1px solid var(--line);border-radius:16px;background:#0c0c0c;padding:16px;min-width:0}
    .meat-card small{color:var(--muted);font-size:11px;font-weight:800}
    .meat-card strong{display:block;font-size:28px;letter-spacing:-.04em;margin-top:9px}
    .meat-card span{display:block;color:var(--muted);font-size:11px;margin-top:6px;line-height:1.4}
    .size-list{display:grid;gap:12px;margin-top:17px}
    .size-row{display:grid;grid-template-columns:minmax(85px,.8fr) 1fr auto;gap:11px;align-items:center}
    .size-row b{font-size:12px}.size-row span{font-size:11px;color:var(--muted);white-space:nowrap}
    .size-track{height:7px;background:#262626;border-radius:99px;overflow:hidden}.size-fill{height:100%;background:linear-gradient(90deg,var(--orange),#ff8e5e);border-radius:99px}
    .management-note{margin-top:12px;color:#777;font-size:10px;line-height:1.45}
    @media(max-width:1100px){.receipt-cards{grid-template-columns:repeat(3,1fr)!important}}
    @media(max-width:900px){.receipt-cards{grid-template-columns:1fr 1fr!important}.doner-mix-grid{grid-template-columns:1fr}}
    @media(max-width:600px){.receipt-cards{grid-template-columns:1fr!important}.report-mode-shell{align-items:flex-start}.report-mode-tabs{width:100%}.report-mode-btn{flex:1}.meat-cards{grid-template-columns:1fr 1fr}.size-row{grid-template-columns:80px 1fr}.size-row span{grid-column:2}}
  `;
  document.head.appendChild(style);

  const $id = id => document.getElementById(id);
  const pad = n => String(n).padStart(2, '0');
  const isoLocal = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  const parseDate = s => { const [y,m,d]=String(s||'').split('-').map(Number); return new Date(y,m-1,d); };
  const dayCount = (a,b) => Math.round((parseDate(b)-parseDate(a))/86400000)+1;
  const pretty = s => { if(!s)return '—'; const [y,m,d]=String(s).slice(0,10).split('-'); return `${d}.${m}.${y}`; };

  let mode = 'day';

  const filters = document.querySelector('.filters');
  if (filters) {
    const shell = document.createElement('div');
    shell.className = 'report-mode-shell';
    shell.innerHTML = `<div class="report-mode-title">Режим отчёта</div><div class="report-mode-tabs"><button type="button" class="report-mode-btn active" data-mode="day">День</button><button type="button" class="report-mode-btn" data-mode="week">Неделя</button><button type="button" class="report-mode-btn" data-mode="month">Месяц</button></div>`;
    filters.insertAdjacentElement('beforebegin', shell);
  }

  const receiptChecks = $id('receiptChecks');
  if (receiptChecks) {
    const cards = receiptChecks.closest('.cards');
    if (cards) {
      cards.classList.add('receipt-cards');
      if (!$id('recordCheck')) {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<div class="label">Рекордный чек</div><div class="value" id="recordCheck">—</div><div class="sub" id="recordCheckMeta">Максимальный чек выбранного периода</div>`;
        cards.appendChild(card);
      }
    }
  }

  function sectionByTitle(title) {
    for (const h of document.querySelectorAll('.section h2')) {
      if ((h.textContent || '').trim() === title) {
        const head = h.closest('.section');
        return { head, body: head ? head.nextElementSibling : null, h };
      }
    }
    return null;
  }

  const category = sectionByTitle('Категории продаж');
  if (category?.body && !$id('donerMixBlock')) {
    const head = document.createElement('div');
    head.className = 'section';
    head.id = 'donerMixHead';
    head.innerHTML = `<h2>Донеры: мясо и размеры</h2><span class="muted">Только донеры, без комбо</span>`;
    const body = document.createElement('section');
    body.className = 'doner-mix-grid';
    body.id = 'donerMixBlock';
    body.innerHTML = `
      <div class="panel"><h3>Курица / говядина</h3><div class="muted">Доля в выручке распознанных донеров</div><div class="meat-cards"><div class="meat-card"><small>Курица</small><strong id="chickenRevenue">—</strong><span id="chickenMeta">—</span></div><div class="meat-card"><small>Говядина</small><strong id="beefRevenue">—</strong><span id="beefMeta">—</span></div></div><div class="management-note" id="meatNote"></div></div>
      <div class="panel"><h3>Размеры донеров</h3><div class="muted">Мини · Стандарт · 1.5 · Двойной</div><div class="size-list" id="donerSizeList"><div class="muted">Данные появятся после загрузки</div></div></div>`;
    category.body.insertAdjacentElement('afterend', body);
    body.insertAdjacentElement('beforebegin', head);
  }

  function setDates(from, to) {
    const a=$id('from'), b=$id('to');
    if(a) a.value=from;
    if(b) b.value=to;
    document.querySelectorAll('.preset').forEach(x=>x.classList.remove('active'));
  }

  function defaultRange(nextMode) {
    const now = new Date();
    const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate()-1);
    if (nextMode === 'day') return [isoLocal(yesterday), isoLocal(yesterday)];
    if (nextMode === 'week') {
      const start = new Date(yesterday); start.setDate(start.getDate()-6);
      return [isoLocal(start), isoLocal(yesterday)];
    }
    const start = new Date(yesterday.getFullYear(), yesterday.getMonth(), 1);
    return [isoLocal(start), isoLocal(yesterday)];
  }

  function setBlock(title, visible) {
    const block=sectionByTitle(title);
    if(block?.head) block.head.style.display=visible?'':'none';
    if(block?.body) block.body.style.display=visible?'':'none';
  }

  function applyMode(nextMode, setRange=false) {
    mode = nextMode;
    document.querySelectorAll('.report-mode-btn').forEach(b=>b.classList.toggle('active', b.dataset.mode===mode));
    if (setRange) {
      const [a,b]=defaultRange(mode); setDates(a,b);
    }

    // Day focuses on checks and hours; a one-point daily trend and best/worst day are not useful.
    // Month focuses on trends and mix; hourly heatmap is kept for Day/Week where staffing decisions are more actionable.
    setBlock('Динамика выручки', mode !== 'day');
    setBlock('Пульс периода', mode !== 'day');
    setBlock('Продажи по часам', mode !== 'month');

    const pulse=sectionByTitle('Пульс периода');
    if(pulse?.h) pulse.h.textContent = mode==='week' ? 'Пульс недели' : mode==='month' ? 'Пульс месяца' : 'Пульс периода';
  }

  document.querySelectorAll('.report-mode-btn').forEach(btn=>btn.addEventListener('click',()=>applyMode(btn.dataset.mode,true)));

  function inferModeFromDates() {
    const a=$id('from')?.value,b=$id('to')?.value;
    if(!a||!b)return;
    const count=dayCount(a,b);
    const start=parseDate(a),end=parseDate(b);
    if(count===1){applyMode('day',false);return;}
    if(count===7){applyMode('week',false);return;}
    if(start.getDate()===1 && start.getFullYear()===end.getFullYear() && start.getMonth()===end.getMonth()) {applyMode('month',false);return;}
    document.querySelectorAll('.report-mode-btn').forEach(x=>x.classList.remove('active'));
  }

  document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(inferModeFromDates,0));
  $id('from')?.addEventListener('change',()=>setTimeout(inferModeFromDates,120));
  $id('to')?.addEventListener('change',()=>setTimeout(inferModeFromDates,0));

  // Month mode compares month-to-date with the same dates of the previous month.
  const previousPrevPeriod = typeof prevPeriod === 'function' ? prevPeriod : null;
  window.prevPeriod = function(a,b) {
    if (mode === 'month') {
      const start=parseDate(a),end=parseDate(b);
      if(start.getDate()===1 && start.getFullYear()===end.getFullYear() && start.getMonth()===end.getMonth()) {
        const ps=new Date(start.getFullYear(),start.getMonth()-1,1);
        const lastPrev=new Date(start.getFullYear(),start.getMonth(),0).getDate();
        const pe=new Date(ps.getFullYear(),ps.getMonth(),Math.min(end.getDate(),lastPrev));
        return [isoLocal(ps),isoLocal(pe)];
      }
    }
    if(previousPrevPeriod) return previousPrevPeriod(a,b);
    const start=parseDate(a),end=parseDate(b); start.setDate(start.getDate()-7); end.setDate(end.getDate()-7); return [isoLocal(start),isoLocal(end)];
  };

  function isDoner(name) {
    const n=String(name||'').toLowerCase();
    return (n.includes('донер')||n.includes('doner')) && !n.includes('комбо') && !n.includes('combo');
  }
  function meatOf(name) {
    const n=String(name||'').toLowerCase();
    if(n.includes('кур')||n.includes('chicken')) return 'chicken';
    if(n.includes('гов')||n.includes('beef')) return 'beef';
    return 'other';
  }
  function sizeOf(name) {
    const n=String(name||'').toLowerCase();
    if(n.includes('мини')||n.includes('mini')) return 'mini';
    if(n.includes('1.5')||n.includes('1,5')||n.includes('полутор')) return 'onehalf';
    if(n.includes('двойн')||n.includes('double')) return 'double';
    return 'standard';
  }
  function nfmt(v){ try{return new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(Number(v||0));}catch(_){return String(v||0)} }
  function rub(v){ try{return `${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;}catch(_){return `${Math.round(Number(v||0))} ₸`;} }

  function renderProductMix() {
    let data=null;
    try { if(typeof currentData !== 'undefined') data=currentData; } catch(_) {}
    const items=(data?.products||[]).filter(p=>isDoner(p.name));
    if(!items.length){
      if($id('chickenRevenue'))$id('chickenRevenue').textContent='—';
      if($id('beefRevenue'))$id('beefRevenue').textContent='—';
      if($id('donerSizeList'))$id('donerSizeList').innerHTML='<div class="muted">Не нашли донеры в выбранном срезе</div>';
      return;
    }
    const meats={chicken:{revenue:0,qty:0},beef:{revenue:0,qty:0},other:{revenue:0,qty:0}};
    const sizes={mini:{label:'Мини',revenue:0,qty:0},standard:{label:'Стандарт',revenue:0,qty:0},onehalf:{label:'1.5',revenue:0,qty:0},double:{label:'Двойной',revenue:0,qty:0}};
    for(const p of items){
      const revenue=Number(p.revenue||0),qty=Number(p.quantity||0),m=meatOf(p.name),s=sizeOf(p.name);
      meats[m].revenue+=revenue; meats[m].qty+=qty; sizes[s].revenue+=revenue; sizes[s].qty+=qty;
    }
    const recognized=meats.chicken.revenue+meats.beef.revenue;
    const share=v=>recognized?v/recognized*100:0;
    $id('chickenRevenue').textContent=rub(meats.chicken.revenue);
    $id('beefRevenue').textContent=rub(meats.beef.revenue);
    $id('chickenMeta').textContent=`${nfmt(meats.chicken.qty)} шт. · ${nfmt(share(meats.chicken.revenue))}%`;
    $id('beefMeta').textContent=`${nfmt(meats.beef.qty)} шт. · ${nfmt(share(meats.beef.revenue))}%`;
    $id('meatNote').textContent=meats.other.revenue>0?`Не удалось определить мясо у части донеров: ${rub(meats.other.revenue)}.`:'Доля рассчитана только среди распознанных куриных и говяжьих донеров.';
    const max=Math.max(...Object.values(sizes).map(x=>x.revenue),1);
    $id('donerSizeList').innerHTML=Object.values(sizes).map(x=>`<div class="size-row"><b>${x.label}</b><div class="size-track"><div class="size-fill" style="width:${Math.max(x.revenue?3:0,x.revenue/max*100)}%"></div></div><span>${nfmt(x.qty)} шт. · ${rub(x.revenue)}</span></div>`).join('');
  }

  async function getRecord(point,a,b,channel) {
    const url=`/management-metrics?point=${encodeURIComponent(point)}&from=${a}&to=${b}&channel=${encodeURIComponent(channel||'all')}`;
    try {
      const r=await fetch(url,{headers:{Accept:'application/json'}}); const j=await r.json();
      if(!r.ok||!j?.success) throw new Error(j?.message||'Ошибка');
      return j;
    } catch(e){ return {_error:e.message}; }
  }
  function renderRecord(j) {
    const value=$id('recordCheck'),meta=$id('recordCheckMeta'); if(!value||!meta)return;
    if(!j||j._error){value.textContent='—';meta.textContent='Не удалось загрузить рекордный чек';return;}
    const r=j.recordCheck;
    if(!r){value.textContent='—';meta.textContent='Нет чеков в выбранном периоде';return;}
    value.textContent=rub(r.amount);
    meta.textContent=`${pretty(r.date)}${r.time?` · ${r.time}`:''}`;
  }

  const go=$id('go');
  if(go && typeof go.onclick==='function') {
    const previousGo=go.onclick;
    go.onclick=async function(event){
      const a=$id('from')?.value,b=$id('to')?.value,point=$id('point')?.value||'Arai',channel=$id('salesChannel')?.value||'all';
      if($id('recordCheck')){$id('recordCheck').textContent='…';$id('recordCheckMeta').textContent='Ищем максимальный чек';}
      const recordPromise=(a&&b)?getRecord(point,a,b,channel):Promise.resolve(null);
      const result=await previousGo.call(this,event);
      renderProductMix();
      renderRecord(await recordPromise);
      inferModeFromDates();
      const compare=$id('comparePeriodLabel');
      if(compare && mode==='month' && a && b){
        const [pa,pb]=window.prevPeriod(a,b);
        compare.textContent=`Сравнение с ${pretty(pa)} — ${pretty(pb)} — предыдущий месяц`;
      }
      return result;
    };
  }

  applyMode('day', false);
})();
