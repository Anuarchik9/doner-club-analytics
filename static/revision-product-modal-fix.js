(() => {
  if (window.__dcRevisionProductModalFix) return;
  window.__dcRevisionProductModalFix = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Closed modal must never block the page. */
    .rev-product-backdrop:not(.show){opacity:0!important;pointer-events:none!important;visibility:hidden!important}
    .rev-product-drawer:not(.show){pointer-events:none!important;visibility:hidden!important}
    .rev-product-backdrop.show{visibility:visible!important;pointer-events:auto!important}
    .rev-product-drawer.show{visibility:visible!important;pointer-events:auto!important}
  `;
  document.head.appendChild(style);

  let closing = false;

  function unlockPage() {
    document.body.classList.remove('rev-product-open');
    if (document.body.style.overflow === 'hidden') document.body.style.removeProperty('overflow');
    if (document.documentElement.style.overflow === 'hidden') document.documentElement.style.removeProperty('overflow');
  }

  function hardClose() {
    if (closing) return;
    closing = true;

    const backdrop = document.getElementById('revProductBackdrop');
    const drawer = document.getElementById('revProductDrawer');

    backdrop?.classList.remove('show');
    drawer?.classList.remove('show');
    drawer?.setAttribute('aria-hidden', 'true');
    unlockPage();

    /* Remove stale modal nodes after the close animation. The original
       drilldown code will recreate them cleanly on the next open. */
    window.setTimeout(() => {
      if (drawer && !drawer.classList.contains('show')) drawer.remove();
      if (backdrop && !backdrop.classList.contains('show')) backdrop.remove();
      unlockPage();
      closing = false;
    }, 260);
  }

  /* Capture phase makes cleanup reliable even if another handler changes
     modal classes later in the bubbling phase. */
  document.addEventListener('click', event => {
    if (event.target.closest('.rev-product-close') || event.target.id === 'revProductBackdrop') {
      hardClose();
    }
  }, true);

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.getElementById('revProductDrawer')) hardClose();
  }, true);

  /* Safety net: if the drawer is closed but a backdrop/body lock remains,
     clear it automatically. */
  const observer = new MutationObserver(() => {
    const drawer = document.getElementById('revProductDrawer');
    const backdrop = document.getElementById('revProductBackdrop');
    if (drawer && !drawer.classList.contains('show')) {
      backdrop?.classList.remove('show');
      unlockPage();
    }
    if (!drawer && backdrop) {
      backdrop.classList.remove('show');
      backdrop.remove();
      unlockPage();
    }
  });
  observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:['class']});
})();
