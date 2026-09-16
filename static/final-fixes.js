(() => {
  if (window.__dcFinalFixes) return;
  window.__dcFinalFixes = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Keep the exact supplied square logo crisp and fully inside the rounded header tile. */
    .logo{width:48px!important;height:48px!important;border-radius:15px!important;overflow:hidden!important;background:transparent!important;padding:0!important;flex:0 0 48px!important}
    .logo img{display:block!important;width:100%!important;height:100%!important;object-fit:cover!important;border-radius:15px!important}

    /* Offline badges were wrapping outside the card. Give them a stable 2×2 block. */
    .channel-mix-card{min-width:0!important}
    .dc-mix-icons.dc-mix-icons-offline{display:grid!important;grid-template-columns:repeat(2,minmax(105px,1fr))!important;gap:8px!important;width:min(42%,300px)!important;right:22px!important;top:50%!important;bottom:auto!important;left:auto!important;transform:translateY(-50%)!important;align-items:center!important}
    .dc-mix-icons.dc-mix-icons-offline .dc-brand-badge{width:100%!important;min-width:0!important;justify-content:flex-start!important;overflow:hidden!important;white-space:nowrap!important}
    .dc-mix-icons.dc-mix-icons-online{max-width:320px!important}

    @media(max-width:900px){
      .dc-mix-icons.dc-mix-icons-offline{display:flex!important;width:auto!important;max-width:none!important;left:20px!important;right:20px!important;bottom:16px!important;top:auto!important;transform:none!important;flex-wrap:wrap!important}
      .dc-mix-icons.dc-mix-icons-offline .dc-brand-badge{width:auto!important}
    }
  `;
  document.head.appendChild(style);

  const logo = document.querySelector('.logo');
  if (logo) logo.innerHTML = '<img src="/static/brand-logo.svg?v=20260916-5" alt="Doner Club">';

  function tagMixGroups(){
    const online=document.getElementById('onlineSales')?.closest('.channel-mix-card')?.querySelector('.dc-mix-icons');
    const offline=document.getElementById('offlineSales')?.closest('.channel-mix-card')?.querySelector('.dc-mix-icons');
    if(online) online.classList.add('dc-mix-icons-online');
    if(offline) offline.classList.add('dc-mix-icons-offline');
  }
  tagMixGroups();
  new MutationObserver(tagMixGroups).observe(document.body,{childList:true,subtree:true});
})();
