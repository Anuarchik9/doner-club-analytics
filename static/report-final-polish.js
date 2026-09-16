(() => {
  if (window.__dcReportFinalPolish) return;
  window.__dcReportFinalPolish = true;

  const nf=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1});
  const money=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0});
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function categoryOf(name){
    const n=String(name||'').toLowerCase();
    if(n.includes('комбо')||n.includes('combo')||n.includes('go!'))return'Комбо';
    if(n.includes('донер')||n.includes('doner'))return'Донеры';
    if(n.includes('батон')||n.includes('baton'))return'Батоны';
    if(n.includes('pepsi')||n.includes('айран')||n.includes('вода')||n.includes('сок')||n.includes('чай')||n.includes('кофе')||n.includes('напит'))return'Напитки';
    if(n.includes('фри')||n.includes('наггет')||n.includes('картоф')||n.includes('закуск'))return'Гарниры и закуски';
    if(n.includes('соус')||n.includes('халап')||n.includes('сыр')||n.includes('добав'))return'Соусы и добавки';
    return'Другие позиции';
  }

  function currentProducts(){
    try{return (typeof currentData!=='undefined'&&currentData?.products)||[]}catch(_){return[]}
  }

  function renderCategories(){
    const root=document.getElementById('categoryList');
    const products=currentProducts();
    if(!root||!products.length)return;
    const groups={};
    for(const p of products){
      const k=categoryOf(p.name);
      if(!groups[k])groups[k]={name:k,revenue:0,quantity:0,products:[]};
      groups[k].revenue+=Number(p.revenue||0);
      groups[k].quantity+=Number(p.quantity||0);
      groups[k].products.push(p);
    }
    const arr=Object.values(groups).sort((a,b)=>b.revenue-a.revenue);
    const total=arr.reduce((s,x)=>s+x.revenue,0)||1;
    const max=Math.max(...arr.map(x=>x.revenue),1);
    root.innerHTML=arr.map(x=>{
      const share=x.revenue/total*100;
      const details=x.name==='Другие позиции'
        ? `<span class="dc-other-breakdown">Внутри: ${x.products.sort((a,b)=>Number(b.revenue||0)-Number(a.revenue||0)).slice(0,4).map(p=>esc(p.name)).join(' · ')}${x.products.length>4?` · ещё ${x.products.length-4}`:''}</span>`
        : '';
      return `<div class="cat-row"><div class="cat-name"><strong>${esc(x.name)}</strong><span>${nf.format(x.quantity)} ед. · ${nf.format(share)}% выручки</span>${details}</div><div class="track"><div class="fill" style="width:${Math.max(2,x.revenue/max*100)}%"></div></div><div class="cat-share">${money.format(x.revenue)} ₸</div></div>`;
    }).join('');
  }

  function findSection(title){
    for(const h of document.querySelectorAll('.section h2')){
      if((h.textContent||'').trim()===title){
        const head=h.closest('.section');
        return {head,body:head?.nextElementSibling};
      }
    }
    return null;
  }

  function parse(s){const [y,m,d]=String(s||'').split('-').map(Number);return new Date(y,m-1,d)}
  function syncMonthlyDynamic(){
    const a=document.getElementById('from')?.value,b=document.getElementById('to')?.value;
    const block=findSection('Динамика выручки');
    if(!a||!b||!block)return;
    const s=parse(a),e=parse(b);
    const isMonthReport=s.getDate()===1&&s.getFullYear()===e.getFullYear()&&s.getMonth()===e.getMonth();
    if(block.head)block.head.style.display=isMonthReport?'none':'';
    if(block.body)block.body.style.display=isMonthReport?'none':'';
  }

  function refresh(){
    renderCategories();
    syncMonthlyDynamic();
  }

  document.getElementById('go')?.addEventListener('click',()=>{
    setTimeout(refresh,500);
    setTimeout(refresh,1600);
    setTimeout(refresh,3000);
  });
  document.getElementById('from')?.addEventListener('change',()=>setTimeout(syncMonthlyDynamic,150));
  document.getElementById('to')?.addEventListener('change',()=>setTimeout(syncMonthlyDynamic,80));
  document.querySelector('.presets')?.addEventListener('click',()=>setTimeout(syncMonthlyDynamic,80));
  setTimeout(refresh,1400);
})();
