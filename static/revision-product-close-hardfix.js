(() => {
  if (window.__dcRevisionProductCloseHardfixV2) return;
  window.__dcRevisionProductCloseHardfixV2 = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-product-close{position:relative!important;z-index:99999!important;pointer-events:auto!important;cursor:pointer!important}
    .rev-product-drawer.dc-closing,.rev-product-backdrop.dc-closing{pointer-events:none!important}
    .rev-product-drawer.dc-closing{opacity:0!important;visibility:hidden!important}
    .rev-product-backdrop.dc-closing{opacity:0!important;visibility:hidden!important}
  `;
  document.head.appendChild(style);

  let suppressUntil = 0;
  let closeTimer = null;

  function unlockPage() {
    const body = document.body;
    const html = document.documentElement;
    body.classList.remove('rev-product-open');
    for (const prop of ['overflow','overflow-y','position','touch-action','pointer-events']) body.style.removeProperty(prop);
    for (const prop of ['overflow','overflow-y','position','touch-action','pointer-events']) html.style.removeProperty(prop);
  }

  function cleanupNodes() {
    document.querySelectorAll('#revProductDrawer,.rev-product-drawer').forEach(el => el.remove());
    document.querySelectorAll('#revProductBackdrop,.rev-product-backdrop').forEach(el => el.remove());
    unlockPage();
  }

  function forceClose() {
    suppressUntil = Date.now() + 700;
    clearTimeout(closeTimer);

    const drawers = [...document.querySelectorAll('#revProductDrawer,.rev-product-drawer')];
    const backdrops = [...document.querySelectorAll('#revProductBackdrop,.rev-product-backdrop')];

    drawers.forEach(el => {
      el.classList.add('dc-closing');
      el.classList.remove('show');
      el.setAttribute('aria-hidden','true');
    });
    backdrops.forEach(el => {
      el.classList.add('dc-closing');
      el.classList.remove('show');
    });

    unlockPage();
    document.activeElement?.blur?.();

    // Keep the old modal nodes alive for a moment. Removing them during pointerdown
    // can make the browser retarget the following click to the product row underneath
    // and instantly reopen the modal. We suppress that click, then remove everything.
    closeTimer = setTimeout(cleanupNodes, 360);
  }

  window.__dcCloseRevisionProduct = forceClose;

  function isCloseTarget(target) {
    return target instanceof Element && (
      !!target.closest('.rev-product-close') ||
      target.id === 'revProductBackdrop' ||
      !!target.closest('#revProductBackdrop')
    );
  }

  // Catch the close before the older delegated handlers.
  window.addEventListener('pointerdown', event => {
    if (!isCloseTarget(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    forceClose();
  }, true);

  // Suppress the synthetic click that follows pointerdown so it cannot hit the
  // product row behind the disappearing modal and reopen it.
  window.addEventListener('click', event => {
    if (Date.now() < suppressUntil) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (!isCloseTarget(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    forceClose();
  }, true);

  window.addEventListener('pointerup', event => {
    if (Date.now() < suppressUntil) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  window.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const drawer = document.getElementById('revProductDrawer') || document.querySelector('.rev-product-drawer.show');
    if (!drawer) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    forceClose();
  }, true);

  function wireCloseButton() {
    document.querySelectorAll('.rev-product-close').forEach(button => {
      button.style.setProperty('pointer-events','auto','important');
      button.style.setProperty('z-index','99999','important');
      button.setAttribute('type','button');
      button.setAttribute('aria-label','Закрыть разбор позиции');
    });
  }

  const observer = new MutationObserver(() => {
    wireCloseButton();
    const drawer = document.getElementById('revProductDrawer');
    const backdrop = document.getElementById('revProductBackdrop');
    if (!drawer && backdrop) {
      backdrop.remove();
      unlockPage();
    }
    if (drawer && !drawer.classList.contains('show') && !drawer.classList.contains('dc-closing')) {
      backdrop?.classList.remove('show');
      backdrop?.classList.add('dc-closing');
      unlockPage();
    }
  });
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});

  // Recovery for a stale modal left by an older cached script.
  if (document.querySelector('.rev-product-drawer:not(.show)')) cleanupNodes();
  wireCloseButton();
})();
