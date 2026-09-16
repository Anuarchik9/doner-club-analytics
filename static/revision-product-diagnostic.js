(() => {
  if (window.__dcRevisionProductDiagnostic) return;
  window.__dcRevisionProductDiagnostic = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-product-diagnostic{margin-top:11px;padding:13px 14px;border:1px solid #4b392c;border-radius:14px;background:linear-gradient(135deg,#17120e,#101010);font-size:10px;line-height:1.55;color:#cfc5bc}
    .rev-product-diagnostic b{color:#fff}.rev-product-diagnostic strong{color:#ffad72}.rev-product-diagnostic.good{border-color:#294638;background:#0d1511}.rev-product-diagnostic.good strong{color:#8be0b2}.rev-product-diagnostic.bad{border-color:#512d2d;background:#170e0e}.rev-product-diagnostic.bad strong{color:#ff8d8d}
    .rev-product-doc-note{margin-top:8px;color:#8a817a;font-size:9px;line-height:1.5}.rev-product-doc-note b{color:#d7cfc8}
    .rev-product-table .doc-name{max-width:190px;white-space:normal}.rev-product-table .store-name{max-width:150px;white-space:normal;color:#999}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const pct = value => `${Number(value || 0).toLocaleString('ru-RU',{maximumFractionDigits:1})}%`;
  const signedMoney = value => { const n=Number(value||0); return `${n>0?'+':n<0?'−':''}${Math.round(Math.abs(n)).toLocaleString('ru-RU')} ₸`; };
  const signedQty = value => { const n=Number(value||0); return `${n>0?'+':n<0?'−':''}${Math.abs(n).toLocaleString('ru-RU',{maximumFractionDigits:3})}`; };
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => { const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(value||'')); return m?`${m[3]}.${m[2]}.${m[1]}`:String(value||''); };

  function aggregateRevision(revision,name){
    let quantityDelta=0, shortage=0, surplus=0, net=0, unit='';
    const docs=[];
    for(const doc of revision?.documents||[]){
      let dQty=0,dShort=0,dSurplus=0,dNet=0,dUnit='',matched=false;
      for(const line of doc.products||[]){
        if(String(line.name||'').trim()!==name) continue;
        matched=true;
        const q=Number(line.quantityDelta||0), s=Number(line.shortage||0), p=Number(line.surplus||0), n=Number(line.net ?? (p-s));
        dQty+=q; dShort+=s; dSurplus+=p; dNet+=n; if(!dUnit&&line.unit)dUnit=String(line.unit);
      }
      if(matched){
        docs.push({document:String(doc.document||'Без номера'),store:String(doc.store||'Склад не определён'),quantityDelta:dQty,shortage:dShort,surplus:dSurplus,net:dNet,unit:dUnit});
        quantityDelta+=dQty; shortage+=dShort; surplus+=dSurplus; net+=dNet; if(!unit&&dUnit)unit=dUnit;
      }
    }
    return {date:revision?.date,quantityDelta,shortage,surplus,net,unit,docs,matched:docs.length>0};
  }

  function productRows(data,name){
    return (data?.revisionDetails||[]).map(r=>aggregateRevision(r,name)).filter(x=>x.matched).sort((a,b)=>String(b.date).localeCompare(String(a.date)));
  }

  function shortageStreak(rows){let n=0;for(const r of rows){if(r.shortage>0.005)n++;else break;}return n;}

  function diagnostic(rows){
    const totalShort=rows.reduce((s,x)=>s+x.shortage,0), totalSurplus=rows.reduce((s,x)=>s+x.surplus,0);
    const gross=totalShort+totalSurplus, net=totalSurplus-totalShort;
    const mixed=rows.filter(x=>x.shortage>0.005&&x.surplus>0.005).length;
    const comp=gross>0 ? Math.max(0,(gross-Math.abs(net))/gross*100) : 0;
    const ratio=rows.length?mixed/rows.length:0;
    let kind='',title='Паттерн требует разбора',text='По данным одной только ревизии нельзя надёжно определить причину отклонения.';
    if(ratio>=.6 && comp>=70){
      kind='good'; title='Смешанное расхождение — сначала проверять учёт и технологический цикл';
      text=`В ${mixed} из ${rows.length} ревизий по одной и той же позиции одновременно есть и недостача, и излишек. Внутренняя компенсация за период — ${pct(comp)}. Такой рисунок больше похож на пересорт, разные стадии полуфабриката, единицы измерения, движения или время проводки документов, чем на одностороннее исчезновение товара. Это направление проверки, а не доказанная причина.`;
    } else if(net<0 && comp<40){
      kind='bad'; title='Преимущественно чистая недостача';
      text=`Плюсы слабо перекрывают минусы: внутренняя компенсация ${pct(comp)}. В первую очередь нужно подтверждать фактическую недостачу и проверять списания, отпуск, потери и движения.`;
    }
    return {totalShort,totalSurplus,gross,net,mixed,comp,ratio,kind,title,text};
  }

  function docTraceHtml(row){
    if(!row?.docs?.length) return '';
    const hasNeg=row.docs.some(d=>d.net<-.005), hasPos=row.docs.some(d=>d.net>.005);
    const note = hasNeg&&hasPos
      ? '<b>Важный сигнал:</b> в одной дате разные документы/склады дают противоположный чистый знак. Это нужно разобрать первым — здесь может находиться источник взаимной компенсации.'
      : row.docs.some(d=>d.shortage>0.005&&d.surplus>0.005)
        ? '<b>Важный сигнал:</b> внутри одного документа по позиции одновременно формируются минус и плюс. Проверь строки документа и единицы измерения.'
        : 'Здесь видно, какой именно документ и склад сформировали отклонение последней ревизии.';
    return `<section class="rev-product-section rev-product-doc-trace"><div class="rev-product-section-head"><div><h3>Откуда взялось отклонение ${dateRu(row.date)}</h3><span>Разбор последней даты по документам и складам</span></div></div>
      <div class="rev-product-table-wrap"><table class="rev-product-table"><thead><tr><th>Документ</th><th>Склад</th><th class="r">Δ количество</th><th class="r">Недостача</th><th class="r">Излишки</th><th class="r">Чистое</th></tr></thead><tbody>${row.docs.map(d=>`<tr><td class="doc-name">${esc(d.document)}</td><td class="store-name">${esc(d.store)}</td><td class="r ${d.quantityDelta<0?'neg':d.quantityDelta>0?'pos':'muted'}">${signedQty(d.quantityDelta)}${d.unit?` ${esc(d.unit)}`:''}</td><td class="r neg">${d.shortage?money(d.shortage):'—'}</td><td class="r pos">${d.surplus?money(d.surplus):'—'}</td><td class="r ${d.net<0?'neg':d.net>0?'pos':''}">${signedMoney(d.net)}</td></tr>`).join('')}</tbody></table></div>
      <div class="rev-product-doc-note">${note}</div></section>`;
  }

  function enhance(){
    const drawer=document.getElementById('revProductDrawer');
    if(!drawer || !drawer.classList.contains('show') || drawer.querySelector('.rev-product-diagnostic')) return;
    const data=window.__dcRevisionDetailData; if(!data)return;
    const name=(drawer.querySelector('.rev-product-head h2')?.textContent||'').trim(); if(!name)return;
    const rows=productRows(data,name); if(!rows.length)return;
    const d=diagnostic(rows), streak=shortageStreak(rows), countSurplus=rows.filter(x=>x.surplus>0.005).length;

    const summary=drawer.querySelector('.rev-product-summary');
    if(summary){
      summary.innerHTML=`По позиции <b>${esc(name)}</b> за выбранный период: недостача <strong>${money(d.totalShort)}</strong>, излишки <b>${money(d.totalSurplus)}</b>, чистое отклонение <strong>${signedMoney(d.net)}</strong>. Недостача присутствует <b>${streak} ревизий подряд</b>, но излишки также есть в <b>${countSurplus} из ${rows.length}</b> ревизий. Поэтому серия «недостач» не означает ${streak} отдельных чистых потерь.`;
    }

    const kpis=[...drawer.querySelectorAll('.rev-product-kpi')];
    if(kpis[3]){
      const label=kpis[3].querySelector('span'), value=kpis[3].querySelector('b'), small=kpis[3].querySelector('small');
      if(label)label.textContent='Смешанные ревизии';
      if(value)value.textContent=`${d.mixed} из ${rows.length}`;
      if(small)small.textContent=`${streak} подряд с недостачей · ${pct(d.comp)} внутренней компенсации`;
      kpis[3].classList.toggle('warn',d.mixed>0);
    }

    const kpiGrid=drawer.querySelector('.rev-product-kpis');
    if(kpiGrid){
      const box=document.createElement('div');box.className=`rev-product-diagnostic ${d.kind}`;
      box.innerHTML=`<strong>${esc(d.title)}</strong><br>${d.text}`;
      kpiGrid.insertAdjacentElement('afterend',box);
    }

    const historySection=[...drawer.querySelectorAll('.rev-product-section')].find(s=>(s.querySelector('h3')?.textContent||'').includes('История позиции'));
    if(historySection) historySection.insertAdjacentHTML('afterend',docTraceHtml(rows[0]));
  }

  const observer=new MutationObserver(()=>setTimeout(enhance,0));
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
})();