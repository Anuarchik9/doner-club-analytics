(() => {
  if (window.__dcCompactLayout) return;
  window.__dcCompactLayout = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Show only five rows before the existing expand buttons. */
    .tablebox.dc-collapsed:not(.dc-searching) tbody tr:nth-child(n+6){display:none!important}
    #stopItems.dc-stop-collapsed .stop-item:nth-child(n+6){display:none!important}

    /* Gross-profit table: five rows first, full list on demand. */
    #econProducts.dc-econ-collapsed tr:nth-child(n+6){display:none!important}
    .dc-econ-more-wrap{display:flex;justify-content:center;margin-top:13px}
    .dc-econ-more{border:1px solid var(--line);background:#101010;color:#ddd;border-radius:999px;padding:9px 18px;font:inherit;font-size:12px;font-weight:800;cursor:pointer}
    .dc-econ-more:hover{border-color:var(--orange);color:#fff;background:var(--soft)}

    /* Categories should read as one compact unit with no huge dead zone in the middle. */
    #categoryList{width:100%!important;max-width:none!important;gap:11px!important}
    #categoryList .cat-row{grid-template-columns:minmax(190px,300px) minmax(260px,1fr) 120px!important;gap:16px!important;justify-content:stretch!important}
    #categoryList .cat-name{min-width:0}
    #categoryList .track{width:100%;margin:0!important}
    #categoryList .cat-share{text-align:right!important}

    /* Branded visual cluster inside Online / Offline cards. */
    .channel-mix-card{padding-right:46%!important}
    .dc-mix-icons{position:absolute;right:22px;top:50%;transform:translateY(-48%);width:40%;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;z-index:2}
    .dc-brand-badge{height:36px;min-width:36px;padding:0 10px;border-radius:12px;border:1px solid #323232;background:linear-gradient(160deg,#111,#090909);display:inline-flex;align-items:center;justify-content:center;gap:6px;color:#f5f5f2;font-size:10px;font-weight:900;letter-spacing:-.01em;box-shadow:0 7px 18px rgba(0,0,0,.22)}
    .dc-brand-badge i{font-style:normal;font-size:15px;line-height:1}
    .dc-brand-badge.yandex i{color:#ff5252}.dc-brand-badge.wolt i{color:#5bc9ff}.dc-brand-badge.glovo i{color:#ffd34d}.dc-brand-badge.choco i{color:#ff9a63}.dc-brand-badge.starter i{color:#a8e063}
    .dc-brand-badge.kaspi i{color:#ff5555}.dc-brand-badge.cash i{color:#8fe1ad}.dc-brand-badge.card i{color:#9ec7ff}.dc-brand-badge.call i{color:#ffb36b}

    /* Offline badges use a strict 2×2 grid so a single badge can never stretch across the card. */
    .dc-offline-card{padding-right:42%!important}
    .dc-offline-card .dc-mix-icons{display:grid!important;grid-template-columns:repeat(2,minmax(105px,1fr));grid-auto-rows:38px;gap:9px;width:min(38%,300px)!important;right:20px!important;left:auto!important;top:50%!important;bottom:auto!important;transform:translateY(-50%)!important;align-content:center;justify-content:stretch!important}
    .dc-offline-card .dc-brand-badge{width:100%!important;min-width:0!important;height:38px!important;padding:0 10px!important;justify-content:flex-start!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

    @media(max-width:900px){
      #categoryList .cat-row{grid-template-columns:minmax(0,1fr) minmax(120px,.8fr) auto!important}
      .channel-mix-card{padding-right:20px!important;padding-bottom:84px!important}
      .dc-mix-icons{left:20px;right:20px;bottom:16px;top:auto;transform:none;width:auto;justify-content:flex-start}
      .dc-offline-card{padding-right:20px!important;padding-bottom:116px!important}
      .dc-offline-card .dc-mix-icons{left:20px!important;right:20px!important;bottom:16px!important;top:auto!important;transform:none!important;width:auto!important;grid-template-columns:repeat(2,minmax(0,1fr))!important}
    }
    @media(max-width:600px){
      #categoryList .cat-row{grid-template-columns:1fr!important}
      #categoryList .cat-share{text-align:left!important}
      .dc-brand-badge{height:31px;padding:0 8px}
      .dc-offline-card .dc-mix-icons{grid-auto-rows:34px!important;gap:7px!important}
      .dc-offline-card .dc-brand-badge{height:34px!important;font-size:9px!important}
    }
  `;
  document.head.appendChild(style);

  const $ = id => document.getElementById(id);

  function forceFiveRowButtons(){
    const tbody = $('tbody');
    const search = $('search');
    const productWrap = $('productTableMore')?.parentElement;
    if (tbody && productWrap) {
      const count = tbody.children.length;
      const searching = !!(search && search.value.trim());
      productWrap.style.setProperty('display', count > 5 && !searching ? 'flex' : 'none', 'important');
    }

    const stopItems = $('stopItems');
    const stopWrap = $('stopListMoreWrap');
    if (stopItems && stopWrap) {
      const count = stopItems.querySelectorAll(':scope > .stop-item').length;
      stopWrap.style.setProperty('display', count > 5 ? 'flex' : 'none', 'important');
    }
  }

  function observeFiveRowLists(){
    const tbody = $('tbody');
    if (tbody && !tbody.dataset.dcFiveWatch) {
      tbody.dataset.dcFiveWatch='1';
      new MutationObserver(()=>setTimeout(forceFiveRowButtons,0)).observe(tbody,{childList:true});
    }
    const stopItems = $('stopItems');
    if (stopItems && !stopItems.dataset.dcFiveWatch) {
      stopItems.dataset.dcFiveWatch='1';
      new MutationObserver(()=>setTimeout(forceFiveRowButtons,0)).observe(stopItems,{childList:true});
    }
    const search = $('search');
    if (search && !search.dataset.dcFiveWatch) {
      search.dataset.dcFiveWatch='1';
      search.addEventListener('input',()=>setTimeout(forceFiveRowButtons,0));
    }
    forceFiveRowButtons();
  }

  function installEconomicsMore(){
    const tbody = $('econProducts');
    if (!tbody || $('econProductsMore')) return false;
    tbody.classList.add('dc-econ-collapsed');
    const tableWrap = tbody.closest('.econ-table-wrap');
    if (!tableWrap) return false;
    const wrap=document.createElement('div');
    wrap.className='dc-econ-more-wrap';
    const button=document.createElement('button');
    button.type='button';button.id='econProductsMore';button.className='dc-econ-more';
    wrap.appendChild(button);tableWrap.insertAdjacentElement('afterend',wrap);

    const sync=()=>{
      const count=tbody.children.length;
      wrap.style.display=count>5?'flex':'none';
      button.textContent=tbody.classList.contains('dc-econ-collapsed')?`Посмотреть все (${count})`:'Свернуть';
    };
    button.addEventListener('click',()=>{
      tbody.classList.toggle('dc-econ-collapsed');
      sync();
      if(tbody.classList.contains('dc-econ-collapsed')) tableWrap.scrollIntoView({behavior:'smooth',block:'start'});
    });
    new MutationObserver(sync).observe(tbody,{childList:true});
    sync();
    return true;
  }

  const onlineBadges = `
    <span class="dc-brand-badge yandex"><i>Я</i>Yandex</span>
    <span class="dc-brand-badge wolt"><i>W</i>Wolt</span>
    <span class="dc-brand-badge glovo"><i>G</i>Glovo</span>
    <span class="dc-brand-badge choco"><i>Ch</i>Choco</span>
    <span class="dc-brand-badge starter"><i>S</i>Starter</span>`;
  const offlineBadges = `
    <span class="dc-brand-badge kaspi"><i>K</i>Kaspi QR</span>
    <span class="dc-brand-badge cash"><i>₸</i>Наличные</span>
    <span class="dc-brand-badge card"><i>▰</i>Карта</span>
    <span class="dc-brand-badge call"><i>☎</i>Call Center</span>`;

  function installMixIcons(){
    const online=$('onlineSales')?.closest('.channel-mix-card');
    const offline=$('offlineSales')?.closest('.channel-mix-card');
    if(!online||!offline)return false;
    online.classList.add('dc-online-card');
    offline.classList.add('dc-offline-card');
    if(!online.querySelector('.dc-mix-icons')){
      const box=document.createElement('div');
      box.className='dc-mix-icons';
      box.innerHTML=onlineBadges;
      online.appendChild(box);
    }
    let offlineBox=offline.querySelector('.dc-mix-icons');
    if(!offlineBox){
      offlineBox=document.createElement('div');
      offlineBox.className='dc-mix-icons dc-offline-icons';
      offlineBox.innerHTML=offlineBadges;
      offline.appendChild(offlineBox);
    } else {
      // Important: do not rewrite innerHTML here. A body-wide MutationObserver watches
      // child-list changes; rewriting an already-correct box would recursively trigger
      // the observer forever and freeze the page.
      offlineBox.classList.add('dc-offline-icons');
    }
    return true;
  }

  function boot(){
    observeFiveRowLists();
    installEconomicsMore();
    installMixIcons();
  }
  boot();
  let bootQueued=false;
  const observer=new MutationObserver(()=>{
    if(bootQueued)return;
    bootQueued=true;
    requestAnimationFrame(()=>{
      bootQueued=false;
      boot();
    });
  });
  observer.observe(document.body,{childList:true,subtree:true});
  setTimeout(boot,900);setTimeout(boot,2200);
})();
