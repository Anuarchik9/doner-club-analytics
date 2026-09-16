(() => {
  if (window.__dcRevisionProductDrilldown) return;
  window.__dcRevisionProductDrilldown = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-product-click{cursor:pointer;transition:background .15s ease,border-color .15s ease}.rev-product-click:hover{background:rgba(255,90,31,.055)!important}.rev-product-click b:first-child{text-decoration:underline;text-decoration-color:rgba(255,130,78,.28);text-underline-offset:3px}.rev-product-click:hover b:first-child{text-decoration-color:#ff8455}
    .rev-product-backdrop{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.72);backdrop-filter:blur(5px);opacity:0;pointer-events:none;transition:opacity .18s ease}.rev-product-backdrop.show{opacity:1;pointer-events:auto}
    .rev-product-drawer{position:fixed;z-index:91;right:0;top:0;width:min(720px,94vw);height:100dvh;background:#0b0b0b;border-left:1px solid #303030;box-shadow:-28px 0 80px rgba(0,0,0,.55);transform:translateX(102%);transition:transform .22s ease;overflow:auto}.rev-product-drawer.show{transform:translateX(0)}
    .rev-product-head{position:sticky;top:0;z-index:2;display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:22px 24px 18px;background:rgba(11,11,11,.94);backdrop-filter:blur(16px);border-bottom:1px solid #252525}.rev-product-head small{display:block;color:#ff7d49;font-size:9px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px}.rev-product-head h2{margin:0;font-size:25px;line-height:1.1;letter-spacing:-.03em}.rev-product-close{width:36px;height:36px;flex:0 0 36px;border-radius:11px;border:1px solid #333;background:#121212;color:#ddd;font-size:20px;cursor:pointer}.rev-product-close:hover{border-color:#5b443a;color:#fff}
    .rev-product-body{padding:20px 24px 32px}.rev-product-summary{padding:14px 16px;border:1px solid #433127;border-radius:15px;background:#15100d;color:#d6cbc3;font-size:11px;line-height:1.55}.rev-product-summary b{color:#fff}.rev-product-summary strong{color:#ff9870}
    .rev-product-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:11px}.rev-product-kpi{min-width:0;padding:13px;border:1px solid #292929;border-radius:14px;background:#111}.rev-product-kpi span{display:block;color:#70706c;font-size:8px;text-transform:uppercase;letter-spacing:.06em}.rev-product-kpi b{display:block;margin-top:6px;font-size:17px;line-height:1.15;overflow-wrap:anywhere}.rev-product-kpi small{display:block;color:#777;font-size:8px;margin-top:4px;line-height:1.4}.rev-product-kpi.neg b{color:#ff8585}.rev-product-kpi.pos b{color:#8be0b2}.rev-product-kpi.warn b{color:#ffad72}
    .rev-product-section{margin-top:20px}.rev-product-section-head{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin-bottom:9px}.rev-product-section h3{margin:0;font-size:14px}.rev-product-section-head span,.rev-product-section>p{color:#777;font-size:9px;line-height:1.45;margin:4px 0 0}
    .rev-product-table-wrap{overflow-x:auto;border:1px solid #292929;border-radius:15px}.rev-product-table{width:100%;min-width:610px;border-collapse:collapse;background:#0e0e0e}.rev-product-table th{padding:9px 10px;color:#65655f;font-size:8px;text-transform:uppercase;letter-spacing:.05em;text-align:left;border-bottom:1px solid #272727}.rev-product-table td{padding:10px;border-bottom:1px solid #202020;font-size:10px}.rev-product-table tr:last-child td{border-bottom:0}.rev-product-table .r{text-align:right}.rev-product-table .neg{color:#ff8b8b;font-weight:800}.rev-product-table .pos{color:#8be0b2;font-weight:800}.rev-product-table .muted{color:#777}
    .rev-product-candidates{display:grid;gap:7px;margin-top:9px}.rev-product-candidate{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:10px 11px;border:1px solid #292929;border-radius:12px;background:#101010}.rev-product-candidate b{font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rev-product-candidate small{display:block;color:#777;font-size:8px;margin-top:3px;line-height:1.4}.rev-product-candidate strong{font-size:10px;color:#8be0b2;white-space:nowrap}.rev-product-warning{margin-top:9px;padding:10px 11px;border:1px solid #443a2d;border-radius:12px;background:#15120d;color:#a99884;font-size:9px;line-height:1.5}
    .rev-product-actions{display:grid;gap:8px;margin-top:9px}.rev-product-action{display:grid;grid-template-columns:24px minmax(0,1fr);gap:10px;padding:11px 12px;border:1px solid #292929;border-radius:13px;background:#101010}.rev-product-action i{display:grid;place-items:center;width:24px;height:24px;border-radius:8px;background:rgba(255,90,31,.12);color:#ff8d60;font-style:normal;font-size:9px;font-weight:900}.rev-product-action b{display:block;font-size:10px}.rev-product-action span{display:block;color:#81817b;font-size:9px;line-height:1.5;margin-top:3px}
    body.rev-product-open{overflow:hidden}
    @media(max-width:760px){.rev-product-body{padding:16px 14px 26px}.rev-product-head{padding:18px 14px 14px}.rev-product-kpis{grid-template-columns:1fr 1fr}.rev-product-head h2{font-size:21px}}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const qty = value => Number(value || 0).toLocaleString('ru-RU',{maximumFractionDigits:3});
  const signedMoney = value => { const n=Number(value||0); return `${n>0?'+':n<0?'−':''}${Math.round(Math.abs(n)).toLocaleString('ru-RU')} ₸`; };
  const signedQty = value => { const n=Number(value||0); return `${n>0?'+':n<0?'−':''}${Math.abs(n).toLocaleString('ru-RU',{maximumFractionDigits:3})}`; };
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => { const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(value||'')); return m?`${m[3]}.${m[2]}.${m[1]}`:String(value||''); };

  let latestData = null;

  function ensureDrawer(){
    let backdrop=document.getElementById('revProductBackdrop');
    let drawer=document.getElementById('revProductDrawer');
    if(!backdrop){backdrop=document.createElement('div');backdrop.id='revProductBackdrop';backdrop.className='rev-product-backdrop';document.body.appendChild(backdrop);}
    if(!drawer){drawer=document.createElement('aside');drawer.id='revProductDrawer';drawer.className='rev-product-drawer';drawer.setAttribute('aria-hidden','true');document.body.appendChild(drawer);}
    return {backdrop,drawer};
  }

  function collectProductsForRevision(revision){
    const map=new Map();
    for(const doc of revision?.documents||[]){
      for(const line of doc.products||[]){
        const name=String(line.name||'Позиция без названия').trim();
        const item=map.get(name)||{name,unit:String(line.unit||''),quantityDelta:0,shortage:0,surplus:0,net:0,costWeighted:0,costQty:0,documents:0};
        const delta=Number(line.quantityDelta||0), shortage=Number(line.shortage||0), surplus=Number(line.surplus||0), net=Number(line.net ?? (surplus-shortage)), cost=Number(line.unitCost||0);
        item.quantityDelta+=delta; item.shortage+=shortage; item.surplus+=surplus; item.net+=net; item.documents+=1;
        if(cost>0){const w=Math.max(Math.abs(delta),.001);item.costWeighted+=cost*w;item.costQty+=w;}
        if(!item.unit && line.unit)item.unit=String(line.unit);
        map.set(name,item);
      }
    }
    return [...map.values()].map(x=>({...x,unitCost:x.costQty?x.costWeighted/x.costQty:0}));
  }

  function productHistory(data,name){
    const rows=[];
    for(const revision of data?.revisionDetails||[]){
      const matches=collectProductsForRevision(revision).filter(x=>x.name===name);
      if(!matches.length) continue;
      const item=matches[0];
      rows.push({date:revision.date,...item});
    }
    return rows.sort((a,b)=>String(b.date).localeCompare(String(a.date)));
  }

  function currentStreak(rows){
    let streak=0;
    for(const row of rows){if(row.shortage>0.005)streak++;else break;}
    return streak;
  }

  function candidateOffsets(data,name,rows){
    const relevantDates=new Set(rows.filter(r=>r.shortage>0.005).map(r=>r.date));
    const selectedLatest=rows[0];
    const map=new Map();
    for(const revision of data?.revisionDetails||[]){
      if(!relevantDates.has(revision.date)) continue;
      const latestDate=selectedLatest?.date===revision.date;
      for(const item of collectProductsForRevision(revision)){
        if(item.name===name || item.surplus<=0.005) continue;
        const x=map.get(item.name)||{name:item.name,surplus:0,count:0,latestSurplus:0};
        x.surplus+=item.surplus; x.count+=1; if(latestDate)x.latestSurplus+=item.surplus; map.set(item.name,x);
      }
    }
    return [...map.values()].sort((a,b)=>(b.latestSurplus-a.latestSurplus)||(b.surplus-a.surplus)).slice(0,6);
  }

  function summaryText(name,rows,totalShort,totalSurplus,net,streak){
    const latest=rows[0];
    let text=`По позиции <b>${esc(name)}</b> за выбранный период: недостача <strong>${money(totalShort)}</strong>, излишки <b>${money(totalSurplus)}</b>, чистое отклонение <strong>${signedMoney(net)}</strong>. `;
    if(streak>=3) text+=`Недостача фиксируется <b>${streak} ревизий подряд</b> — это уже системный сигнал, а не единичный скачок. `;
    else if(streak>0) text+=`Недостача есть ${streak} ревизи${streak===1?'ю':'и'} подряд. `;
    if(latest) text+=`Последнее отклонение: <b>${signedQty(latest.quantityDelta)} ${esc(latest.unit||'ед.')}</b> и ${signedMoney(latest.net)}.`;
    return text;
  }

  function renderDrawer(data,name){
    const rows=productHistory(data,name);
    if(!rows.length)return;
    const totalShort=rows.reduce((s,x)=>s+x.shortage,0), totalSurplus=rows.reduce((s,x)=>s+x.surplus,0), net=totalSurplus-totalShort;
    const streak=currentStreak(rows); const latest=rows[0]; const candidates=candidateOffsets(data,name,rows);
    const countShort=rows.filter(x=>x.shortage>0.005).length;
    const {backdrop,drawer}=ensureDrawer();
    drawer.innerHTML=`
      <div class="rev-product-head"><div><small>Разбор позиции</small><h2>${esc(name)}</h2></div><button class="rev-product-close" type="button" aria-label="Закрыть">×</button></div>
      <div class="rev-product-body">
        <div class="rev-product-summary">${summaryText(name,rows,totalShort,totalSurplus,net,streak)}</div>
        <div class="rev-product-kpis">
          <div class="rev-product-kpi neg"><span>Недостача за период</span><b>${money(totalShort)}</b><small>${countShort} ревизий с минусом</small></div>
          <div class="rev-product-kpi pos"><span>Излишки за период</span><b>${money(totalSurplus)}</b><small>Положительные отклонения той же позиции</small></div>
          <div class="rev-product-kpi ${net<0?'neg':net>0?'pos':''}"><span>Чистое отклонение</span><b>${signedMoney(net)}</b><small>Излишки − недостача</small></div>
          <div class="rev-product-kpi ${streak>=3?'warn':''}"><span>Текущая серия недостач</span><b>${streak} подряд</b><small>${rows.length} ревизий с данными по позиции</small></div>
        </div>

        <section class="rev-product-section"><div class="rev-product-section-head"><div><h3>История позиции по ревизиям</h3><span>Количество, себестоимость и денежное отклонение</span></div></div>
          <div class="rev-product-table-wrap"><table class="rev-product-table"><thead><tr><th>Дата</th><th class="r">Δ количество</th><th class="r">Себест./ед.</th><th class="r">Недостача</th><th class="r">Излишки</th><th class="r">Чистое</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${dateRu(r.date)}</td><td class="r ${r.quantityDelta<0?'neg':r.quantityDelta>0?'pos':'muted'}">${signedQty(r.quantityDelta)}${r.unit?` ${esc(r.unit)}`:''}</td><td class="r">${r.unitCost?money(r.unitCost):'—'}</td><td class="r neg">${r.shortage?money(r.shortage):'—'}</td><td class="r pos">${r.surplus?money(r.surplus):'—'}</td><td class="r ${r.net<0?'neg':r.net>0?'pos':''}">${signedMoney(r.net)}</td></tr>`).join('')}</tbody></table></div>
        </section>

        <section class="rev-product-section"><div class="rev-product-section-head"><div><h3>Возможные связанные плюсы</h3><span>Товары, которые уходили в излишек в те же даты</span></div></div>
          ${candidates.length?`<div class="rev-product-candidates">${candidates.map(c=>`<div class="rev-product-candidate"><div><b>${esc(c.name)}</b><small>${c.count} совпадающих ревизий${c.latestSurplus?` · на последней +${money(c.latestSurplus)}`:''}</small></div><strong>+${money(c.surplus)}</strong></div>`).join('')}</div>`:'<div class="rev-product-warning">Явных положительных отклонений по другим товарам в те же даты не найдено.</div>'}
          <div class="rev-product-warning"><b>Важно:</b> совпадение по дате не доказывает пересорт. Этот список нужен как направление проверки: одинаковое сырьё, похожие названия, полуфабрикат ↔ сырьё, единицы измерения, перемещения и списания.</div>
        </section>

        <section class="rev-product-section"><div class="rev-product-section-head"><div><h3>Что проверить по этой позиции</h3><span>Практический чек-лист для разбора</span></div></div><div class="rev-product-actions">
          <div class="rev-product-action"><i>1</i><div><b>Факт против учёта</b><span>Сверить реальный вес/количество с единицей измерения в iiko и убедиться, что приход, списание и перемещения проведены в той же единице.</span></div></div>
          <div class="rev-product-action"><i>2</i><div><b>Техкарты и полуфабрикаты</b><span>Проверить, не списывается ли эта позиция через другую номенклатуру или полуфабрикат. Особенно важно, если рядом регулярно появляется излишек по связанному товару.</span></div></div>
          <div class="rev-product-action"><i>3</i><div><b>Повторяемость</b><span>${streak>=3?`Минус идёт ${streak} ревизий подряд — после исправления причины следующая ревизия должна подтвердить, что серия остановилась.`:'После корректировки проверить эту же позицию на следующей ревизии и сравнить динамику.'}</span></div></div>
        </div></section>
      </div>`;
    backdrop.classList.add('show');drawer.classList.add('show');drawer.setAttribute('aria-hidden','false');document.body.classList.add('rev-product-open');
  }

  function closeDrawer(){const b=document.getElementById('revProductBackdrop'),d=document.getElementById('revProductDrawer');b?.classList.remove('show');d?.classList.remove('show');d?.setAttribute('aria-hidden','true');document.body.classList.remove('rev-product-open');}

  function decorate(){
    const host=document.getElementById('revisionManagement'); if(!host)return;
    const panels=[...host.querySelectorAll('.rev-mgmt-panel')];
    const productPanel=panels.find(p=>(p.querySelector('h3')?.textContent||'').includes('товары'));
    productPanel?.querySelectorAll('.rev-mgmt-row').forEach(row=>{row.classList.add('rev-product-click');row.title='Открыть историю позиции';});
    const kpis=[...host.querySelectorAll('.rev-mgmt-kpi')];
    const sourceKpi=kpis.find(k=>(k.querySelector('span')?.textContent||'').includes('Главный источник'));
    if(sourceKpi){sourceKpi.classList.add('rev-product-click');sourceKpi.title='Открыть историю позиции';}
  }

  const observer=new MutationObserver(()=>decorate()); observer.observe(document.documentElement,{subtree:true,childList:true});
  const prevFetch=window.fetch.bind(window);
  window.fetch=async(...args)=>{const response=await prevFetch(...args);try{const target=String(args?.[0]?.url||args?.[0]||'');if(target.includes('/revision-data'))response.clone().json().then(data=>{if(data?.success){latestData=data;setTimeout(decorate,750);}}).catch(()=>{});}catch(_){}return response;};

  document.addEventListener('click',event=>{
    if(event.target.closest('.rev-product-close') || event.target.id==='revProductBackdrop'){closeDrawer();return;}
    const click=event.target.closest('.rev-product-click'); if(!click)return;
    const host=click.closest('#revisionManagement'); if(!host)return;
    let name='';
    if(click.classList.contains('rev-mgmt-row')) name=(click.querySelector('b')?.textContent||'').trim();
    else name=(click.querySelector('b')?.textContent||'').trim();
    const data=latestData || window.__dcRevisionDetailData; if(name&&data)renderDrawer(data,name);
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closeDrawer();});
})();