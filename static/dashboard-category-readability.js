(() => {
  if (window.__dcDashboardCategoryReadability) return;
  window.__dcDashboardCategoryReadability = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Use the available desktop width instead of leaving large dead margins. */
    .wrap{max-width:1760px!important;padding-left:28px!important;padding-right:28px!important}
    body{font-size:16px!important}
    .hero h1{font-size:58px!important;line-height:1.04!important}
    .hero #period{font-size:14px!important}
    .section{margin-top:36px!important;margin-bottom:15px!important}
    .section h2{font-size:26px!important;line-height:1.15!important}
    .section>.muted{font-size:13px!important}
    .panel{padding:24px!important}
    .panel h3{font-size:19px!important;line-height:1.2!important}
    .muted{font-size:13px!important;line-height:1.55!important}
    .filters{gap:15px!important;padding:19px!important}
    .field label{font-size:11.5px!important}
    .field select,.field input{height:52px!important;font-size:15px!important;padding:0 15px!important}
    .go{height:52px!important;font-size:15px!important;padding:0 25px!important}
    .preset,.report-mode-btn{font-size:13.5px!important;padding:9px 14px!important}
    .label{font-size:12.5px!important}
    .value{font-size:42px!important}
    .sub{font-size:12.5px!important;line-height:1.55!important}

    /* Sales categories: larger text and a wider name column. */
    #categoryList{gap:15px!important}
    #categoryList .cat-row{grid-template-columns:minmax(240px,350px) minmax(340px,1fr) 145px!important;gap:20px!important;align-items:center!important}
    #categoryList .cat-name strong{font-size:16px!important;line-height:1.3!important}
    #categoryList .cat-name>span:not(.dc-other-breakdown){font-size:12.5px!important;line-height:1.45!important;margin-top:4px!important}
    #categoryList .dc-other-breakdown{font-size:12px!important;line-height:1.5!important;max-width:680px!important;margin-top:6px!important}
    #categoryList .cat-share{font-size:15px!important;font-weight:900!important}
    #categoryList .track{height:9px!important}

    /* Doner mix and the rest of analytics should be readable from a normal desktop distance. */
    .doner-mix-grid{gap:18px!important}
    .meat-card{padding:19px!important}
    .meat-card small{font-size:12.5px!important}
    .meat-card strong{font-size:31px!important}
    .meat-card span{font-size:12.5px!important}
    .size-row b{font-size:14.5px!important}.size-row span{font-size:12.5px!important}
    .management-note{font-size:12px!important;line-height:1.55!important}
    table{font-size:13.5px!important}th{font-size:11.5px!important}td{font-size:13.5px!important}

    @media(max-width:1200px){
      .wrap{padding-left:22px!important;padding-right:22px!important}
      #categoryList .cat-row{grid-template-columns:minmax(200px,290px) minmax(220px,1fr) 125px!important}
      .hero h1{font-size:52px!important}
    }
    @media(max-width:900px){
      body{font-size:15px!important}.wrap{padding-left:16px!important;padding-right:16px!important}
      #categoryList .cat-row{grid-template-columns:minmax(0,1fr) minmax(120px,.8fr) auto!important}
      .section h2{font-size:23px!important}.hero h1{font-size:44px!important}
    }
    @media(max-width:600px){
      body{font-size:14px!important}.wrap{padding-left:12px!important;padding-right:12px!important}
      #categoryList .cat-row{grid-template-columns:1fr!important}.value{font-size:35px!important}.hero h1{font-size:38px!important}
    }
  `;
  document.head.appendChild(style);

  const nf = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1});
  const money = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0});
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rub = v => `${money.format(Number(v||0))} ₸`;

  function products(){
    try { return (typeof currentData !== 'undefined' && currentData?.products) || []; }
    catch (_) { return []; }
  }

  function categoryOf(name){
    const n=String(name||'').toLowerCase();
    if(n.includes('комбо')||n.includes('combo')||n.includes('go!')) return 'Комбо';
    if(n.includes('батон')||n.includes('baton')) return 'Батоны';
    if(n.includes('донер')||n.includes('doner')) return 'Донеры';
    if(n.includes('pepsi')||n.includes('айран')||n.includes('вода')||n.includes('сок')||n.includes('чай')||n.includes('кофе')||n.includes('напит')) return 'Напитки';
    if(n.includes('фри')||n.includes('наггет')||n.includes('картоф')||n.includes('закуск')) return 'Гарниры и закуски';
    if(n.includes('соус')||n.includes('халап')||n.includes('сыр')||n.includes('добав')) return 'Соусы и добавки';
    return 'Другие позиции';
  }

  function expectedGroups(){
    const groups={};
    for(const p of products()){
      const k=categoryOf(p.name);
      if(!groups[k]) groups[k]={name:k,revenue:0,quantity:0,products:[]};
      groups[k].revenue+=Number(p.revenue||0);
      groups[k].quantity+=Number(p.quantity||0);
      groups[k].products.push(p);
    }
    return Object.values(groups).sort((a,b)=>b.revenue-a.revenue);
  }

  let rendering=false;
  let queued=false;
  function renderCanonical(){
    if(rendering) return;
    const root=document.getElementById('categoryList');
    const arr=expectedGroups();
    if(!root||!arr.length) return;

    const wanted=arr.map(x=>x.name);
    const current=[...root.querySelectorAll(':scope > .cat-row .cat-name strong')].map(x=>(x.textContent||'').trim());
    const wrongNames=current.length!==wanted.length || current.some((x,i)=>x!==wanted[i]);
    const otherText=[...root.querySelectorAll(':scope > .cat-row')]
      .find(r=>(r.querySelector('.cat-name strong')?.textContent||'').trim()==='Другие позиции')?.textContent?.toLowerCase()||'';
    const batonLeaked=otherText.includes('батон')||otherText.includes('baton');
    if(!wrongNames && !batonLeaked) return;

    rendering=true;
    const total=arr.reduce((s,x)=>s+x.revenue,0)||1;
    const max=Math.max(...arr.map(x=>x.revenue),1);
    root.innerHTML=arr.map(x=>{
      const share=x.revenue/total*100;
      const details=x.name==='Другие позиции'
        ? `<span class="dc-other-breakdown">Внутри: ${x.products.slice().sort((a,b)=>Number(b.revenue||0)-Number(a.revenue||0)).slice(0,4).map(p=>esc(p.name)).join(' · ')}${x.products.length>4?` · ещё ${x.products.length-4}`:''}</span>`
        : '';
      return `<div class="cat-row"><div class="cat-name"><strong>${esc(x.name)}</strong><span>${nf.format(x.quantity)} ед. · ${nf.format(share)}% выручки</span>${details}</div><div class="track"><div class="fill" style="width:${Math.max(2,x.revenue/max*100)}%"></div></div><div class="cat-share">${money.format(x.revenue)} ₸</div></div>`;
    }).join('');
    rendering=false;
  }

  function sanitizeOther(){
    const root=document.getElementById('categoryList');
    if(!root) return;
    const row=[...root.querySelectorAll(':scope > .cat-row')].find(r=>(r.querySelector('.cat-name strong')?.textContent||'').trim()==='Другие позиции');
    if(!row) return;
    const otherProducts=products().filter(p=>categoryOf(p.name)==='Другие позиции').sort((a,b)=>Number(b.revenue||0)-Number(a.revenue||0));
    const names=otherProducts.slice(0,4).map(p=>String(p.name||'').trim()).filter(Boolean);
    const more=Math.max(0,otherProducts.length-names.length);
    const text=`Внутри: ${names.join(' · ')}${more?` · ещё ${more}`:''}`;
    let detail=row.querySelector('.dc-other-breakdown');
    if(!detail){detail=document.createElement('span');detail.className='dc-other-breakdown';row.querySelector('.cat-name')?.appendChild(detail)}
    if(detail && detail.textContent!==text) detail.textContent=text;
  }

  function isTrueDoner(name){
    const n=String(name||'').toLowerCase();
    return (n.includes('донер')||n.includes('doner'))
      && !n.includes('батон') && !n.includes('baton')
      && !n.includes('комбо') && !n.includes('combo') && !n.includes('go!');
  }
  function meatOf(name){
    const n=String(name||'').toLowerCase();
    if(n.includes('ассорти')||n.includes('assorti')||n.includes('mixed')) return 'assorti';
    if(n.includes('кур')||n.includes('chicken')) return 'chicken';
    if(n.includes('гов')||n.includes('beef')) return 'beef';
    return 'other';
  }
  function sizeOf(name){
    const n=String(name||'').toLowerCase();
    if(n.includes('мини')||n.includes('mini')) return 'mini';
    if(n.includes('1.5')||n.includes('1,5')||n.includes('полутор')) return 'onehalf';
    if(n.includes('двойн')||n.includes('double')) return 'double';
    return 'standard';
  }

  function renderDonerMix(){
    const items=products().filter(p=>isTrueDoner(p.name));
    if(!items.length) return;
    const meats={chicken:{revenue:0,qty:0},beef:{revenue:0,qty:0},assorti:{revenue:0,qty:0},other:{revenue:0,qty:0}};
    const sizes={mini:{label:'Мини',revenue:0,qty:0},standard:{label:'Стандарт',revenue:0,qty:0},onehalf:{label:'1.5',revenue:0,qty:0},double:{label:'Двойной',revenue:0,qty:0}};
    for(const p of items){
      const revenue=Number(p.revenue||0),qty=Number(p.quantity||0);
      const m=meatOf(p.name),s=sizeOf(p.name);
      meats[m].revenue+=revenue;meats[m].qty+=qty;sizes[s].revenue+=revenue;sizes[s].qty+=qty;
    }
    const recognized=meats.chicken.revenue+meats.beef.revenue+meats.assorti.revenue;
    const share=v=>recognized?v/recognized*100:0;
    const targets=[['chicken','chickenRevenue','chickenMeta'],['beef','beefRevenue','beefMeta'],['assorti','assortiRevenue','assortiMeta']];
    for(const [key,valueId,metaId] of targets){
      const value=document.getElementById(valueId),meta=document.getElementById(metaId),bucket=meats[key];
      if(value)value.textContent=rub(bucket.revenue);
      if(meta)meta.textContent=`${nf.format(bucket.qty)} шт. · ${nf.format(share(bucket.revenue))}%`;
    }
    const note=document.getElementById('meatNote');
    if(note) note.textContent=meats.other.revenue>0
      ? `В блоке только донеры. Батоны и комбо исключены. Не удалось определить мясо у части донеров: ${rub(meats.other.revenue)}.`
      : 'В блоке только донеры. Батоны и комбо исключены.';
    const sizeList=document.getElementById('donerSizeList');
    if(sizeList){
      const max=Math.max(...Object.values(sizes).map(x=>x.revenue),1);
      sizeList.innerHTML=Object.values(sizes).map(x=>`<div class="size-row"><b>${x.label}</b><div class="size-track"><div class="size-fill" style="width:${Math.max(x.revenue?3:0,x.revenue/max*100)}%"></div></div><span>${nf.format(x.qty)} шт. · ${rub(x.revenue)}</span></div>`).join('');
    }
  }

  function clarifyDonerBlock(){
    const head=document.getElementById('donerMixHead');
    const note=head?.querySelector('.muted');
    if(note) note.textContent='Только донеры. Батоны и комбо сюда не входят.';
    const sizePanel=document.getElementById('donerMixBlock')?.querySelectorAll('.panel')?.[1];
    const sizeSub=sizePanel?.querySelector('.muted');
    if(sizeSub) sizeSub.textContent='Мини · Стандарт · 1.5 · Двойной · только донеры, без батонов';
  }

  function enforce(){
    renderCanonical();
    sanitizeOther();
    renderDonerMix();
    clarifyDonerBlock();
  }

  function queue(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(()=>{queued=false;enforce();});
  }

  const categoryRoot=document.getElementById('categoryList');
  if(categoryRoot) new MutationObserver(queue).observe(categoryRoot,{childList:true,subtree:true});
  const donerRoot=document.getElementById('donerMixBlock');
  if(donerRoot) new MutationObserver(queue).observe(donerRoot,{childList:true,subtree:true});

  document.getElementById('go')?.addEventListener('click',()=>{
    [120,350,700,1200,2000,3500,6000].forEach(ms=>setTimeout(enforce,ms));
  });
  document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(enforce,300));
  document.querySelectorAll('.report-mode-btn').forEach(btn=>btn.addEventListener('click',()=>setTimeout(enforce,300)));
  [400,900,1600,2600].forEach(ms=>setTimeout(enforce,ms));
})();
