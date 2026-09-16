(() => {
  const style = document.createElement('style');
  style.textContent = `
    .dc-chart-tooltip{position:absolute;z-index:8;pointer-events:none;min-width:168px;padding:10px 12px;border:1px solid #3a3a3a;border-radius:12px;background:rgba(10,10,10,.96);box-shadow:0 12px 34px rgba(0,0,0,.45);color:#f7f7f2;font:12px Inter,system-ui,-apple-system,Segoe UI,sans-serif;transform:translate(-50%,-100%);display:none;white-space:nowrap}
    .dc-chart-tooltip b{display:block;font-size:12px;margin-bottom:7px;color:#fff}
    .dc-chart-tooltip .dc-tip-row{display:flex;justify-content:space-between;gap:18px;line-height:1.65;color:#aaa}
    .dc-chart-tooltip .dc-tip-row strong{color:#fff;font-size:12px}
    .dc-chart-tooltip .dc-current:before,.dc-chart-tooltip .dc-previous:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:1px}
    .dc-chart-tooltip .dc-current:before{background:#ff5a1f}.dc-chart-tooltip .dc-previous:before{background:#626262}
    .dc-chart-hover-guide{stroke:#8a8a8a;stroke-width:1;stroke-dasharray:4 4;opacity:.7}
    .dc-chart-hover-dot-current{fill:#ff5a1f;stroke:#111;stroke-width:3}
    .dc-chart-hover-dot-prev{fill:#737373;stroke:#111;stroke-width:3}
    .chart-wrap{cursor:crosshair}
  `;
  document.head.appendChild(style);

  const original = window.renderChart;
  if (typeof original !== 'function') return;

  function rub(v){
    try { return `${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`; }
    catch (_) { return `${Math.round(Number(v||0))} ₸`; }
  }
  function prettyDate(s){
    if (!s) return '—';
    const p=String(s).slice(0,10).split('-');
    return p.length===3?`${p[2]}.${p[1]}.${p[0]}`:String(s);
  }

  window.renderChart = function(cur, prev){
    const c=(cur?.daily||[]), p=(prev?.daily||[]), root=document.getElementById('chartWrap');
    if(!root) return original(cur,prev);
    if(!c.length){root.innerHTML='<div class="chart-empty">Нет данных для графика</div>';return;}

    const W=1000,H=260,L=58,R=18,T=18,B=38,n=c.length;
    const all=[...c.map(x=>Number(x.revenue||0)),...p.map(x=>Number(x.revenue||0))];
    const max=Math.max(...all,1);
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

    root.innerHTML=`<svg viewBox="0 0 ${W} ${H}" aria-label="График выручки"><defs><linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ff5a1f" stop-opacity=".26"/><stop offset="1" stop-color="#ff5a1f" stop-opacity="0"/></linearGradient></defs>${grids}<polygon class="chart-area" points="${area}"/>${p.length?`<polyline class="chart-prev" points="${pts(p.slice(0,n))}"/>`:''}<polyline class="chart-line" points="${pts(c)}"/>${dots}${labels}<line id="dcHoverGuide" class="dc-chart-hover-guide" x1="0" x2="0" y1="${T}" y2="${H-B}" visibility="hidden"/><circle id="dcHoverCurrent" class="dc-chart-hover-dot-current" r="6" visibility="hidden"/><circle id="dcHoverPrev" class="dc-chart-hover-dot-prev" r="5" visibility="hidden"/></svg><div id="dcChartTooltip" class="dc-chart-tooltip"></div>`;

    const svg=root.querySelector('svg'), tip=root.querySelector('#dcChartTooltip'), guide=root.querySelector('#dcHoverGuide'), currentDot=root.querySelector('#dcHoverCurrent'), prevDot=root.querySelector('#dcHoverPrev');
    if(!svg||!tip) return;

    const show=(clientX)=>{
      const box=svg.getBoundingClientRect();
      if(!box.width) return;
      const svgX=(clientX-box.left)/box.width*W;
      let idx=n===1?0:Math.round((svgX-L)/(W-L-R)*(n-1));
      idx=Math.max(0,Math.min(n-1,idx));
      const d=c[idx], pd=p[idx];
      const px=x(idx), py=y(d.revenue);
      guide.setAttribute('x1',px);guide.setAttribute('x2',px);guide.setAttribute('visibility','visible');
      currentDot.setAttribute('cx',px);currentDot.setAttribute('cy',py);currentDot.setAttribute('visibility','visible');
      if(pd){prevDot.setAttribute('cx',px);prevDot.setAttribute('cy',y(pd.revenue));prevDot.setAttribute('visibility','visible')}else prevDot.setAttribute('visibility','hidden');
      tip.innerHTML=`<b>${prettyDate(d.date)}</b><div class="dc-tip-row"><span class="dc-current">Текущий</span><strong>${rub(d.revenue)}</strong></div>${pd?`<div class="dc-tip-row"><span class="dc-previous">Неделей ранее</span><strong>${rub(pd.revenue)}</strong></div>`:''}`;
      const leftPct=px/W*100, topPct=py/H*100;
      tip.style.left=`${Math.max(8,Math.min(92,leftPct))}%`;
      tip.style.top=`${Math.max(22,topPct)}%`;
      tip.style.display='block';
    };
    const hide=()=>{tip.style.display='none';guide.setAttribute('visibility','hidden');currentDot.setAttribute('visibility','hidden');prevDot.setAttribute('visibility','hidden')};
    svg.addEventListener('mousemove',e=>show(e.clientX));
    svg.addEventListener('mouseenter',e=>show(e.clientX));
    svg.addEventListener('mouseleave',hide);
    svg.addEventListener('touchstart',e=>{if(e.touches?.[0])show(e.touches[0].clientX)},{passive:true});
    svg.addEventListener('touchmove',e=>{if(e.touches?.[0])show(e.touches[0].clientX)},{passive:true});
  };
})();
