(() => {
  if (window.__dcDashboardPolish) return;
  window.__dcDashboardPolish = true;

  const style=document.createElement('style');
  style.textContent=`
    .tablebox th:nth-child(2),.tablebox td:nth-child(2){display:none!important}
    .tablebox table{width:min(100%,920px)!important;min-width:620px!important;margin:0!important;table-layout:auto}
    .tablebox th:first-child,.tablebox td:first-child{width:auto!important;max-width:560px}
    .tablebox th:nth-child(3),.tablebox td:nth-child(3){width:125px!important;min-width:125px!important}
    .tablebox th:nth-child(4),.tablebox td:nth-child(4){width:155px!important;min-width:155px!important}
    .tablebox td:first-child{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .logo{width:48px!important;height:48px!important;border-radius:15px!important;background:transparent!important;overflow:hidden!important;padding:0!important;display:block!important;line-height:0!important;flex:0 0 48px}
    .logo svg{display:block;width:100%;height:100%;border-radius:15px}
    .meat-cards.dc-three{grid-template-columns:repeat(3,1fr)!important}
    @media(max-width:700px){.meat-cards.dc-three{grid-template-columns:1fr!important}.tablebox table{min-width:570px!important}.tablebox th:nth-child(3),.tablebox td:nth-child(3){width:105px!important;min-width:105px!important}.tablebox th:nth-child(4),.tablebox td:nth-child(4){width:135px!important;min-width:135px!important}}
  `;
  document.head.appendChild(style);

  // Keep the brand mark inline so it cannot break because of an external image/static-cache issue.
  const logo=document.querySelector('.logo');
  if(logo) logo.innerHTML=`<svg viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Doner Club shaurma house"><rect width="160" height="160" rx="30" fill="#f75b24"/><g fill="#fff" font-family="Arial Black,Inter,Arial,sans-serif" font-weight="900"><text x="18" y="69" font-size="39" letter-spacing="-2.7">DONER</text><text x="18" y="112" font-size="43" letter-spacing="-2.7">CLUB</text><text x="101" y="88" font-size="10" letter-spacing="-.4">shaurma</text><text x="101" y="99" font-size="10" letter-spacing="-.4">house</text></g></svg>`;

  const search=document.getElementById('search');
  if(search) search.placeholder='Поиск по названию';

  const meatCards=document.querySelector('.meat-cards');
  if(meatCards){
    const panel=meatCards.closest('.panel');
    const title=panel?.querySelector('h3');
    if(title) title.textContent='Курица / говядина / ассорти';
  }
  if(meatCards&&!document.getElementById('assortiRevenue')){
    meatCards.classList.add('dc-three');
    const card=document.createElement('div');
    card.className='meat-card';
    card.innerHTML='<small>Ассорти</small><strong id="assortiRevenue">—</strong><span id="assortiMeta">—</span>';
    meatCards.appendChild(card);
  }

  const fmt=v=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(Number(v||0));
  const rub=v=>`${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;
  const isDoner=name=>{const n=String(name||'').toLowerCase();return (n.includes('донер')||n.includes('doner'))&&!n.includes('комбо')&&!n.includes('combo')};
  const meatOf=name=>{
    const n=String(name||'').toLowerCase();
    if(n.includes('ассорти')||n.includes('assorti')||n.includes('mixed'))return'assorti';
    if(n.includes('кур')||n.includes('chicken'))return'chicken';
    if(n.includes('гов')||n.includes('beef'))return'beef';
    return'other';
  };

  let busy=false;
  function rerender(){
    if(busy)return;
    let data=null;
    try{if(typeof currentData!=='undefined')data=currentData}catch(_){return}
    const items=(data?.products||[]).filter(x=>isDoner(x.name));
    if(!items.length)return;
    busy=true;
    try{
      const buckets={chicken:{revenue:0,qty:0},beef:{revenue:0,qty:0},assorti:{revenue:0,qty:0},other:{revenue:0,qty:0}};
      for(const p of items){const key=meatOf(p.name),r=Number(p.revenue||0),q=Number(p.quantity||0);buckets[key].revenue+=r;buckets[key].qty+=q}
      const recognized=buckets.chicken.revenue+buckets.beef.revenue+buckets.assorti.revenue;
      const share=v=>recognized?v/recognized*100:0;
      const map=[['chicken','chickenRevenue','chickenMeta'],['beef','beefRevenue','beefMeta'],['assorti','assortiRevenue','assortiMeta']];
      for(const [key,valueId,metaId] of map){
        const value=document.getElementById(valueId),meta=document.getElementById(metaId),b=buckets[key];
        if(value)value.textContent=rub(b.revenue);
        if(meta)meta.textContent=`${fmt(b.qty)} шт. · ${fmt(share(b.revenue))}%`;
      }
      const note=document.getElementById('meatNote');
      if(note)note.textContent=buckets.other.revenue>0?`Не удалось определить мясо у части донеров: ${rub(buckets.other.revenue)}.`:'Доля рассчитана среди куриных, говяжьих и донеров ассорти.';
    }finally{busy=false}
  }

  const chickenMeta=document.getElementById('chickenMeta');
  if(chickenMeta){
    const observer=new MutationObserver(()=>setTimeout(rerender,0));
    observer.observe(chickenMeta,{childList:true,characterData:true,subtree:true});
  }
  document.getElementById('go')?.addEventListener('click',()=>{setTimeout(rerender,800);setTimeout(rerender,2500)});
  setTimeout(rerender,1200);
})();
