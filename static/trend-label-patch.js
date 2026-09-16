(() => {
  if (window.__dcTrendLabelPatch) return;
  window.__dcTrendLabelPatch = true;

  const moneyCompact = v => new Intl.NumberFormat('ru-RU',{notation:'compact',maximumFractionDigits:1}).format(Number(v||0));
  let requestSeq = 0;

  function addLabels(root, series) {
    if (!root || !series?.length) return;
    const svg = root.querySelector('svg');
    if (!svg) return;

    svg.querySelectorAll('.dc-extra-value').forEach(x => x.remove());

    // Existing trend code intentionally thins labels on long months. On desktop we
    // show every daily value and stagger neighbouring labels to keep them readable.
    if (window.innerWidth <= 900) return;

    const dots = [...svg.querySelectorAll('.dc-trend-dot')];
    dots.forEach((dot, i) => {
      const item = series[i];
      const value = Number(item?.revenue || 0);
      if (!item || value <= 0) return;

      const cx = Number(dot.getAttribute('cx'));
      const cy = Number(dot.getAttribute('cy'));
      if (!Number.isFinite(cx) || !Number.isFinite(cy)) return;

      // Remove the original label at this x-position so the replacement does not duplicate it.
      [...svg.querySelectorAll('.dc-trend-value:not(.dc-extra-value)')].forEach(label => {
        if (Math.abs(Number(label.getAttribute('x')) - cx) < 0.5) label.remove();
      });

      const text = document.createElementNS('http://www.w3.org/2000/svg','text');
      text.setAttribute('class','dc-trend-value dc-extra-value');
      text.setAttribute('x', String(cx));
      const dense = series.length > 20;
      const lift = dense ? (i % 2 === 0 ? 11 : 27) : 11;
      text.setAttribute('y', String(Math.max(13, cy - lift)));
      text.textContent = moneyCompact(value);
      svg.appendChild(text);
    });
  }

  async function refresh() {
    const point = document.getElementById('point')?.value;
    if (!point) return;
    const channel = document.getElementById('salesChannel')?.value || 'all';
    const compareOffset = Number(document.getElementById('trendCompareMonth')?.value || 2);
    const id = ++requestSeq;
    try {
      const r = await fetch(`/trend-analytics?point=${encodeURIComponent(point)}&channel=${encodeURIComponent(channel)}&compareOffset=${compareOffset}`,{headers:{Accept:'application/json'}});
      const j = await r.json();
      if (id !== requestSeq || !r.ok || !j?.success) return;
      // Wait until trend-features.js has drawn its SVGs.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        addLabels(document.getElementById('currentTrendChart'), j.current?.series || []);
        addLabels(document.getElementById('compareTrendChart'), j.comparison?.series || []);
      }));
    } catch (_) {}
  }

  const current = document.getElementById('currentTrendChart');
  const compare = document.getElementById('compareTrendChart');
  const observer = new MutationObserver(() => setTimeout(refresh, 60));
  if (current) observer.observe(current,{childList:true,subtree:true});
  if (compare) observer.observe(compare,{childList:true,subtree:true});

  document.getElementById('trendCompareMonth')?.addEventListener('change',()=>setTimeout(refresh,120));
  document.getElementById('point')?.addEventListener('change',()=>setTimeout(refresh,120));
  document.addEventListener('change',e=>{if(e.target?.id==='salesChannel')setTimeout(refresh,120)});
  setTimeout(refresh,1200);
})();
