(() => {
  if (window.__dcOnlineOfflineTrends) return;
  window.__dcOnlineOfflineTrends = true;
  if (!location.pathname.endsWith('/dashboard-v2.html')) return;

  const $ = id => document.getElementById(id);
  const money = value => `${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(value||0))} ₸`;
  const compact = value => new Intl.NumberFormat('ru-RU',{notation:'compact',maximumFractionDigits:1}).format(Number(value||0));
  const percent = value => `${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(Number(value||0))}%`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const monthTitle = iso => {
    const [year,month] = String(iso||'').slice(0,7).split('-').map(Number);
    if(!year||!month) return 'Месяц';
    const text = new Intl.DateTimeFormat('ru-RU',{month:'long',year:'numeric'}).format(new Date(year,month-1,1));
    return text.charAt(0).toUpperCase()+text.slice(1);
  };
  const shortMonth = iso => {
    const [year,month] = String(iso||'').slice(0,7).split('-').map(Number);
    if(!year||!month) return String(iso||'');
    return new Intl.DateTimeFormat('ru-RU',{month:'short'}).format(new Date(year,month-1,1)).replace('.','');
  };
  const dayLabel = iso => String(iso||'').slice(8,10);
  const dateTitle = iso => {
    const [y,m,d] = String(iso||'').slice(0,10).split('-');
    return d&&m&&y ? `${d}.${m}.${y}` : String(iso||'—');
  };

  const style = document.createElement('style');
  style.textContent = `
    .oo-section-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:30px 0 12px}
    .oo-section-head h2{margin:0;font-size:20px}.oo-head-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .oo-source{display:inline-flex;align-items:center;gap:6px;border:1px solid #304a3c;color:#9fe4bf;border-radius:999px;padding:5px 9px;font-size:10px}.oo-source:before{content:"";width:6px;height:6px;border-radius:50%;background:#4bd396}
    .oo-mode{display:flex;gap:4px;padding:4px;border:1px solid #303030;border-radius:12px;background:#0b0b0b}.oo-mode button{height:30px;border:0;border-radius:8px;background:transparent;color:#999;padding:0 12px;font:inherit;font-size:11px;font-weight:800;cursor:pointer}.oo-mode button.active{background:rgba(255,90,31,.14);color:#fff;box-shadow:inset 0 0 0 1px #8d3d20}
    .oo-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}.oo-panel{padding:20px;min-width:0}.oo-panel.wide{grid-column:1/-1}.oo-panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:6px}.oo-panel-head h3{margin:0;font-size:16px}.oo-panel-head .muted{font-size:11px;margin-top:4px;line-height:1.4}
    .oo-legend{display:flex;align-items:center;gap:12px;flex-wrap:wrap;color:#999;font-size:10px}.oo-legend span{display:inline-flex;align-items:center;gap:6px}.oo-legend i{width:16px;height:3px;border-radius:6px;display:inline-block}.oo-legend .online i{background:#4d9fff}.oo-legend .offline i{background:#ff685e}
    .oo-chart{height:285px;position:relative;margin-top:9px}.oo-chart svg{display:block;width:100%;height:100%;overflow:visible}.oo-gridline{stroke:#272727;stroke-width:1}.oo-axis{fill:#777;font-size:10px}.oo-line-online{fill:none;stroke:#4d9fff;stroke-width:3.5;stroke-linecap:round;stroke-linejoin:round}.oo-line-offline{fill:none;stroke:#ff685e;stroke-width:3.5;stroke-linecap:round;stroke-linejoin:round}.oo-dot-online{fill:#4d9fff;stroke:#111;stroke-width:2.5}.oo-dot-offline{fill:#ff685e;stroke:#111;stroke-width:2.5}.oo-hit{fill:transparent;cursor:pointer}.oo-value-online,.oo-value-offline{font-size:8.5px;font-weight:800;text-anchor:middle}.oo-value-online{fill:#8bc3ff}.oo-value-offline{fill:#ff9992}
    .oo-tooltip{position:absolute;z-index:12;display:none;pointer-events:none;transform:translate(-50%,-108%);min-width:170px;padding:10px 12px;border:1px solid #383838;border-radius:12px;background:rgba(8,8,8,.97);box-shadow:0 12px 34px rgba(0,0,0,.5);font-size:11px;color:#aaa;white-space:nowrap}.oo-tooltip b{display:block;color:#fff;font-size:12px;margin-bottom:6px}.oo-tooltip .on{color:#8bc3ff}.oo-tooltip .off{color:#ff9992}.oo-tooltip strong{color:inherit}.oo-loading{height:255px;display:grid;place-items:center;color:#8e8e88;font-size:12px}.oo-note{margin-top:8px;color:#777;font-size:10px;line-height:1.45}.oo-current{color:#ff9d73}
    @media(max-width:900px){.oo-grid{grid-template-columns:1fr}.oo-panel.wide{grid-column:auto}.oo-chart{height:260px}.oo-section-head{align-items:flex-start}}
    @media(max-width:600px){.oo-section-head{flex-direction:column}.oo-head-right{width:100%;justify-content:space-between}.oo-mode{width:100%}.oo-mode button{flex:1}.oo-panel{padding:16px}.oo-chart{height:235px}.oo-panel-head{flex-direction:column}.oo-axis{font-size:9px}}
  `;
  document.head.appendChild(style);

  let state = null;
  let mode = 'days';
  let requestNo = 0;
  let uiReady = false;

  function legend(){
    return '<div class="oo-legend"><span class="online"><i></i>Онлайн</span><span class="offline"><i></i>Оффлайн</span></div>';
  }

  function ensureUI(){
    if(uiReady && $('onlineOfflineTrends')) return true;
    const anchor = $('staticMonthTrend');
    if(!anchor) return false;

    const head = document.createElement('div');
    head.id = 'onlineOfflineTrendsHead';
    head.className = 'oo-section-head';
    head.innerHTML = `
      <h2>Онлайн / оффлайн динамика</h2>
      <div class="oo-head-right">
        <span class="oo-source">iikoServer OLAP</span>
        <div class="oo-mode" role="group" aria-label="Период графиков">
          <button type="button" data-mode="days" class="active">По дням</button>
          <button type="button" data-mode="months">По месяцам</button>
        </div>
      </div>`;

    const block = document.createElement('section');
    block.id = 'onlineOfflineTrends';
    block.className = 'oo-grid';
    block.innerHTML = `
      <div class="panel oo-panel" id="ooCurrentPanel">
        <div class="oo-panel-head"><div><h3 id="ooCurrentTitle">Текущий месяц</h3><div class="muted" id="ooCurrentSub">Онлайн и оффлайн выручка по дням</div></div>${legend()}</div>
        <div class="oo-chart" id="ooCurrentChart"><div class="oo-loading">Получаем онлайн/оффлайн продажи…</div></div>
      </div>
      <div class="panel oo-panel" id="ooComparePanel">
        <div class="oo-panel-head"><div><h3 id="ooCompareTitle">Месяц сравнения</h3><div class="muted" id="ooCompareSub">Онлайн и оффлайн выручка по дням</div></div>${legend()}</div>
        <div class="oo-chart" id="ooCompareChart"><div class="oo-loading">Получаем сравнение…</div></div>
      </div>
      <div class="panel oo-panel wide" id="ooSharePanel">
        <div class="oo-panel-head"><div><h3 id="ooShareTitle">Доля онлайн и оффлайн</h3><div class="muted" id="ooShareSub">Процент от общей классифицированной выручки за день</div></div>${legend()}</div>
        <div class="oo-chart" id="ooShareChart"><div class="oo-loading">Считаем доли…</div></div>
        <div class="oo-note">Доля считается как онлайн / (онлайн + оффлайн) и оффлайн / (онлайн + оффлайн). Баллы, питание персонала и нераспознанные источники в знаменатель не входят.</div>
      </div>`;

    anchor.insertAdjacentElement('afterend', head);
    head.insertAdjacentElement('afterend', block);

    head.querySelectorAll('.oo-mode button').forEach(button => {
      button.addEventListener('click', () => {
        mode = button.dataset.mode || 'days';
        head.querySelectorAll('.oo-mode button').forEach(x => x.classList.toggle('active', x === button));
        renderAll();
      });
    });

    uiReady = true;
    return true;
  }

  function smartIndexes(data){
    const result = new Set();
    const n = data.length;
    if(!n) return result;
    result.add(0);result.add(n-1);
    if(n <= 12){ data.forEach((_,i)=>result.add(i)); return result; }
    const step = window.innerWidth > 1100 ? 3 : 5;
    data.forEach((_,i)=>{ if(i%step===0) result.add(i); });
    return result;
  }

  function renderDual(root, series, options={}){
    if(!root) return;
    const isShare = options.kind === 'share';
    const monthly = options.monthly === true;
    const data = (series||[]).map(item => ({...item,
      online: Number(isShare ? item.onlineShare : item.onlineRevenue || 0),
      offline: Number(isShare ? item.offlineShare : item.offlineRevenue || 0),
    }));
    if(!data.length){ root.innerHTML='<div class="oo-loading">Нет данных</div>'; return; }

    const W=960,H=280,L=66,R=20,T=30,B=42,n=data.length;
    const rawMax = isShare ? 100 : Math.max(...data.flatMap(x=>[x.online,x.offline]),1);
    const max = isShare ? 100 : rawMax * 1.08;
    const x = i => n===1 ? (L+W-R)/2 : L+i*(W-L-R)/(n-1);
    const y = value => T+(H-T-B)*(1-Number(value||0)/(max||1));
    const onlinePoints = data.map((d,i)=>`${x(i)},${y(d.online)}`).join(' ');
    const offlinePoints = data.map((d,i)=>`${x(i)},${y(d.offline)}`).join(' ');
    let grid='', labels='', dots='';
    const levels = isShare ? [100,75,50,25,0] : [max,max*.75,max*.5,max*.25,0];
    levels.forEach((value,index)=>{
      const yy=T+index*(H-T-B)/(levels.length-1);
      grid += `<line class="oo-gridline" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text class="oo-axis" x="0" y="${yy+4}">${isShare?percent(value):compact(value)}</text>`;
    });

    const valueIndexes=smartIndexes(data);
    const labelStep=monthly?1:Math.max(1,Math.ceil(n/8));
    data.forEach((d,i)=>{
      const px=x(i),pyOn=y(d.online),pyOff=y(d.offline);
      const label=monthly?shortMonth(d.month):dayLabel(d.date);
      if(i%labelStep===0||i===n-1) labels += `<text class="oo-axis" text-anchor="middle" x="${px}" y="${H-13}">${esc(label)}</text>`;
      dots += `<circle class="oo-dot-online" cx="${px}" cy="${pyOn}" r="4.5"></circle><circle class="oo-dot-offline" cx="${px}" cy="${pyOff}" r="4.5"></circle><circle class="oo-hit" data-index="${i}" cx="${px}" cy="${(pyOn+pyOff)/2}" r="18"></circle>`;
      if(valueIndexes.has(i)){
        const onlineLabel=isShare?percent(d.online):compact(d.online);
        const offlineLabel=isShare?percent(d.offline):compact(d.offline);
        if(d.online>0) labels += `<text class="oo-value-online" x="${px}" y="${Math.max(12,pyOn-10)}">${esc(onlineLabel)}</text>`;
        if(d.offline>0) labels += `<text class="oo-value-offline" x="${px}" y="${Math.min(H-B-4,pyOff+15)}">${esc(offlineLabel)}</text>`;
      }
    });

    root.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-label="Онлайн и оффлайн продажи">${grid}<polyline class="oo-line-online" points="${onlinePoints}"/><polyline class="oo-line-offline" points="${offlinePoints}"/>${dots}${labels}</svg><div class="oo-tooltip"></div>`;
    const tooltip=root.querySelector('.oo-tooltip');
    const svg=root.querySelector('svg');
    const showTip=index=>{
      const d=data[index]; if(!d||!svg||!tooltip)return;
      const rect=svg.getBoundingClientRect();
      const px=x(index)/W*rect.width;
      const py=Math.min(y(d.online),y(d.offline))/H*rect.height;
      const title=monthly?monthTitle(`${d.month}-01`):dateTitle(d.date);
      tooltip.innerHTML=`<b>${esc(title)}</b><div class="on">Онлайн: <strong>${isShare?percent(d.online):money(d.online)}</strong></div><div class="off">Оффлайн: <strong>${isShare?percent(d.offline):money(d.offline)}</strong></div>${!isShare?`<div style="margin-top:5px">Всего: <strong style="color:#fff">${money(Number(d.online)+Number(d.offline))}</strong></div>`:''}`;
      tooltip.style.left=`${Math.max(70,Math.min(rect.width-70,px))}px`;
      tooltip.style.top=`${Math.max(48,py)}px`;
      tooltip.style.display='block';
    };
    root.querySelectorAll('.oo-hit').forEach(hit=>{
      const fn=()=>showTip(Number(hit.dataset.index));
      hit.addEventListener('pointerenter',fn);hit.addEventListener('pointerdown',fn);hit.addEventListener('click',fn);
    });
    root.addEventListener('pointerleave',()=>{if(tooltip)tooltip.style.display='none'});
  }

  function setLoading(){
    ['ooCurrentChart','ooCompareChart','ooShareChart'].forEach(id=>{const el=$(id);if(el)el.innerHTML='<div class="oo-loading">Получаем данные из iikoServer…</div>';});
  }

  function renderAll(){
    if(!state || !ensureUI()) return;
    const currentPanel=$('ooCurrentPanel'), comparePanel=$('ooComparePanel');
    if(mode==='months'){
      currentPanel?.classList.add('wide');
      if(comparePanel) comparePanel.style.display='none';
      $('ooCurrentTitle').textContent='Онлайн и оффлайн по месяцам';
      $('ooCurrentSub').textContent=`${monthTitle(state.monthly?.from)} — ${monthTitle(state.monthly?.to)} · выручка по месяцам`;
      renderDual($('ooCurrentChart'),state.monthly?.series||[],{monthly:true,kind:'money'});
      $('ooShareTitle').textContent='Доля онлайн и оффлайн по месяцам';
      $('ooShareSub').textContent='Процент от общей классифицированной выручки за каждый месяц';
      renderDual($('ooShareChart'),state.monthly?.series||[],{monthly:true,kind:'share'});
    }else{
      currentPanel?.classList.remove('wide');
      if(comparePanel) comparePanel.style.display='block';
      $('ooCurrentTitle').textContent=monthTitle(state.current?.from);
      const ct=state.current?.totals||{};
      $('ooCurrentSub').innerHTML=`Онлайн ${money(ct.onlineRevenue)} · оффлайн ${money(ct.offlineRevenue)} · <span class="oo-current">текущий месяц</span>`;
      $('ooCompareTitle').textContent=monthTitle(state.comparison?.from);
      const pt=state.comparison?.totals||{};
      $('ooCompareSub').textContent=`Онлайн ${money(pt.onlineRevenue)} · оффлайн ${money(pt.offlineRevenue)} · полный месяц`;
      renderDual($('ooCurrentChart'),state.current?.series||[],{kind:'money'});
      renderDual($('ooCompareChart'),state.comparison?.series||[],{kind:'money'});
      $('ooShareTitle').textContent=`Доля онлайн и оффлайн — ${monthTitle(state.current?.from)}`;
      $('ooShareSub').textContent='Процент от общей классифицированной выручки за каждый день';
      renderDual($('ooShareChart'),state.current?.series||[],{kind:'share'});
    }
  }

  async function loadData(){
    if(!ensureUI()) return;
    const point=$('point')?.value;
    if(!point) return;
    const compareOffset=Number($('trendCompareMonth')?.value||2);
    const myRequest=++requestNo;
    setLoading();
    try{
      const response=await fetch(`/online-offline-trends?point=${encodeURIComponent(point)}&compareOffset=${compareOffset}`,{headers:{Accept:'application/json'}});
      const payload=await response.json();
      if(myRequest!==requestNo)return;
      if(!response.ok||!payload?.success)throw new Error(payload?.message||payload?.details||`HTTP ${response.status}`);
      state=payload;
      renderAll();
    }catch(error){
      if(myRequest!==requestNo)return;
      ['ooCurrentChart','ooCompareChart','ooShareChart'].forEach(id=>{const el=$(id);if(el)el.innerHTML=`<div class="oo-loading">Не удалось загрузить онлайн/оффлайн динамику: ${esc(error.message)}</div>`;});
    }
  }

  function bind(){
    if(!ensureUI()) return false;
    $('trendCompareMonth')?.addEventListener('change',loadData);
    $('point')?.addEventListener('change',loadData);
    window.addEventListener('dc:points-changed',loadData);
    window.addEventListener('resize',()=>{if(state)renderAll()});
    loadData();
    return true;
  }

  if(!bind()){
    let tries=0;
    const timer=setInterval(()=>{
      tries++;
      if(bind()||tries>40)clearInterval(timer);
    },150);
  }
})();
