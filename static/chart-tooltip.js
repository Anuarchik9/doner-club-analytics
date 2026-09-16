(() => {
  const style = document.createElement('style');
  style.textContent = `
    .dc-chart-tooltip{position:absolute;z-index:8;pointer-events:none;min-width:168px;padding:10px 12px;border:1px solid #3a3a3a;border-radius:12px;background:rgba(10,10,10,.96);box-shadow:0 12px 34px rgba(0,0,0,.45);color:#f7f7f2;font:12px Inter,system-ui,-apple-system,Segoe UI,sans-serif;transform:translate(-50%,-100%);display:none;white-space:nowrap}
    .dc-chart-tooltip b{display:block;font-size:12px;margin-bottom:7px;color:#fff}
    .dc-chart-tooltip .dc-tip-row{display:flex;justify-content:space-between;gap:18px;line-height:1.65;color:#aaa}
    .dc-chart-tooltip .dc-tip-row strong{color:#fff;font-size:12px}
    .dc-chart-tooltip .dc-current:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:1px;background:#ff5a1f}
    .dc-chart-hover-guide{stroke:#8a8a8a;stroke-width:1;stroke-dasharray:4 4;opacity:.7}
    .dc-chart-hover-dot-current{fill:#ff5a1f;stroke:#111;stroke-width:3}
    .chart-wrap{cursor:crosshair}
    .legend .prev{display:none!important}
    .chart-prev{display:none!important}
  `;
  document.head.appendChild(style);

  function parseDateOnly(s){
    const [y,m,d]=String(s||'').slice(0,10).split('-').map(Number);
    return new Date(y,m-1,d);
  }
  function isoDate(d){
    const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${day}`;
  }
  function prettyDate(s){
    if(!s)return '—';
    const p=String(s).slice(0,10).split('-');
    return p.length===3?`${p[2]}.${p[1]}.${p[0]}`:String(s);
  }
  function daysCount(a,b){
    return Math.round((parseDateOnly(b)-parseDateOnly(a))/86400000)+1;
  }
  function isFullCalendarMonth(a,b){
    const start=parseDateOnly(a),end=parseDateOnly(b);
    if(start.getFullYear()!==end.getFullYear()||start.getMonth()!==end.getMonth()||start.getDate()!==1)return false;
    const last=new Date(end.getFullYear(),end.getMonth()+1,0).getDate();
    return end.getDate()===last;
  }

  // Comparison rules:
  // 1) Full calendar month -> previous calendar month.
  // 2) Multi-day range -> immediately preceding range of the same length.
  // 3) Single day -> same weekday one week earlier (keeps the existing day comparison behavior).
  window.prevPeriod = function(a,b){
    const start=parseDateOnly(a),end=parseDateOnly(b);
    if(isFullCalendarMonth(a,b)){
      const prevStart=new Date(start.getFullYear(),start.getMonth()-1,1);
      const prevEnd=new Date(start.getFullYear(),start.getMonth(),0);
      return [isoDate(prevStart),isoDate(prevEnd)];
    }
    const count=daysCount(a,b);
    if(count<=1){
      const ps=new Date(start),pe=new Date(end);
      ps.setDate(ps.getDate()-7);pe.setDate(pe.getDate()-7);
      return [isoDate(ps),isoDate(pe)];
    }
    const prevEnd=new Date(start);prevEnd.setDate(prevEnd.getDate()-1);
    const prevStart=new Date(prevEnd);prevStart.setDate(prevStart.getDate()-count+1);
    return [isoDate(prevStart),isoDate(prevEnd)];
  };

  function comparisonLabel(cur,prev){
    const from=cur?.period?.from,to=cur?.period?.to,pf=prev?.period?.from,pt=prev?.period?.to;
    if(!from||!to||!pf||!pt)return '';
    const range=pf===pt?prettyDate(pf):`${prettyDate(pf)} — ${prettyDate(pt)}`;
    const count=daysCount(from,to);
    if(isFullCalendarMonth(from,to))return `Сравнение с ${range} — предыдущий месяц`;
    if(count===7)return `Сравнение с ${range} — предыдущие 7 дней`;
    if(count===1)return `Сравнение с ${range} — тот же день недели`;
    return `Сравнение с ${range} — предыдущий период такой же длины`;
  }

  function rub(v){
    try{return `${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;}
    catch(_){return `${Math.round(Number(v||0))} ₸`;}
  }

  const original = window.renderChart;
  if(typeof original!=='function')return;

  window.renderChart = function(cur,prev){
    const c=(cur?.daily||[]),root=document.getElementById('chartWrap');
    if(!root)return original(cur,prev);
    if(!c.length){root.innerHTML='<div class="chart-empty">Нет данных для графика</div>';return;}

    const compare=document.getElementById('comparePeriodLabel');
    const chartCompare=document.getElementById('chartCompareLabel');
    const legendCurrent=document.querySelector('.legend span:not(.prev)');
    if(compare){const text=comparisonLabel(cur,prev);if(text)compare.textContent=text;}
    if(chartCompare)chartCompare.textContent='Показывается только выбранный период';
    if(legendCurrent)legendCurrent.textContent='Выбранный период';

    const W=1000,H=260,L=58,R=18,T=18,B=38,n=c.length;
    const max=Math.max(...c.map(x=>Number(x.revenue||0)),1);
    const x=i=>n===1?W/2:L+i*(W-L-R)/(n-1);
    const y=v=>T+(H-T-B)*(1-Number(v||0)/max);
    const pts=a=>a.map((d,i)=>`${x(i)},${y(d.revenue)}`).join(' ');
    const area=`${x(0)},${H-B} ${pts(c)} ${x(n-1)},${H-B}`;
    let grids='',labels='';
    for(let i=0;i<4;i++){
      const yy=T+i*(H-T-B)/3,val=max*(1-i/3);
      grids+=`<line class="chart-grid" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text class="axis-label" x="0" y="${yy+4}">${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(val)}</text>`;
    }
    const step=Math.max(1,Math.ceil(n/6));
    c.forEach((d,i)=>{if(i%step===0||i===n-1)labels+=`<text class="axis-label" text-anchor="middle" x="${x(i)}" y="${H-10}">${prettyDate(d.date).slice(0,5)}</text>`});
    const dots=n<=10?c.map((d,i)=>`<circle class="chart-dot" cx="${x(i)}" cy="${y(d.revenue)}" r="5"></circle>`).join(''):'';

    root.innerHTML=`<svg viewBox="0 0 ${W} ${H}" aria-label="График выручки"><defs><linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ff5a1f" stop-opacity=".26"/><stop offset="1" stop-color="#ff5a1f" stop-opacity="0"/></linearGradient></defs>${grids}<polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${pts(c)}"/>${dots}${labels}<line id="dcHoverGuide" class="dc-chart-hover-guide" x1="0" x2="0" y1="${T}" y2="${H-B}" visibility="hidden"/><circle id="dcHoverCurrent" class="dc-chart-hover-dot-current" r="6" visibility="hidden"/></svg><div id="dcChartTooltip" class="dc-chart-tooltip"></div>`;

    const svg=root.querySelector('svg'),tip=root.querySelector('#dcChartTooltip'),guide=root.querySelector('#dcHoverGuide'),currentDot=root.querySelector('#dcHoverCurrent');
    if(!svg||!tip)return;

    const show=(clientX)=>{
      const box=svg.getBoundingClientRect();
      if(!box.width)return;
      const svgX=(clientX-box.left)/box.width*W;
      let idx=n===1?0:Math.round((svgX-L)/(W-L-R)*(n-1));
      idx=Math.max(0,Math.min(n-1,idx));
      const d=c[idx],px=x(idx),py=y(d.revenue);
      guide.setAttribute('x1',px);guide.setAttribute('x2',px);guide.setAttribute('visibility','visible');
      currentDot.setAttribute('cx',px);currentDot.setAttribute('cy',py);currentDot.setAttribute('visibility','visible');
      tip.innerHTML=`<b>${prettyDate(d.date)}</b><div class="dc-tip-row"><span class="dc-current">Выручка</span><strong>${rub(d.revenue)}</strong></div>`;
      const leftPct=px/W*100,topPct=py/H*100;
      tip.style.left=`${Math.max(8,Math.min(92,leftPct))}%`;
      tip.style.top=`${Math.max(22,topPct)}%`;
      tip.style.display='block';
    };
    const hide=()=>{tip.style.display='none';guide.setAttribute('visibility','hidden');currentDot.setAttribute('visibility','hidden');};
    svg.addEventListener('mousemove',e=>show(e.clientX));
    svg.addEventListener('mouseenter',e=>show(e.clientX));
    svg.addEventListener('mouseleave',hide);
    svg.addEventListener('touchstart',e=>{if(e.touches?.[0])show(e.touches[0].clientX)},{passive:true});
    svg.addEventListener('touchmove',e=>{if(e.touches?.[0])show(e.touches[0].clientX)},{passive:true});
  };
})();
