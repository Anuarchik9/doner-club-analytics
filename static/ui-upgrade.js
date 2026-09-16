(() => {
  if (window.__dcUiUpgrade) return;
  window.__dcUiUpgrade = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Give the large location title enough breathing room for descenders such as «р». */
    .hero h1{line-height:1.06!important;margin:9px 0 14px!important;padding-bottom:2px}
    .hero #period{display:block;line-height:1.45}

    /* Product list is useful, but should not make every report several screens long. */
    .tablebox.dc-collapsed:not(.dc-searching) tbody tr:nth-child(n+13){display:none}
    .dc-table-more-wrap{display:flex;justify-content:center;margin-top:12px}
    .dc-table-more{border:1px solid var(--line);background:#101010;color:#ddd;border-radius:999px;padding:9px 18px;font:inherit;font-size:12px;font-weight:800;cursor:pointer}
    .dc-table-more:hover{border-color:var(--orange);color:#fff;background:var(--soft)}

    /* Apply the same compact/show-all behaviour to the stop list. */
    #stopItems.dc-stop-collapsed .stop-item:nth-child(n+13){display:none}
    .dc-stop-more-wrap{display:flex;justify-content:center;margin-top:13px}
    .dc-stop-more{border:1px solid var(--line);background:#101010;color:#ddd;border-radius:999px;padding:9px 18px;font:inherit;font-size:12px;font-weight:800;cursor:pointer}
    .dc-stop-more:hover{border-color:var(--orange);color:#fff;background:var(--soft)}

    /* Values on desktop charts were too small to read at a glance. */
    @media(min-width:901px){
      .dc-trend-value{font-size:13px!important;font-weight:900!important}
      .dc-trend-axis,.axis-label{font-size:11.5px!important}
      .dc-line-chart{height:315px!important}
      .hour-line-chart{height:270px!important}
    }
    @media(max-width:600px){
      .hero h1{margin-bottom:12px!important}
    }
  `;
  document.head.appendChild(style);

  function pointsFrom(polyline){
    const raw = (polyline.getAttribute('points') || '').trim();
    if (!raw) return [];
    return raw.split(/\s+/).map(pair => {
      const [x,y] = pair.split(',').map(Number);
      return Number.isFinite(x) && Number.isFinite(y) ? {x,y} : null;
    }).filter(Boolean);
  }

  function smoothPath(points){
    if (points.length < 2) return '';
    if (points.length === 2) return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;
    let d = `M ${points[0].x} ${points[0].y}`;
    const tension = .72;
    for (let i=0;i<points.length-1;i++){
      const p0 = points[i-1] || points[i];
      const p1 = points[i];
      const p2 = points[i+1];
      const p3 = points[i+2] || p2;
      let c1x = p1.x + (p2.x-p0.x)/6*tension;
      let c1y = p1.y + (p2.y-p0.y)/6*tension;
      let c2x = p2.x - (p3.x-p1.x)/6*tension;
      let c2y = p2.y - (p3.y-p1.y)/6*tension;
      const low = Math.min(p1.y,p2.y), high = Math.max(p1.y,p2.y);
      c1y = Math.max(low,Math.min(high,c1y));
      c2y = Math.max(low,Math.min(high,c2y));
      d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
    }
    return d;
  }

  function softenPolyline(polyline){
    if (!polyline || polyline.dataset.dcSmoothed === '1') return;
    const pts = pointsFrom(polyline);
    if (pts.length < 3) return;
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    for (const attr of Array.from(polyline.attributes)){
      if (attr.name !== 'points') path.setAttribute(attr.name, attr.value);
    }
    path.setAttribute('d', smoothPath(pts));
    path.setAttribute('fill','none');
    path.dataset.dcSmoothed = '1';
    polyline.replaceWith(path);
  }

  function softenCharts(root=document){
    root.querySelectorAll?.('polyline.dc-trend-line, polyline.chart-line, polyline.chart-prev').forEach(softenPolyline);
  }

  const chartObserver = new MutationObserver(mutations => {
    for (const m of mutations){
      for (const node of m.addedNodes){
        if (node.nodeType === 1) softenCharts(node);
      }
    }
  });
  chartObserver.observe(document.body,{childList:true,subtree:true});
  softenCharts();

  const tablebox = document.querySelector('.tablebox');
  const tbody = document.getElementById('tbody');
  const search = document.getElementById('search');
  if (tablebox && tbody && !document.getElementById('productTableMore')){
    tablebox.classList.add('dc-collapsed');
    const wrap = document.createElement('div');
    wrap.className = 'dc-table-more-wrap';
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'productTableMore';
    button.className = 'dc-table-more';
    button.textContent = 'Посмотреть все';
    wrap.appendChild(button);
    tablebox.insertAdjacentElement('afterend',wrap);

    const sync = () => {
      const count = tbody.children.length;
      const searching = !!(search && search.value.trim());
      tablebox.classList.toggle('dc-searching',searching);
      wrap.style.display = count > 12 && !searching ? 'flex' : 'none';
      button.textContent = tablebox.classList.contains('dc-collapsed') ? `Посмотреть все (${count})` : 'Свернуть';
    };

    button.addEventListener('click',()=>{
      tablebox.classList.toggle('dc-collapsed');
      sync();
      if (tablebox.classList.contains('dc-collapsed')) {
        tablebox.scrollIntoView({behavior:'smooth',block:'start'});
      }
    });
    search?.addEventListener('input',sync);
    new MutationObserver(sync).observe(tbody,{childList:true});
    sync();
  }

  function installStopMore(){
    const stopItems = document.getElementById('stopItems');
    if (!stopItems || document.getElementById('stopListMore')) return false;
    stopItems.classList.add('dc-stop-collapsed');
    const wrap = document.createElement('div');
    wrap.className = 'dc-stop-more-wrap';
    wrap.id = 'stopListMoreWrap';
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'stopListMore';
    button.className = 'dc-stop-more';
    wrap.appendChild(button);
    stopItems.insertAdjacentElement('afterend',wrap);

    const sync = () => {
      const count = stopItems.querySelectorAll(':scope > .stop-item').length;
      wrap.style.display = count > 12 ? 'flex' : 'none';
      button.textContent = stopItems.classList.contains('dc-stop-collapsed') ? `Посмотреть все (${count})` : 'Свернуть';
    };
    button.addEventListener('click',()=>{
      stopItems.classList.toggle('dc-stop-collapsed');
      sync();
      if (stopItems.classList.contains('dc-stop-collapsed')) {
        stopItems.closest('.panel')?.scrollIntoView({behavior:'smooth',block:'start'});
      }
    });
    new MutationObserver(sync).observe(stopItems,{childList:true});
    sync();
    return true;
  }

  if(!installStopMore()){
    const stopWatcher = new MutationObserver(()=>{
      if(installStopMore()) stopWatcher.disconnect();
    });
    stopWatcher.observe(document.body,{childList:true,subtree:true});
  }
})();
