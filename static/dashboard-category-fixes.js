(() => {
  if (window.__dcDashboardCategoryFixes) return;
  window.__dcDashboardCategoryFixes = true;

  const style = document.createElement('style');
  style.textContent = `
    #categoryList .dc-other-more{
      pointer-events:auto!important;
      position:relative!important;
      z-index:3!important;
      cursor:pointer!important;
    }
    #categoryList .dc-other-full{
      margin-top:9px;
      padding:11px 12px;
      border:1px solid #343434;
      border-radius:12px;
      background:#0d0d0d;
      display:grid;
      gap:7px;
      max-height:280px;
      overflow:auto;
    }
    #categoryList .dc-other-full[hidden]{display:none!important}
    #categoryList .dc-other-item{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:12px;
      align-items:start;
      padding-bottom:6px;
      border-bottom:1px solid #222;
    }
    #categoryList .dc-other-item:last-child{border-bottom:0;padding-bottom:0}
    #categoryList .dc-other-item b{font-size:11.5px;line-height:1.35;color:#eee;overflow-wrap:anywhere}
    #categoryList .dc-other-item span{font-size:10.5px!important;color:#8e8e88;white-space:nowrap}
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

  function groups(){
    const out={};
    for(const p of products()){
      const k=categoryOf(p.name);
      if(!out[k]) out[k]={name:k,revenue:0,quantity:0,products:[]};
      out[k].revenue+=Number(p.revenue||0);
      out[k].quantity+=Number(p.quantity||0);
      out[k].products.push(p);
    }
    return Object.values(out).sort((a,b)=>b.revenue-a.revenue);
  }

  function otherHtml(list){
    const sorted=list.slice().sort((a,b)=>Number(b.revenue||0)-Number(a.revenue||0));
    const preview=sorted.slice(0,4);
    const rest=sorted.slice(4);
    const previewText=preview.map(p=>esc(p.name)).join(' · ');
    const restHtml=rest.map(p=>`<div class="dc-other-item"><b>${esc(p.name)}</b><span>${nf.format(Number(p.quantity||0))} ед. · ${rub(p.revenue)}</span></div>`).join('');
    return `<div class="dc-other-audit"><span class="dc-other-preview">Внутри: ${previewText}${rest.length?' · ':''}</span>${rest.length?`<button type="button" class="dc-other-more" aria-expanded="false">ещё ${rest.length}</button><div class="dc-other-full" hidden>${restHtml}</div>`:''}</div>`;
  }

  function numberFromText(text){
    const s=String(text||'').replace(/\s/g,'').replace(/[^0-9,.-]/g,'').replace(',','.');
    return Number(s)||0;
  }

  let rendering=false;
  let queued=false;

  function needsRender(root,arr){
    const rows=[...root.querySelectorAll(':scope > .cat-row')];
    if(rows.length!==arr.length) return true;
    for(let i=0;i<arr.length;i++){
      const row=rows[i];
      const name=(row.querySelector('.cat-name strong')?.textContent||'').trim();
      if(name!==arr[i].name) return true;
      const revenue=numberFromText(row.querySelector('.cat-share')?.textContent);
      if(Math.round(revenue)!==Math.round(arr[i].revenue)) return true;
      const qtyText=(row.querySelector('.cat-name>span')?.textContent||'').split('ед.')[0];
      const qty=numberFromText(qtyText);
      if(Math.abs(qty-arr[i].quantity)>0.05) return true;
    }
    return false;
  }

  function render(){
    if(rendering) return;
    const root=document.getElementById('categoryList');
    const arr=groups();
    if(!root||!arr.length||!needsRender(root,arr)) return;

    rendering=true;
    const total=arr.reduce((s,x)=>s+x.revenue,0)||1;
    const max=Math.max(...arr.map(x=>x.revenue),1);
    root.innerHTML=arr.map(x=>{
      const share=x.revenue/total*100;
      const details=x.name==='Другие позиции'?otherHtml(x.products):'';
      return `<div class="cat-row"><div class="cat-name"><strong>${esc(x.name)}</strong><span>${nf.format(x.quantity)} ед. · ${nf.format(share)}% выручки</span>${details}</div><div class="track"><div class="fill" style="width:${Math.max(2,x.revenue/max*100)}%"></div></div><div class="cat-share">${money.format(x.revenue)} ₸</div></div>`;
    }).join('');
    rendering=false;
  }

  function queue(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(()=>{
      queued=false;
      render();
    });
  }

  function connectObserver(){
    const root=document.getElementById('categoryList');
    if(!root || root.dataset.dcCategoryFixObserver==='1') return;
    root.dataset.dcCategoryFixObserver='1';
    new MutationObserver(queue).observe(root,{childList:true,subtree:true});
  }

  // Capture-phase delegation makes the expander work even when the category rows
  // are rebuilt dynamically by other dashboard scripts.
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
    const count=full.querySelectorAll('.dc-other-item').length;
    button.textContent=opening?'свернуть':`ещё ${count}`;
  },true);

  function enforce(){
    connectObserver();
    render();
  }

  document.getElementById('go')?.addEventListener('click',()=>{
    [80,250,600,1100,1800,3000,5000].forEach(ms=>setTimeout(enforce,ms));
  });
  document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(enforce,250));
  document.querySelectorAll('.report-mode-btn').forEach(btn=>btn.addEventListener('click',()=>setTimeout(enforce,250)));
  [100,350,800,1500,2600].forEach(ms=>setTimeout(enforce,ms));
})();
