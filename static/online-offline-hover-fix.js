(() => {
  if (window.__dcOnlineOfflineHoverFixV2) return;
  window.__dcOnlineOfflineHoverFixV2 = true;
  if (!location.pathname.endsWith('/dashboard-v2.html')) return;

  const NS = 'http://www.w3.org/2000/svg';

  const style = document.createElement('style');
  style.textContent = `
    .oo-chart svg{touch-action:pan-y}
    .oo-hit{pointer-events:none!important}
    .oo-direct-hit{fill:transparent;pointer-events:all;cursor:pointer}
    .oo-hover-guide{stroke:#777;stroke-width:1;stroke-dasharray:4 5;opacity:.65;pointer-events:none}
    .oo-hover-focus{fill:#111;stroke-width:3;pointer-events:none}
    .oo-hover-focus.online{stroke:#4d9fff}.oo-hover-focus.offline{stroke:#ff685e}
    @media (hover:none){.oo-direct-hit{cursor:default}}
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
    if (!svg || svg.dataset.dcOoHoverFixedV2 === '1') return;

    const hits = Array.from(svg.querySelectorAll('.oo-hit'));
    const onlineDots = Array.from(svg.querySelectorAll('.oo-dot-online'));
    const offlineDots = Array.from(svg.querySelectorAll('.oo-dot-offline'));
    if (!hits.length || !onlineDots.length || !offlineDots.length) return;

    svg.dataset.dcOoHoverFixedV2 = '1';

    const vb = svg.viewBox?.baseVal;
    const viewH = vb?.height || 280;
    const top = 30;
    const bottom = viewH - 42;

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

    const root = svg.closest('.oo-chart');

    function placeTooltip(index) {
      const tooltip = root?.querySelector('.oo-tooltip');
      const on = onlineDots[index];
      const off = offlineDots[index];
      if (!tooltip || !root || (!on && !off)) return;

      const rootRect = root.getBoundingClientRect();
      const onRect = on?.getBoundingClientRect();
      const offRect = off?.getBoundingClientRect();
      const source = onRect || offRect;
      if (!source || !rootRect.width) return;

      const centerX = source.left + source.width / 2 - rootRect.left;
      const topY = Math.min(
        onRect ? onRect.top + onRect.height / 2 : Infinity,
        offRect ? offRect.top + offRect.height / 2 : Infinity,
      ) - rootRect.top;

      tooltip.style.left = `${Math.max(80, Math.min(rootRect.width - 80, centerX))}px`;
      tooltip.style.top = `${Math.max(48, topY)}px`;
    }

    function show(index, event) {
      const hit = hits[index];
      const on = onlineDots[index];
      const off = offlineDots[index];
      if (!hit || (!on && !off)) return;

      const cx = Number((on || off).getAttribute('cx') || 0);
      guide.setAttribute('x1', String(cx));
      guide.setAttribute('x2', String(cx));
      guide.style.display = '';

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

      dispatchHit(hit, event);
      placeTooltip(index);
    }

    function hide() {
      guide.style.display = 'none';
      focusOnline.style.display = 'none';
      focusOffline.style.display = 'none';
      const tooltip = root?.querySelector('.oo-tooltip');
      if (tooltip) tooltip.style.display = 'none';
    }

    // Create the hover areas exactly on top of the visible blue/red points.
    // This avoids the old behaviour where the whole plot width selected the
    // nearest date and, on wide charts, the pointer had to travel far past a dot.
    hits.forEach((_, index) => {
      [onlineDots[index], offlineDots[index]].forEach(dot => {
        if (!dot) return;
        const target = document.createElementNS(NS, 'circle');
        target.setAttribute('class', 'oo-direct-hit');
        target.setAttribute('cx', dot.getAttribute('cx') || '0');
        target.setAttribute('cy', dot.getAttribute('cy') || '0');
        target.setAttribute('r', '13');
        target.dataset.index = String(index);
        svg.appendChild(target);

        const activate = event => show(index, event);
        target.addEventListener('pointerenter', activate);
        target.addEventListener('pointermove', activate, {passive:true});
        target.addEventListener('pointerdown', activate, {passive:true});
        target.addEventListener('click', activate);
        target.addEventListener('pointerleave', hide);
      });
    });

    svg.addEventListener('pointerleave', hide);
  }

  function scan() {
    document.querySelectorAll('.oo-chart svg').forEach(enhanceSvg);
  }

  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, {childList:true, subtree:true});
  scan();
  setTimeout(scan, 200);
  setTimeout(scan, 800);
})();
