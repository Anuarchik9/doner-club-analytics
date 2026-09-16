(() => {
  if (window.__dcDashboardCategoryReadability) return;
  window.__dcDashboardCategoryReadability = true;

  const style = document.createElement('style');
  style.textContent = `
    .wrap{max-width:1680px!important;padding-left:32px!important;padding-right:32px!important}
    body{font-size:15px!important}
    .section{margin-top:34px!important;margin-bottom:14px!important}
    .section h2{font-size:24px!important;line-height:1.15!important}
    .section>.muted{font-size:12px!important}
    .panel{padding:22px!important}
    .panel h3{font-size:18px!important;line-height:1.2!important}
    .muted{font-size:12px!important;line-height:1.5!important}
    .filters{gap:14px!important;padding:18px!important}
    .field label{font-size:11px!important}
    .field select,.field input{height:50px!important;font-size:14px!important;padding:0 14px!important}
    .go{height:50px!important;font-size:14px!important;padding:0 24px!important}
    .preset,.report-mode-btn{font-size:13px!important;padding:8px 13px!important}
    .label{font-size:12px!important}
    .value{font-size:40px!important}
    .sub{font-size:12px!important;line-height:1.5!important}
    #categoryList{gap:14px!important}
    #categoryList .cat-row{grid-template-columns:minmax(220px,330px) minmax(320px,1fr) 135px!important;gap:18px!important;align-items:center!important}
    #categoryList .cat-name strong{font-size:15px!important;line-height:1.3!important}
    #categoryList .cat-name>span:not(.dc-other-breakdown){font-size:11.5px!important;line-height:1.4!important;margin-top:3px!important}
    #categoryList .dc-other-breakdown{font-size:11px!important;line-height:1.45!important;max-width:620px!important;margin-top:5px!important}
    #categoryList .cat-share{font-size:14px!important;font-weight:900!important}
    #categoryList .track{height:8px!important}
    .doner-mix-grid{gap:16px!important}
    .meat-card{padding:18px!important}
    .meat-card small{font-size:12px!important}
    .meat-card strong{font-size:30px!important}
    .meat-card span{font-size:12px!important}
    .size-row b{font-size:14px!important}.size-row span{font-size:12px!important}
    .management-note{font-size:11.5px!important;line-height:1.5!important}
    table{font-size:13px!important}th{font-size:11px!important}td{font-size:13px!important}
    @media(max-width:1200px){.wrap{padding-left:22px!important;padding-right:22px!important}#categoryList .cat-row{grid-template-columns:minmax(190px,280px) minmax(220px,1fr) 120px!important}}
    @media(max-width:900px){.wrap{padding-left:16px!important;padding-right:16px!important}#categoryList .cat-row{grid-template-columns:minmax(0,1fr) minmax(120px,.8fr) auto!important}.section h2{font-size:22px!important}}
    @media(max-width:600px){body{font-size:14px!important}.wrap{padding-left:12px!important;padding-right:12px!important}#categoryList .cat-row{grid-template-columns:1fr!important}.value{font-size:34px!important}}
  `;
  document.head.appendChild(style);

  const nf = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1});
  const money = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0});
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

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
    const otherText=[...root.querySelectorAll(':scope > .cat-row')].find(r=>(r.querySelector('.cat-name strong')?.textContent||'').trim()==='Другие позиции')?.textContent?.toLowerCase()||'';
    const batonLeak=otherText.includes('батон')||otherText.includes('baton');
    if(!wrongNames && !batonLeak) return;

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

  function clarifyDonerBlock(){
    const head=document.getElementById('donerMixHead');
    const note=head?.querySelector('.muted');
    if(note) note.textContent='Только донеры. Батоны и комбо сюда не входят.';
    const sizePanel=document.getElementById('donerMixBlock')?.querySelectorAll('.panel')?.[1];
    const sizeSub=sizePanel?.querySelector('.muted');
    if(sizeSub && !sizeSub.textContent.includes('Батоны')) sizeSub.textContent='Мини · Стандарт · 1.5 · Двойной · только донеры, без батонов';
  }

  function enforce(){
    renderCanonical();
    sanitizeOther();
    clarifyDonerBlock();
  }

  function queue(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(()=>{queued=false;enforce();});
  }

  const root=document.getElementById('categoryList');
  if(root) new MutationObserver(queue).observe(root,{childList:true,subtree:true});
  const bodyObserver=new MutationObserver(()=>{
    if(!document.getElementById('categoryList')) return;
    queue();
  });
  bodyObserver.observe(document.body,{childList:true,subtree:true});

  document.getElementById('go')?.addEventListener('click',()=>{
    [150,500,1000,1800,3200,6000].forEach(ms=>setTimeout(enforce,ms));
  });
  document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(enforce,300));
  document.querySelectorAll('.report-mode-btn').forEach(btn=>btn.addEventListener('click',()=>setTimeout(enforce,300)));
  setTimeout(enforce,700);
  setTimeout(enforce,1800);
})();
