(() => {
  if (window.__dcRevisionProductCloseHardfix) return;
  window.__dcRevisionProductCloseHardfix = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-product-close{
      position:relative!important;
      z-index:99999!important;
      pointer-events:auto!important;
      cursor:pointer!important;
    }
    .rev-product-drawer[data-force-closed="1"],
    .rev-product-backdrop[data-force-closed="1"]{
      display:none!important;
      visibility:hidden!important;
      pointer-events:none!important;
      opacity:0!important;
    }
  `;
  document.head.appendChild(style);

  function unlockPage() {
    const body = document.body;
    const html = document.documentElement;

    body.classList.remove('rev-product-open');
    body.style.removeProperty('overflow');
    body.style.removeProperty('overflow-y');
    body.style.removeProperty('position');
    body.style.removeProperty('touch-action');
    body.style.removeProperty('pointer-events');

    html.style.removeProperty('overflow');
    html.style.removeProperty('overflow-y');
    html.style.removeProperty('position');
    html.style.removeProperty('touch-action');
    html.style.removeProperty('pointer-events');
  }

  function forceClose() {
    const drawers = [...document.querySelectorAll('#revProductDrawer, .rev-product-drawer')];
    const backdrops = [...document.querySelectorAll('#revProductBackdrop, .rev-product-backdrop')];

    drawers.forEach(drawer => {
      drawer.dataset.forceClosed = '1';
      drawer.classList.remove('show');
      drawer.setAttribute('aria-hidden', 'true');
      drawer.style.setProperty('display', 'none', 'important');
      drawer.style.setProperty('pointer-events', 'none', 'important');
    });

    backdrops.forEach(backdrop => {
      backdrop.dataset.forceClosed = '1';
      backdrop.classList.remove('show');
      backdrop.style.setProperty('display', 'none', 'important');
      backdrop.style.setProperty('pointer-events', 'none', 'important');
    });

    unlockPage();

    // Remove stale modal nodes completely so the next open starts cleanly.
    requestAnimationFrame(() => {
      drawers.forEach(drawer => drawer.remove());
      backdrops.forEach(backdrop => backdrop.remove());
      unlockPage();
    });
  }

  window.__dcCloseRevisionProduct = forceClose;

  function isCloseTarget(target) {
    if (!(target instanceof Element)) return false;
    return Boolean(target.closest('.rev-product-close')) || target.id === 'revProductBackdrop' || Boolean(target.closest('#revProductBackdrop'));
  }

  // pointerdown closes before any bubbling handlers can interfere.
  window.addEventListener('pointerdown', event => {
    if (!isCloseTarget(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    forceClose();
  }, true);

  // click is a fallback for browsers/input methods that do not emit pointerdown.
  window.addEventListener('click', event => {
    if (!isCloseTarget(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    forceClose();
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
      button.style.setProperty('pointer-events', 'auto', 'important');
      button.style.setProperty('z-index', '99999', 'important');
      button.setAttribute('type', 'button');
      button.onclick = event => {
        event?.preventDefault?.();
        event?.stopPropagation?.();
        forceClose();
        return false;
      };
    });
  }

  const observer = new MutationObserver(() => {
    wireCloseButton();

    // A backdrop without a visible drawer is always stale and must not block the page.
    const drawer = document.getElementById('revProductDrawer');
    const backdrop = document.getElementById('revProductBackdrop');
    if (backdrop && (!drawer || !drawer.classList.contains('show'))) {
      backdrop.classList.remove('show');
      backdrop.style.setProperty('pointer-events', 'none', 'important');
      unlockPage();
    }
  });
  observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:['class']});

  wireCloseButton();
})();
