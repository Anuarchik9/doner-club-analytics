(() => {
  if (window.__dcDashboardCategoryReadabilityV2) return;
  window.__dcDashboardCategoryReadabilityV2 = true;

  const style = document.createElement('style');
  style.textContent = `
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

    #categoryList{gap:15px!important}
    #categoryList .cat-row{grid-template-columns:minmax(240px,350px) minmax(340px,1fr) 145px!important;gap:20px!important;align-items:center!important}
    #categoryList .cat-name strong{font-size:16px!important;line-height:1.3!important}
    #categoryList .cat-name>span{font-size:12.5px!important;line-height:1.45!important;margin-top:4px!important}
    #categoryList .dc-other-audit{display:block;margin-top:6px;color:#c8c8c1;font-size:12px;line-height:1.5;max-width:760px}
    #categoryList .dc-other-preview{display:inline}
    #categoryList .dc-other-more{appearance:none;border:0;background:transparent;color:#ff8b5e;font:inherit;font-weight:850;padding:0 2px;cursor:pointer;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px;pointer-events:auto;position:relative;z-index:3}
    #categoryList .dc-other-more:hover{color:#fff}
    #categoryList .dc-other-more[aria-expanded="true"]{font-size:0!important}
    #categoryList .dc-other-more[aria-expanded="true"]::after{content:'свернуть';font-size:12px;font-weight:850}
    #categoryList .dc-other-full{margin-top:9px;padding:11px 12px;border:1px solid #343434;border-radius:12px;background:#0d0d0d;display:grid;gap:7px;max-height:280px;overflow:auto}
    #categoryList .dc-other-full[hidden]{display:none!important}
    #categoryList .dc-other-item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:start;padding-bottom:6px;border-bottom:1px solid #222}
    #categoryList .dc-other-item:last-child{border-bottom:0;padding-bottom:0}
    #categoryList .dc-other-item b{font-size:11.5px;line-height:1.35;color:#eee;overflow-wrap:anywhere}
    #categoryList .dc-other-item span{font-size:10.5px!important;color:#8e8e88;white-space:nowrap}
    #categoryList .cat-share{font-size:15px!important;font-weight:900!important}
    #categoryList .track{height:9px!important}

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
      #categoryList .dc-other-item{grid-template-columns:1fr}
      #categoryList .dc-other-item span{white-space:normal}
    }
  `;
  document.head.appendChild(style);

  const nf = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1});
  const money = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0});
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rub = v => `${money.format(Number(v||0))} ₸`;
  const setText = (el,text) => { if(el && el.textContent !== text) el.textContent = text; };

  function products(){
    try { return (typeof currentData !== 'undefined' && currentData?.products) || []; }
    catch (_) { return []; }
  }

  function startsProduct(n,word){
    return n===word || n.startsWith(`${word} `) || n.startsWith(`${word}-`) || n.startsWith(`${word}(`);
  }

  function isDrinkName(name){
    const n=String(name||'').trim().toLowerCase();
    return (
      n.includes('pepsi') || n.includes('пепси') ||
      n.includes('айран') || n.includes('вода') || n.includes('сок') ||
      n.includes('чай') || n.includes('кофе') || n.includes('напит') ||
      n.includes('mirinda') || n.includes('миринда') ||
      startsProduct(n,'кинза') || startsProduct(n,'kinza') ||
      startsProduct(n,'ава') || startsProduct(n,'ava') ||
      startsProduct(n,'пиала') || startsProduct(n,'piala') ||
      startsProduct(n,'да-да') || startsProduct(n,'да да') ||
      startsProduct(n,'da-da') || startsProduct(n,'da da') || startsProduct(n,'dada')
    );
  }

  function categoryOf(name){
    const n=String(name||'').trim().toLowerCase();
    if(n.includes('комбо')||n.includes('combo')||n.includes('go!')) return 'Комбо';
    if(n.includes('батон')||n.includes('baton')) return 'Батоны';
    if(n.includes('донер')||n.includes('doner')) return 'Донеры';
    if(isDrinkName(n)) return 'Напитки';
    if(n.includes('фри')||n.includes('наггет')||n.includes('картоф')||n.includes('закуск')||n.includes('стрипс')||n.includes('strip')) return 'Гарниры и закуски';
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

  function otherAuditHtml(list,open=false){
    const sorted=list.slice().sort((a,b)=>Number(b.revenue||0)-Number(a.revenue||0));
    const preview=sorted.slice(0,4);
    const rest=sorted.slice(4);
    const previewText=preview.map(p=>esc(p.name)).join(' · ');
    const restHtml=rest.map(p=>`<div class="dc-other-item"><b>${esc(p.name)}</b><span>${nf.format(Number(p.quantity||0))} ед. · ${rub(p.revenue)}</span></div>`).join('');
    return `<div class="dc-other-audit"><span class="dc-other-preview">Внутри: ${previewText}${rest.length?' · ':''}</span>${rest.length?`<button type="button" class="dc-other-more" aria-expanded="${open?'true':'false'}">ещё ${rest.length}</button><div class="dc-other-full" ${open?'':'hidden'}>${restHtml}</div>`:''}</div>`;
  }

  function numberFromText(text){
    const s=String(text||'').replace(/\s/g,'').replace(/[^0-9,.-]/g,'').replace(',','.');
    return Number(s)||0;
  }

  function domMatches(root,arr){
    const rows=[...root.querySelectorAll(':scope > .cat-row')];
    if(rows.length!==arr.length) return false;
    for(let i=0;i<arr.length;i++){
      const row=rows[i];
      if((row.querySelector('.cat-name strong')?.textContent||'').trim()!==arr[i].name) return false;
      if(Math.round(numberFromText(row.querySelector('.cat-share')?.textContent))!==Math.round(arr[i].revenue)) return false;
      const qtyText=(row.querySelector('.cat-name>span')?.textContent||'').split('ед.')[0];
      if(Math.abs(numberFromText(qtyText)-arr[i].quantity)>0.05) return false;
      if(arr[i].name==='Другие позиции' && !row.querySelector('.dc-other-audit')) return false;
    }
    return true;
  }

  let rendering=false;
  let queued=false;

  function renderCanonical(){
    if(rendering) return;
    const root=document.getElementById('categoryList');
    const arr=expectedGroups();
    if(!root||!arr.length||domMatches(root,arr)) return;

    const wasOpen=root.querySelector('.dc-other-more[aria-expanded="true"]')!==null;
    rendering=true;
    const total=arr.reduce((s,x)=>s+x.revenue,0)||1;
    const max=Math.max(...arr.map(x=>x.revenue),1);
    root.innerHTML=arr.map(x=>{
      const share=x.revenue/total*100;
      const details=x.name==='Другие позиции'?otherAuditHtml(x.products,wasOpen):'';
      return `<div class="cat-row"><div class="cat-name"><strong>${esc(x.name)}</strong><span>${nf.format(x.quantity)} ед. · ${nf.format(share)}% выручки</span>${details}</div><div class="track"><div class="fill" style="width:${Math.max(2,x.revenue/max*100)}%"></div></div><div class="cat-share">${money.format(x.revenue)} ₸</div></div>`;
    }).join('');
    rendering=false;
  }

  function isTrueDoner(name){
    const n=String(name||'').toLowerCase();
    return (n.includes('донер')||n.includes('doner'))
      && !n.includes('батон') && !n.includes('baton')
      && !n.includes('комбо') && !n.includes('combo') && !n.includes('go!');
  }
  function isBaton(name){
    const n=String(name||'').toLowerCase();
    return (n.includes('батон')||n.includes('baton'))
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
    const all=products();
    const meatItems=all.filter(p=>isTrueDoner(p.name)||isBaton(p.name));
    const sizeItems=all.filter(p=>isTrueDoner(p.name));
    if(!meatItems.length && !sizeItems.length) return;

    const meats={chicken:{revenue:0,qty:0},beef:{revenue:0,qty:0},assorti:{revenue:0,qty:0},other:{revenue:0,qty:0}};
    const sizes={mini:{label:'Мини',revenue:0,qty:0},standard:{label:'Стандарт',revenue:0,qty:0},onehalf:{label:'1.5',revenue:0,qty:0},double:{label:'Двойной',revenue:0,qty:0}};

    for(const p of meatItems){
      const revenue=Number(p.revenue||0),qty=Number(p.quantity||0),m=meatOf(p.name);
      meats[m].revenue+=revenue;meats[m].qty+=qty;
    }
    for(const p of sizeItems){
      const revenue=Number(p.revenue||0),qty=Number(p.quantity||0),s=sizeOf(p.name);
      sizes[s].revenue+=revenue;sizes[s].qty+=qty;
    }

    const recognized=meats.chicken.revenue+meats.beef.revenue+meats.assorti.revenue;
    const share=v=>recognized?v/recognized*100:0;
    const targets=[['chicken','chickenRevenue','chickenMeta'],['beef','beefRevenue','beefMeta'],['assorti','assortiRevenue','assortiMeta']];
    for(const [key,valueId,metaId] of targets){
      const bucket=meats[key];
      setText(document.getElementById(valueId),rub(bucket.revenue));
      setText(document.getElementById(metaId),`${nf.format(bucket.qty)} шт. · ${nf.format(share(bucket.revenue))}%`);
    }

    const note=document.getElementById('meatNote');
    const batonCount=meatItems.filter(p=>isBaton(p.name)).reduce((s,p)=>s+Number(p.quantity||0),0);
    const baseNote=`Мясо считается по донерам и батонам. Комбо исключены. Батонов в выбранном периоде: ${nf.format(batonCount)} шт.`;
    setText(note,meats.other.revenue>0
      ? `${baseNote} Не удалось определить мясо у части позиций: ${rub(meats.other.revenue)}.`
      : baseNote);

    const sizeList=document.getElementById('donerSizeList');
    if(sizeList){
      const max=Math.max(...Object.values(sizes).map(x=>x.revenue),1);
      const html=Object.values(sizes).map(x=>`<div class="size-row"><b>${x.label}</b><div class="size-track"><div class="size-fill" style="width:${Math.max(x.revenue?3:0,x.revenue/max*100)}%"></div></div><span>${nf.format(x.qty)} шт. · ${rub(x.revenue)}</span></div>`).join('');
      if(sizeList.innerHTML!==html) sizeList.innerHTML=html;
    }
  }

  function clarifyDonerBlock(){
    const head=document.getElementById('donerMixHead');
    setText(head?.querySelector('h2'),'Мясо и размеры');
    setText(head?.querySelector('.muted'),'Мясо — донеры + батоны; размеры — только донеры. Комбо не учитываются.');

    const panels=document.getElementById('donerMixBlock')?.querySelectorAll('.panel');
    const meatPanel=panels?.[0];
    const sizePanel=panels?.[1];
    setText(meatPanel?.querySelector('h3'),'Мясо: донеры + батоны');
    setText(meatPanel?.querySelector('.muted'),'Курица / говядина / ассорти по донерам и батонам');
    setText(sizePanel?.querySelector('h3'),'Размеры донеров');
    setText(sizePanel?.querySelector('.muted'),'Мини · Стандарт · 1.5 · Двойной · батоны сюда не входят');
  }

  function enforce(){
    renderCanonical();
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

  document.addEventListener('click',event=>{
    const button=event.target.closest?.('.dc-other-more');
    if(!button) return;
    const root=document.getElementById('categoryList');
    if(!root?.contains(button)) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const full=button.parentElement?.querySelector('.dc-other-full');
    if(!full) return;
    const opening=full.hidden;
    full.hidden=!opening;
    button.setAttribute('aria-expanded',String(opening));
  },true);

  const donerRoot=document.getElementById('donerMixBlock');
  if(donerRoot) new MutationObserver(queue).observe(donerRoot,{childList:true,subtree:true});

  document.getElementById('go')?.addEventListener('click',()=>{
    [80,250,600,1100,1800,3000,5000].forEach(ms=>setTimeout(enforce,ms));
  });
  document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(enforce,250));
  document.querySelectorAll('.report-mode-btn').forEach(btn=>btn.addEventListener('click',()=>setTimeout(enforce,250)));
  [100,350,800,1500,2600].forEach(ms=>setTimeout(enforce,ms));
})();
