(() => {
  if (window.__dcOnlineOfflineHoverFix) return;
  window.__dcOnlineOfflineHoverFix = true;
  if (!location.pathname.endsWith('/dashboard-v2.html')) return;

  const NS = 'http://www.w3.org/2000/svg';

  const style = document.createElement('style');
  style.textContent = `
    .oo-chart svg{touch-action:pan-y;cursor:crosshair}
    .oo-hover-capture{fill:transparent;pointer-events:all}
    .oo-hover-guide{stroke:#777;stroke-width:1;stroke-dasharray:4 5;opacity:.65;pointer-events:none}
    .oo-hover-focus{fill:#111;stroke-width:3;pointer-events:none}
    .oo-hover-focus.online{stroke:#4d9fff}.oo-hover-focus.offline{stroke:#ff685e}
    @media (hover:none){.oo-chart svg{cursor:default}}
  `;
  document.head.appendChild(style);

  function dispatchHit(hit, sourceEvent) {
    if (!hit) return;
    try {
      hit.dispatchEvent(new PointerEvent('pointerenter', {
        bubbles: false,
        pointerType: sourceEvent?.pointerType || 'mouse',
        clientX: sourceEvent?.clientX || 0,
        clientY: sourceEvent?.clientY || 0,
      }));
    } catch (_) {
      hit.dispatchEvent(new Event('pointerenter'));
    }
  }

  function enhanceSvg(svg) {
    if (!svg || svg.dataset.dcOoHoverFixed === '1') return;
    const hits = Array.from(svg.querySelectorAll('.oo-hit'));
    if (!hits.length) return;
    svg.dataset.dcOoHoverFixed = '1';

    const vb = svg.viewBox?.baseVal;
    const viewW = vb?.width || 960;
    const viewH = vb?.height || 280;
    const left = 66;
    const right = viewW - 20;
    const top = 30;
    const bottom = viewH - 42;

    // Transparent plot-area target: hovering anywhere near a date/month now
    // resolves to the nearest x point, not only to the tiny midpoint circle.
    const capture = document.createElementNS(NS, 'rect');
    capture.setAttribute('class', 'oo-hover-capture');
    capture.setAttribute('x', String(left));
    capture.setAttribute('y', String(top));
    capture.setAttribute('width', String(Math.max(1, right - left)));
    capture.setAttribute('height', String(Math.max(1, bottom - top)));
    svg.insertBefore(capture, svg.firstChild);

    const guide = document.createElementNS(NS, 'line');
    guide.setAttribute('class', 'oo-hover-guide');
    guide.setAttribute('y1', String(top));
    guide.setAttribute('y2', String(bottom));
    guide.style.display = 'none';
    svg.appendChild(guide);

    const focusOnline = document.createElementNS(NS, 'circle');
    focusOnline.setAttribute('class', 'oo-hover-focus online');
    focusOnline.setAttribute('r', '6');
    focusOnline.style.display = 'none';
    svg.appendChild(focusOnline);

    const focusOffline = document.createElementNS(NS, 'circle');
    focusOffline.setAttribute('class', 'oo-hover-focus offline');
    focusOffline.setAttribute('r', '6');
    focusOffline.style.display = 'none';
    svg.appendChild(focusOffline);

    let lastIndex = -1;

    function nearestIndex(clientX) {
      const rect = svg.getBoundingClientRect();
      if (!rect.width) return -1;
      const xInSvg = (clientX - rect.left) / rect.width * viewW;
      let best = 0;
      let bestDistance = Infinity;
      hits.forEach((hit, index) => {
        const cx = Number(hit.getAttribute('cx') || 0);
        const distance = Math.abs(cx - xInSvg);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = index;
        }
      });
      return best;
    }

    function showAt(index, event) {
      if (index < 0 || index >= hits.length) return;
      const hit = hits[index];
      const cx = Number(hit.getAttribute('cx') || 0);
      guide.setAttribute('x1', String(cx));
      guide.setAttribute('x2', String(cx));
      guide.style.display = '';

      // The chart has one blue and one red dot for each data index.
      const onlineDots = svg.querySelectorAll('.oo-dot-online');
      const offlineDots = svg.querySelectorAll('.oo-dot-offline');
      const on = onlineDots[index];
      const off = offlineDots[index];
      if (on) {
        focusOnline.setAttribute('cx', on.getAttribute('cx') || String(cx));
        focusOnline.setAttribute('cy', on.getAttribute('cy') || String(top));
        focusOnline.style.display = '';
      }
      if (off) {
        focusOffline.setAttribute('cx', off.getAttribute('cx') || String(cx));
        focusOffline.setAttribute('cy', off.getAttribute('cy') || String(top));
        focusOffline.style.display = '';
      }

      // Reuse the chart's own tooltip renderer so values/labels stay exactly
      // consistent with the data already rendered by online-offline-trends.js.
      if (lastIndex !== index || event?.type === 'pointerdown' || event?.type === 'click') {
        dispatchHit(hit, event);
        lastIndex = index;
      }
    }

    function move(event) {
      showAt(nearestIndex(event.clientX), event);
    }

    svg.addEventListener('pointermove', move, {passive: true});
    svg.addEventListener('mousemove', move, {passive: true});
    svg.addEventListener('pointerdown', event => showAt(nearestIndex(event.clientX), event), {passive: true});
    svg.addEventListener('click', event => showAt(nearestIndex(event.clientX), event));
    svg.addEventListener('pointerleave', () => {
      lastIndex = -1;
      guide.style.display = 'none';
      focusOnline.style.display = 'none';
      focusOffline.style.display = 'none';
    });
  }

  function scan() {
    document.querySelectorAll('.oo-chart svg').forEach(enhanceSvg);
  }

  const observer = new MutationObserver(() => scan());
  observer.observe(document.documentElement, {childList: true, subtree: true});
  scan();
  setTimeout(scan, 250);
  setTimeout(scan, 900);
})();
