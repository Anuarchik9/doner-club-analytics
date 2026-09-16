(() => {
  if (window.__dcTrendFeatures) return;
  window.__dcTrendFeatures = true;

  const style = document.createElement('style');
  style.textContent = `
    .static-trend-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}
    .static-trend-panel{padding:20px;min-width:0}
    .static-trend-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:8px}
    .static-trend-head h3{margin:0;font-size:16px}.static-trend-head .muted{font-size:11px;margin-top:4px}
    .trend-compare-select{height:34px;border:1px solid var(--line);border-radius:10px;background:#0b0b0b;color:#ddd;padding:0 9px;font-size:11px;max-width:132px}
    .dc-line-chart{height:285px;position:relative;margin-top:8px}.dc-line-chart svg{display:block;width:100%;height:100%;overflow:visible}
    .dc-trend-gridline{stroke:#272727;stroke-width:1}.dc-trend-axis{fill:#777;font-size:10px}.dc-trend-line{fill:none;stroke:var(--orange);stroke-width:3.5;stroke-linecap:round;stroke-linejoin:round}
    .dc-trend-area{fill:url(#dcTrendFill)}.dc-trend-dot{fill:var(--orange);stroke:#121212;stroke-width:3}.dc-trend-hit{fill:transparent;cursor:pointer}
    .dc-trend-value{fill:#ff9d73;font-size:9px;font-weight:800;text-anchor:middle}.dc-trend-today-ring{fill:none;stroke:var(--orange);stroke-width:2;transform-box:fill-box;transform-origin:center;animation:dcPulse 1.35s ease-out infinite}
    @keyframes dcPulse{0%{transform:scale(.55);opacity:1}75%,100%{transform:scale(2.2);opacity:0}}
    .dc-trend-tooltip{position:absolute;z-index:8;pointer-events:none;display:none;transform:translate(-50%,-110%);min-width:145px;padding:9px 11px;border:1px solid #383838;border-radius:11px;background:rgba(8,8,8,.96);box-shadow:0 10px 30px rgba(0,0,0,.45);font-size:11px;color:#aaa;white-space:nowrap}
    .dc-trend-tooltip b{display:block;color:#fff;font-size:12px;margin-bottom:5px}.dc-trend-tooltip strong{color:#fff}
    .trend-loading{height:255px;display:grid;place-items:center;color:var(--muted);font-size:12px}
    .trend-current-note{display:inline-flex;align-items:center;gap:7px;color:#ff9d73;font-size:10px;margin-top:7px}.trend-current-note:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--orange);box-shadow:0 0 0 0 rgba(255,90,31,.5);animation:dcDot 1.4s infinite}
    @keyframes dcDot{0%{box-shadow:0 0 0 0 rgba(255,90,31,.55)}70%{box-shadow:0 0 0 8px rgba(255,90,31,0)}100%{box-shadow:0 0 0 0 rgba(255,90,31,0)}}
    .hour-line-shell{border-bottom:1px solid #242424;padding-bottom:18px;margin-bottom:18px}.hour-line-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:4px}.hour-line-head h3{margin:0;font-size:15px}.hour-line-head span{font-size:10px;color:var(--muted)}
    .hour-line-chart{height:235px;position:relative}
    @media(max-width:900px){.static-trend-grid{grid-template-columns:1fr}.dc-line-chart{height:260px}}
    @media(max-width:600px){.static-trend-panel{padding:16px}.dc-line-chart{height:230px}.hour-line-chart{height:220px}.static-trend-head{align-items:flex-start}.trend-compare-select{max-width:120px}.dc-trend-axis{font-size:9px}}
  `;
  document.head.appendChild(style);

  const $ = id => document.getElementById(id);
  const money = v => `${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;
  const compact = v => new Intl.NumberFormat('ru-RU',{notation:'compact',maximumFractionDigits:1}).format(Number(v||0));
  const dateText = s => { const [y,m,d]=String(s||'').slice(0,10).split('-'); return d&&m&&y ? `${d}.${m}.${y}` : String(s||'—'); };
  const monthName = s => {
    const [y,m] = String(s||'').slice(0,7).split('-').map(Number);
    if(!y||!m) return 'Месяц';
    const text = new Intl.DateTimeFormat('ru-RU',{month:'long',year:'numeric'}).format(new Date(y,m-1,1));
    return text.charAt(0).toUpperCase()+text.slice(1);
  };
  const previousMonthOptions = () => {
    const now=new Date(), names=[];
    for(let offset=1;offset<=3;offset++){
      const d=new Date(now.getFullYear(),now.getMonth()-offset,1);
      let label=new Intl.DateTimeFormat('ru-RU',{month:'long'}).format(d);
      label=label.charAt(0).toUpperCase()+label.slice(1);
      names.push({offset,label});
    }
    return names;
  };

  function findSection(title){
    for(const h of document.querySelectorAll('.section h2')){
      if((h.textContent||'').trim()===title){const head=h.closest('.section');return {head,body:head?.nextElementSibling,h};}
    }
    return null;
  }

  // Always-visible current-month trend. It is independent of the selected report dates,
  // but follows the chosen point and sales channel.
  const dynamic = findSection('Динамика выручки');
  if(dynamic?.head && !$('staticMonthTrend')){
    const head=document.createElement('div');
    head.className='section';
    head.id='staticMonthTrendHead';
    head.innerHTML='<h2>Ежедневная тенденция</h2><span class="source-chip">iikoServer OLAP</span>';
    const block=document.createElement('section');
    block.id='staticMonthTrend';
    block.className='static-trend-grid';
    const opts=previousMonthOptions();
    block.innerHTML=`
      <div class="panel static-trend-panel">
        <div class="static-trend-head"><div><h3 id="currentTrendTitle">Текущий месяц</h3><div class="muted" id="currentTrendTotal">Загружаем…</div></div></div>
        <div class="dc-line-chart" id="currentTrendChart"><div class="trend-loading">Получаем ежедневную выручку…</div></div>
        <div class="trend-current-note" id="todayTrendNote">Последняя точка — текущий незавершённый день</div>
      </div>
      <div class="panel static-trend-panel">
        <div class="static-trend-head"><div><h3 id="compareTrendTitle">Сравнение</h3><div class="muted" id="compareTrendTotal">Выберите месяц</div></div><select id="trendCompareMonth" class="trend-compare-select">${opts.map(x=>`<option value="${x.offset}" ${x.offset===2?'selected':''}>${x.label}</option>`).join('')}</select></div>
        <div class="dc-line-chart" id="compareTrendChart"><div class="trend-loading">Получаем сравнение…</div></div>
      </div>`;
    dynamic.head.insertAdjacentElement('beforebegin',block);
    block.insertAdjacentElement('beforebegin',head);
  }

  // Hourly line chart lives inside the existing hourly analytics panel and appears for a single day.
  const hourSection=findSection('Продажи по часам');
  if(hourSection?.body && !$('hourRevenueLine')){
    const shell=document.createElement('div');
    shell.id='hourRevenueLine';
    shell.className='hour-line-shell';
    shell.innerHTML='<div class="hour-line-head"><h3>Выручка по часам</h3><span>Только для выбранного дня</span></div><div class="hour-line-chart dc-line-chart" id="hourRevenueChart"><div class="trend-loading">Выберите один день</div></div>';
    hourSection.body.insertAdjacentElement('afterbegin',shell);
  }

  function smartValueIndexes(series,isCurrent){
    const set=new Set();
    if(!series.length)return set;
    set.add(0);set.add(series.length-1);
    let maxI=0,minI=0;
    series.forEach((x,i)=>{if(Number(x.revenue)>Number(series[maxI].revenue))maxI=i;if(Number(x.revenue)<Number(series[minI].revenue))minI=i;});
    set.add(maxI);set.add(minI);
    if(window.innerWidth>1100 && series.length<=18) series.forEach((_,i)=>set.add(i));
    else if(window.innerWidth>700 && series.length<=20) series.forEach((_,i)=>{if(i%2===0)set.add(i)});
    if(isCurrent)set.add(series.length-1);
    return set;
  }

  function renderLine(root,series,{today=null,current=false,hourly=false}={}){
    if(!root)return;
    const data=(series||[]).map(x=>({...x,revenue:Number(x.revenue||0)}));
    if(!data.length){root.innerHTML='<div class="trend-loading">Нет данных</div>';return;}
    const W=900,H=270,L=62,R=18,T=28,B=40,n=data.length;
    const max=Math.max(...data.map(x=>x.revenue),1);
    const min=0;
    const x=i=>n===1?(L+W-R)/2:L+i*(W-L-R)/(n-1);
    const y=v=>T+(H-T-B)*(1-(Number(v)-min)/(max-min||1));
    const points=data.map((d,i)=>`${x(i)},${y(d.revenue)}`).join(' ');
    const area=`${x(0)},${H-B} ${points} ${x(n-1)},${H-B}`;
    let grid='',labels='',dots='';
    for(let i=0;i<4;i++){
      const yy=T+i*(H-T-B)/3,val=max*(1-i/3);
      grid+=`<line class="dc-trend-gridline" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text class="dc-trend-axis" x="0" y="${yy+4}">${compact(val)}</text>`;
    }
    const valueIndexes=smartValueIndexes(data,current);
    const labelStep=hourly?3:Math.max(1,Math.ceil(n/7));
    data.forEach((d,i)=>{
      const px=x(i),py=y(d.revenue),isToday=current&&today&&String(d.date).slice(0,10)===String(today).slice(0,10);
      const rawLabel=hourly?(d.label||`${padHour(d.hour)}:00`):String(d.date||'').slice(8,10);
      if(i%labelStep===0||i===n-1)labels+=`<text class="dc-trend-axis" text-anchor="middle" x="${px}" y="${H-13}">${rawLabel}</text>`;
      dots+=`${isToday?`<circle class="dc-trend-today-ring" cx="${px}" cy="${py}" r="7"></circle>`:''}<circle class="dc-trend-dot" cx="${px}" cy="${py}" r="4.5"></circle><circle class="dc-trend-hit" data-index="${i}" cx="${px}" cy="${py}" r="15"></circle>`;
      if(valueIndexes.has(i)&&d.revenue>0)labels+=`<text class="dc-trend-value" x="${px}" y="${Math.max(12,py-11)}">${compact(d.revenue)}</text>`;
    });
    root.innerHTML=`<svg viewBox="0 0 ${W} ${H}" aria-label="График ежедневной выручки"><defs><linearGradient id="dcTrendFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ff5a1f" stop-opacity=".18"/><stop offset="1" stop-color="#ff5a1f" stop-opacity="0"/></linearGradient></defs>${grid}<polygon class="dc-trend-area" points="${area}"/><polyline class="dc-trend-line" points="${points}"/>${dots}${labels}</svg><div class="dc-trend-tooltip"></div>`;
    const tip=root.querySelector('.dc-trend-tooltip');
    root.querySelectorAll('.dc-trend-hit').forEach(hit=>{
      const show=()=>{
        const i=Number(hit.dataset.index),d=data[i],svg=root.querySelector('svg'),box=svg.getBoundingClientRect();
        const px=x(i)/W*box.width,py=y(d.revenue)/H*box.height;
        const title=hourly?(d.label||`${padHour(d.hour)}:00`):dateText(d.date);
        tip.innerHTML=`<b>${title}</b><span>Выручка: <strong>${money(d.revenue)}</strong></span>${current&&today&&String(d.date).slice(0,10)===String(today).slice(0,10)?'<br><span style="color:#ff9d73">День ещё идёт</span>':''}`;
        tip.style.left=`${Math.max(55,Math.min(box.width-55,px))}px`;tip.style.top=`${Math.max(45,py)}px`;tip.style.display='block';
      };
      hit.addEventListener('pointerenter',show);hit.addEventListener('pointerdown',show);hit.addEventListener('click',show);
    });
    root.addEventListener('pointerleave',()=>{if(tip)tip.style.display='none'});
  }
  function padHour(h){return String(Number(h||0)).padStart(2,'0')}

  let trendRequest=0;
  async function loadStaticTrend(){
    const point=$('point')?.value;
    if(!point)return;
    const channel=$('salesChannel')?.value||'all';
    const compareOffset=Number($('trendCompareMonth')?.value||2);
    const requestId=++trendRequest;
    if($('currentTrendChart'))$('currentTrendChart').innerHTML='<div class="trend-loading">Получаем ежедневную выручку…</div>';
    if($('compareTrendChart'))$('compareTrendChart').innerHTML='<div class="trend-loading">Получаем сравнение…</div>';
    try{
      const r=await fetch(`/trend-analytics?point=${encodeURIComponent(point)}&channel=${encodeURIComponent(channel)}&compareOffset=${compareOffset}`,{headers:{Accept:'application/json'}});
      const j=await r.json();
      if(requestId!==trendRequest)return;
      if(!r.ok||!j?.success)throw new Error(j?.message||j?.details||`HTTP ${r.status}`);
      $('currentTrendTitle').textContent=monthName(j.current?.from);
      $('currentTrendTotal').textContent=`${money(j.current?.revenue)} · с 1 числа по сегодня`;
      $('compareTrendTitle').textContent=monthName(j.comparison?.from);
      $('compareTrendTotal').textContent=`${money(j.comparison?.revenue)} · полный месяц`;
      renderLine($('currentTrendChart'),j.current?.series||[],{today:j.today,current:true});
      renderLine($('compareTrendChart'),j.comparison?.series||[],{});
      $('todayTrendNote').style.display=j.todayIncomplete?'inline-flex':'none';
    }catch(e){
      if(requestId!==trendRequest)return;
      if($('currentTrendChart'))$('currentTrendChart').innerHTML=`<div class="trend-loading">Не удалось загрузить тенденцию: ${escapeHtml(e.message)}</div>`;
      if($('compareTrendChart'))$('compareTrendChart').innerHTML='<div class="trend-loading">Сравнение недоступно</div>';
    }
  }
  function escapeHtml(v){return String(v||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

  function selectedDays(){const a=$('from')?.value,b=$('to')?.value;if(!a||!b)return 0;return Math.round((new Date(`${b}T00:00:00`)-new Date(`${a}T00:00:00`))/86400000)+1;}
  function enforceSelectedTrend(){
    const days=selectedDays();
    const d=findSection('Динамика выручки');
    if(d?.head)d.head.style.display=days===1?'none':'';
    if(d?.body)d.body.style.display=days===1?'none':'';
    const h=findSection('Продажи по часам');
    if(days===1){if(h?.head)h.head.style.display='';if(h?.body)h.body.style.display='';}
    const hourLine=$('hourRevenueLine');if(hourLine)hourLine.style.display=days===1?'':'none';
    if(days===1)renderHourly();
  }

  function renderHourly(){
    if(selectedDays()!==1)return;
    let receipt=null;
    try{if(typeof receiptCurrent!=='undefined')receipt=receiptCurrent}catch(_){receipt=null}
    const root=$('hourRevenueChart');if(!root)return;
    const hourly=receipt?.hourly||[];
    if(!hourly.length){root.innerHTML='<div class="trend-loading">Почасовые данные ещё загружаются…</div>';return;}
    renderLine(root,hourly.map(x=>({hour:x.hour,label:x.label,revenue:Number(x.revenue||0)})),{hourly:true});
  }

  // Heatmap changes when receipt analytics finishes. Re-render the line from the same hourly dataset.
  const heat=$('heatGrid');
  if(heat){new MutationObserver(()=>{if(selectedDays()===1)setTimeout(renderHourly,0)}).observe(heat,{childList:true,subtree:true});}

  $('trendCompareMonth')?.addEventListener('change',loadStaticTrend);
  $('point')?.addEventListener('change',loadStaticTrend);
  document.addEventListener('change',e=>{if(e.target?.id==='salesChannel')loadStaticTrend();if(e.target?.id==='from'||e.target?.id==='to')setTimeout(enforceSelectedTrend,180)});
  $('go')?.addEventListener('click',()=>{setTimeout(enforceSelectedTrend,120);setTimeout(renderHourly,700);setTimeout(renderHourly,2200)});

  // Departments are loaded asynchronously; start the static trend as soon as the point selector is ready.
  let tries=0;
  const boot=setInterval(()=>{
    tries++;
    if($('point')?.value){clearInterval(boot);loadStaticTrend();enforceSelectedTrend();}
    if(tries>40)clearInterval(boot);
  },250);
  setInterval(()=>{if(document.visibilityState==='visible')loadStaticTrend()},5*60*1000);
})();
