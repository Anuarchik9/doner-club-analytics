(() => {
  if (window.__dcRevisionManagement) return;
  window.__dcRevisionManagement = true;

  const style = document.createElement('style');
  style.textContent = `
    html,body{max-width:100%;overflow-x:hidden}
    .rev-accuracy-grid,.rev-accuracy-panel,.rev-accuracy-grid>*{min-width:0}
    .rev-accuracy-table-wrap{width:100%;max-width:100%;overflow-x:auto;overscroll-behavior-inline:contain}
    .rev-accuracy-table{width:max-content;min-width:760px}
    .rev-management{margin-top:28px}
    .rev-management-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:12px}
    .rev-management-head h2{margin:0;font-size:20px}.rev-management-head span{color:#777;font-size:10px;text-align:right;line-height:1.45}
    .rev-management-summary{padding:17px 18px;border:1px solid #4a3328;border-radius:18px;background:linear-gradient(135deg,#17110e,#101010);font-size:13px;line-height:1.55;color:#d8d3cc}
    .rev-management-summary b{color:#fff}.rev-management-summary strong{color:#ff9c72}
    .rev-management-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}
    .rev-mgmt-kpi{padding:15px 16px;border:1px solid #292929;border-radius:16px;background:linear-gradient(160deg,#151515,#0e0e0e);min-height:118px}
    .rev-mgmt-kpi span{display:block;color:#777;font-size:9px;text-transform:uppercase;letter-spacing:.07em}.rev-mgmt-kpi b{display:block;margin-top:8px;font-size:22px;letter-spacing:-.03em;line-height:1.1}.rev-mgmt-kpi small{display:block;color:#85857f;font-size:9px;line-height:1.45;margin-top:6px}.rev-mgmt-kpi.bad b{color:#ff8585}.rev-mgmt-kpi.good b{color:#8be0b2}.rev-mgmt-kpi.warn b{color:#ffad72}
    .rev-management-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.rev-mgmt-panel{min-width:0;border:1px solid #292929;border-radius:18px;background:linear-gradient(160deg,#151515,#0f0f0f);padding:17px}.rev-mgmt-panel h3{margin:0;font-size:14px}.rev-mgmt-panel>p{margin:5px 0 0;color:#777;font-size:9px;line-height:1.45}
    .rev-mgmt-list{display:grid;gap:0;margin-top:10px}.rev-mgmt-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid #222}.rev-mgmt-row:last-child{border-bottom:0}.rev-mgmt-row b{display:block;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rev-mgmt-row small{display:block;color:#777;font-size:9px;line-height:1.4;margin-top:3px}.rev-mgmt-row strong{font-size:10px;white-space:nowrap}.rev-mgmt-row strong.neg{color:#ff8b8b}.rev-mgmt-row strong.pos{color:#8be0b2}
    .rev-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.rev-action{padding:14px 15px;border:1px solid #32302c;border-radius:15px;background:#0d0d0d}.rev-action i{display:grid;place-items:center;width:24px;height:24px;border-radius:8px;background:rgba(255,90,31,.12);color:#ff8f62;font-style:normal;font-size:10px;font-weight:900}.rev-action b{display:block;margin-top:9px;font-size:11px}.rev-action span{display:block;margin-top:5px;color:#85857f;font-size:9px;line-height:1.5}
    .rev-mgmt-note{margin-top:10px;color:#71716c;font-size:9px;line-height:1.5}
    @media(max-width:1250px){.rev-accuracy-grid{grid-template-columns:1fr!important}.rev-accuracy-table{min-width:820px}}
    @media(max-width:1000px){.rev-management-kpis{grid-template-columns:1fr 1fr}.rev-management-grid{grid-template-columns:1fr}.rev-actions{grid-template-columns:1fr}}
    @media(max-width:600px){.rev-management-head{align-items:flex-start;flex-direction:column}.rev-management-head span{text-align:left}.rev-management-kpis{grid-template-columns:1fr}.rev-mgmt-kpi b{font-size:20px}.rev-management-summary{font-size:12px}}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const pct = value => `${Math.abs(Number(value || 0)).toLocaleString('ru-RU',{maximumFractionDigits:1})}%`;
  const signedMoney = value => {
    const n = Number(value || 0); const sign = n > 0 ? '+' : n < 0 ? '−' : '';
    return `${sign}${Math.round(Math.abs(n)).toLocaleString('ru-RU')} ₸`;
  };
  const signedPct = value => {
    const n = Number(value || 0); const sign = n > 0 ? '+' : n < 0 ? '−' : '';
    return `${sign}${Math.abs(n).toLocaleString('ru-RU',{maximumFractionDigits:1})}%`;
  };
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => {
    const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(value||''));
    return m ? `${m[3]}.${m[2]}.${m[1]}` : String(value||'—');
  };

  function latestDetail(data, date) {
    return (data.revisionDetails || []).find(item => item.date === date) || {documents:[]};
  }

  function latestProducts(data, date) {
    const map = new Map();
    for (const doc of latestDetail(data,date).documents || []) {
      for (const item of doc.products || []) {
        const name = String(item.name || 'Позиция без названия').trim();
        const row = map.get(name) || {name, shortage:0, surplus:0, net:0, unit:item.unit || ''};
        row.shortage += Number(item.shortage || 0);
        row.surplus += Number(item.surplus || 0);
        row.net += Number(item.net || 0);
        map.set(name,row);
      }
    }
    return [...map.values()].sort((a,b)=>Math.max(b.shortage,b.surplus)-Math.max(a.shortage,a.surplus));
  }

  function latestStores(data, date) {
    const map = new Map();
    for (const doc of latestDetail(data,date).documents || []) {
      const name = String(doc.store || 'Склад не определён');
      const row = map.get(name) || {name, shortage:0, surplus:0, net:0, docs:0};
      row.shortage += Number(doc.shortage || 0);
      row.surplus += Number(doc.surplus || 0);
      row.net += Number(doc.net || 0);
      row.docs += 1;
      map.set(name,row);
    }
    return [...map.values()].sort((a,b)=>(b.shortage+b.surplus)-(a.shortage+a.surplus));
  }

  function relabelPeriodCards() {
    const sections=[...document.querySelectorAll('.section')];
    const head=sections.find(s => (s.querySelector('h2')?.textContent || '').trim()==='Итог периода');
    if (head) {
      const h=head.querySelector('h2'); if (h) h.textContent='Итог выбранного периода';
      const hint=head.querySelector('.muted'); if (hint) hint.textContent='Накопленные суммы за весь выбранный месяц';
    }
    const cards=document.querySelector('.cards');
    if (!cards) return;
    const labels=[...cards.querySelectorAll('.label')];
    if (labels[1]) labels[1].textContent='Недостача за период';
    if (labels[2]) labels[2].textContent='Излишки за период';
    if (labels[3]) labels[3].textContent='Чистое за период';
  }

  function ensureHost() {
    let host=document.getElementById('revisionManagement');
    if (!host) {
      host=document.createElement('section');
      host.id='revisionManagement';
      host.className='rev-management';
    }
    const analyticsHead=[...document.querySelectorAll('.section')].find(s => (s.querySelector('h2')?.textContent || '').trim()==='Аналитика ревизий');
    if (analyticsHead && analyticsHead.previousElementSibling !== host) analyticsHead.insertAdjacentElement('beforebegin',host);
    return host;
  }

  function rowHtml(item, kind='product') {
    const net=Number(item.net || 0);
    const name=esc(item.name);
    const meta=kind==='store'
      ? `${item.docs} докум. · недостача ${money(item.shortage)} · излишки ${money(item.surplus)}`
      : `недостача ${money(item.shortage)} · излишки ${money(item.surplus)}`;
    return `<div class="rev-mgmt-row"><div><b title="${name}">${name}</b><small>${meta}</small></div><strong class="${net<0?'neg':net>0?'pos':''}">${signedMoney(net)}</strong></div>`;
  }

  function render(data) {
    if (!data?.success || !data.history?.length) return;
    relabelPeriodCards();
    const latest=data.history[0];
    const shortage=Number(latest.shortage || 0), surplus=Number(latest.surplus || 0), gross=Number(latest.gross || (shortage+surplus));
    const net=Number(latest.net ?? (surplus-shortage));
    const book=Number(latest.bookValue || 0);
    const netPct=book>0.01 ? net/book*100 : null;
    const change=latest.shortageChangePct;
    const offsetShare=gross>0 ? Math.max(0,(gross-Math.abs(net))/gross*100) : 0;
    const products=latestProducts(data,latest.date);
    const stores=latestStores(data,latest.date);
    const topShort=products.slice().sort((a,b)=>b.shortage-a.shortage).find(x=>x.shortage>0.005);
    const topShare=topShort && shortage>0 ? topShort.shortage/shortage*100 : 0;
    const recurring=(data.systemProblems || []).find(x=>Number(x.currentShortageStreak || 0)>=2) || (data.systemProblems || [])[0] || null;

    let summary=`Последняя ревизия <b>${dateRu(latest.date)}</b>: `;
    summary += net<0 ? `чистый минус <strong>${money(Math.abs(net))}</strong>. ` : net>0 ? `чистый плюс <b>${money(net)}</b>. ` : 'чистое отклонение около нуля. ';
    summary += `При этом общий оборот расхождений — <b>${money(gross)}</b>. `;
    if (offsetShare>=50) summary += `<b>${pct(offsetShare)}</b> валовых минусов и плюсов взаимно компенсируются — поэтому сначала надо искать пересорт, неверные единицы, движения и ошибки учёта, а не смотреть только на чистый итог.`;
    else summary += `Расхождения слабо компенсируются между собой, поэтому чистый итог близок к общему масштабу проблемы.`;

    const changeKind = change===null || change===undefined ? '' : Number(change)>0 ? 'bad' : 'good';
    const changeText = change===null || change===undefined ? '—' : `${Number(change)>0?'+':'−'}${pct(change)}`;
    const netKind = net<0 ? 'bad' : net>0 ? 'good' : '';
    const offsetKind = offsetShare>=60 ? 'warn' : '';

    const action1=topShort
      ? `<b>1. Начать с ${esc(topShort.name)}</b><span>${money(topShort.shortage)} недостачи на последней ревизии${topShare?` · ${pct(topShare)} всей недостачи`:''}. Сначала сверить фактическое количество, единицу измерения и движения по этой позиции.</span>`
      : '<b>1. Проверить крупнейшие строки</b><span>В последней ревизии нет одной явно доминирующей позиции — разбирать нужно несколько строк.</span>';
    const action2=offsetShare>=50
      ? `<b>2. Проверить взаимную компенсацию</b><span>${pct(offsetShare)} оборота расхождений перекрывается противоположными отклонениями. Сверить пересорт, списания, приходы, перемещения и корректность складов.</span>`
      : '<b>2. Проверить чистый минус</b><span>Минусы и плюсы почти не перекрывают друг друга. Фокус — на фактической недостаче и документах последней ревизии.</span>';
    const action3=recurring
      ? `<b>3. Закрыть системную проблему</b><span>${esc(recurring.name)}: ${Number(recurring.currentShortageStreak || 0)>=2?`${recurring.currentShortageStreak} ревизии подряд`:`недостача повторялась ${recurring.shortageRevisionCount} раз`} · всего ${money(recurring.shortage)} за период.</span>`
      : '<b>3. Зафиксировать контроль</b><span>Повторяющихся позиций пока не выделено. После следующей ревизии сравнить те же товары повторно.</span>';

    const host=ensureHost();
    host.innerHTML=`
      <div class="rev-management-head"><h2>Управленческий вывод</h2><span>Что случилось · где проблема · что делать дальше</span></div>
      <div class="rev-management-summary">${summary}</div>
      <div class="rev-management-kpis">
        <div class="rev-mgmt-kpi ${netKind}"><span>Чистый итог последней ревизии</span><b>${signedMoney(net)}</b><small>${netPct===null?'Нет книжного остатка':`${signedPct(netPct)} от книжного остатка`} · это складское отклонение, не P&amp;L.</small></div>
        <div class="rev-mgmt-kpi ${changeKind}"><span>Недостача к предыдущей ревизии</span><b>${changeText}</b><small>${change===null||change===undefined?'Нет базы сравнения':Number(change)>0?'Недостача выросла — требуется разбор причины':'Недостача снизилась относительно предыдущей ревизии'}.</small></div>
        <div class="rev-mgmt-kpi ${offsetKind}"><span>Взаимная компенсация минусов и плюсов</span><b>${pct(offsetShare)}</b><small>Чем выше показатель, тем сильнее чистый итог скрывает внутренние расхождения по товарам.</small></div>
        <div class="rev-mgmt-kpi ${topShort?'warn':''}"><span>Главный источник недостачи</span><b>${topShort?esc(topShort.name):'—'}</b><small>${topShort?`${money(topShort.shortage)} · ${pct(topShare)} недостачи последней ревизии`:'Нет данных по товарным строкам'}.</small></div>
      </div>
      <div class="rev-management-grid">
        <div class="rev-mgmt-panel"><h3>Где проблема: склады и документы</h3><p>Последняя ревизия. Чистый итог справа, ниже — недостача и излишки.</p><div class="rev-mgmt-list">${stores.length?stores.slice(0,6).map(x=>rowHtml(x,'store')).join(''):'<div class="muted" style="margin-top:10px">Нет детализации по складам.</div>'}</div></div>
        <div class="rev-mgmt-panel"><h3>Где проблема: товары</h3><p>Крупнейшие отклонения последней ревизии.</p><div class="rev-mgmt-list">${products.length?products.slice(0,7).map(x=>rowHtml(x,'product')).join(''):'<div class="muted" style="margin-top:10px">Нет товарной детализации.</div>'}</div></div>
      </div>
      <div class="rev-actions"><div class="rev-action"><i>1</i>${action1}</div><div class="rev-action"><i>2</i>${action2}</div><div class="rev-action"><i>3</i>${action3}</div></div>
      <div class="rev-mgmt-note">Важно: «общее расхождение» — недостача + излишки и показывает объём ошибок учёта. «Чистый итог» — излишки − недостача и показывает направление отклонения. Излишек по одному товару не доказывает, что он экономически компенсирует недостачу другого.</div>`;
  }

  function schedule(data){[90,260,650,1100].forEach(ms=>setTimeout(()=>render(data),ms));}
  relabelPeriodCards();
  const previousFetch=window.fetch.bind(window);
  window.fetch=async(...args)=>{
    const response=await previousFetch(...args);
    try{
      const target=String(args?.[0]?.url || args?.[0] || '');
      if(target.includes('/revision-data')) response.clone().json().then(data=>{if(data?.success)schedule(data)}).catch(()=>{});
    }catch(_){}
    return response;
  };
})();