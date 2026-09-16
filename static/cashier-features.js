(() => {
  if (window.__dcCashierFeatures) return;
  window.__dcCashierFeatures = true;

  const style=document.createElement('style');
  style.textContent=`
    .cashier-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:13px}
    .cashier-kpi{border:1px solid var(--line);border-radius:16px;background:#0c0c0c;padding:16px;min-width:0}
    .cashier-kpi small{display:block;color:var(--muted);font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.07em}
    .cashier-kpi strong{display:block;margin-top:9px;font-size:22px;letter-spacing:-.03em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .cashier-kpi span{display:block;margin-top:6px;color:var(--muted);font-size:10px;line-height:1.4}
    .cashier-table{overflow:auto}
    .cashier-table table{min-width:650px}
    .cashier-table th,.cashier-table td{padding:11px 9px}
    .cashier-delta-up{color:var(--green);font-weight:850}.cashier-delta-down{color:var(--red);font-weight:850}.cashier-delta-flat{color:var(--muted)}
    .cashier-signal{margin-top:12px;border:1px solid #50343a;background:#1a1013;border-radius:14px;padding:12px 14px;color:#e6bdc5;font-size:11px;line-height:1.5}
    @media(max-width:1000px){.cashier-kpis{grid-template-columns:1fr 1fr}}
    @media(max-width:600px){.cashier-kpis{grid-template-columns:1fr}.cashier-kpi strong{font-size:20px}}
  `;
  document.head.appendChild(style);

  const $=id=>document.getElementById(id);
  const money=v=>`${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;
  const num=v=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0));
  const pct=v=>`${Math.abs(Number(v||0)).toLocaleString('ru-RU',{maximumFractionDigits:1})}%`;
  const dateText=s=>{const [y,m,d]=String(s||'').slice(0,10).split('-');return d&&m&&y?`${d}.${m}.${y}`:String(s||'—')};
  const html=s=>String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  function findSection(title){
    for(const h of document.querySelectorAll('.section h2')){
      if((h.textContent||'').trim()===title){const head=h.closest('.section');return {head,body:head?.nextElementSibling};}
    }
    return null;
  }

  const receipt=findSection('Чеки и гости');
  if(receipt?.body && !$('cashierAnalytics')){
    const head=document.createElement('div');
    head.className='section';
    head.innerHTML='<h2>Кассиры и средний чек</h2><span class="source-chip">iikoServer OLAP</span>';
    const body=document.createElement('section');
    body.id='cashierAnalytics';
    body.className='panel';
    body.innerHTML=`
      <div class="cashier-kpis">
        <div class="cashier-kpi"><small>Кассиров в периоде</small><strong id="cashierCount">—</strong><span>По закрытым чекам</span></div>
        <div class="cashier-kpi"><small>Средний чек</small><strong id="cashierOverallAvg">—</strong><span id="cashierOverallDelta">Сравнение появится после загрузки</span></div>
        <div class="cashier-kpi"><small>Высокий средний чек</small><strong id="cashierBest">—</strong><span id="cashierBestMeta">—</span></div>
        <div class="cashier-kpi"><small>Наибольшее снижение</small><strong id="cashierRisk">—</strong><span id="cashierRiskMeta">—</span></div>
      </div>
      <div class="cashier-table"><table><thead><tr><th>Кассир</th><th class="num">Чеков</th><th class="num">Выручка</th><th class="num">Средний чек</th><th class="num">Динамика</th></tr></thead><tbody id="cashierTbody"><tr><td colspan="5" class="muted">Выберите период и нажмите «Показать»</td></tr></tbody></table></div>
      <div class="cashier-signal" id="cashierSignal" style="display:none"></div>`;
    receipt.body.insertAdjacentElement('afterend',body);
    body.insertAdjacentElement('beforebegin',head);
  }

  function localPrev(a,b){
    if(typeof window.prevPeriod==='function')return window.prevPeriod(a,b);
    const parse=s=>{const [y,m,d]=s.split('-').map(Number);return new Date(y,m-1,d)};
    const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const A=parse(a),B=parse(b),days=Math.round((B-A)/86400000)+1;
    if(days===1){A.setDate(A.getDate()-7);B.setDate(B.getDate()-7);return[iso(A),iso(B)]}
    const pa=new Date(A);pa.setDate(pa.getDate()-days);const pb=new Date(B);pb.setDate(pb.getDate()-days);return[iso(pa),iso(pb)];
  }

  async function loadOne(point,a,b,channel){
    const r=await fetch(`/cashier-analytics?point=${encodeURIComponent(point)}&from=${a}&to=${b}&channel=${encodeURIComponent(channel||'all')}`,{headers:{Accept:'application/json'}});
    const text=await r.text();let j;try{j=JSON.parse(text)}catch(_){throw new Error(`HTTP ${r.status}`)}
    if(!r.ok||!j?.success)throw new Error(j?.message||j?.details||`HTTP ${r.status}`);
    return j;
  }

  function deltaHtml(current,previous){
    current=Number(current||0);previous=Number(previous||0);
    if(!previous)return '<span class="cashier-delta-flat">—</span>';
    const d=(current-previous)/previous*100;
    if(Math.abs(d)<.05)return '<span class="cashier-delta-flat">→ 0%</span>';
    return `<span class="${d>0?'cashier-delta-up':'cashier-delta-down'}">${d>0?'↑':'↓'} ${pct(d)}</span>`;
  }

  function render(current,previous,pa,pb){
    const prevMap=new Map((previous?.cashiers||[]).map(x=>[String(x.cashier).trim().toLowerCase(),x]));
    const rows=(current?.cashiers||[]).map(x=>{
      const old=prevMap.get(String(x.cashier).trim().toLowerCase());
      const change=old?.averageCheck?((Number(x.averageCheck)-Number(old.averageCheck))/Number(old.averageCheck)*100):null;
      return {...x,previous:old,change};
    });
    $('cashierCount').textContent=num(current?.summary?.cashiers||0);
    $('cashierOverallAvg').textContent=money(current?.summary?.averageCheck||0);
    $('cashierOverallDelta').innerHTML=`${deltaHtml(current?.summary?.averageCheck,previous?.summary?.averageCheck)} к ${pa===pb?dateText(pa):`${dateText(pa)} — ${dateText(pb)}`}`;

    const eligible=rows.filter(x=>Number(x.checks||0)>=3);
    const best=eligible.slice().sort((a,b)=>Number(b.averageCheck)-Number(a.averageCheck))[0];
    $('cashierBest').textContent=best?.cashier||'—';
    $('cashierBestMeta').textContent=best?`${money(best.averageCheck)} · ${num(best.checks)} чек.`:'Недостаточно данных';

    const declines=eligible.filter(x=>x.previous&&Number(x.previous.checks||0)>=3&&x.change!==null).sort((a,b)=>a.change-b.change);
    const risk=declines[0];
    $('cashierRisk').textContent=risk?.cashier||'—';
    $('cashierRiskMeta').textContent=risk?`${risk.change<0?'↓':'↑'} ${pct(risk.change)} · ${money(risk.averageCheck)}`:'Нет сопоставимой базы';

    $('cashierTbody').innerHTML=rows.length?rows.map(x=>`<tr><td><b>${html(x.cashier)}</b></td><td class="num">${num(x.checks)}</td><td class="num">${money(x.revenue)}</td><td class="num"><b>${money(x.averageCheck)}</b></td><td class="num">${deltaHtml(x.averageCheck,x.previous?.averageCheck)}</td></tr>`).join(''):'<tr><td colspan="5" class="muted">Нет данных по кассирам</td></tr>';

    const down=declines.filter(x=>Number(x.change)<-5);
    const signal=$('cashierSignal');
    if(down.length){
      const first=down[0];
      signal.style.display='block';
      signal.innerHTML=`<b>Сигнал по среднему чеку:</b> у ${down.length} кассир${down.length===1?'а':'ов'} снижение больше 5%. Самое заметное — <b>${html(first.cashier)}</b>: ${first.change.toLocaleString('ru-RU',{maximumFractionDigits:1})}% к сопоставимому периоду.`;
    }else signal.style.display='none';
  }

  async function refresh(){
    const a=$('from')?.value,b=$('to')?.value,point=$('point')?.value||'Arai',channel=$('salesChannel')?.value||'all';
    if(!a||!b||!$('cashierTbody'))return;
    $('cashierTbody').innerHTML='<tr><td colspan="5" class="muted">Получаем данные по кассирам…</td></tr>';
    try{
      const [pa,pb]=localPrev(a,b);
      const [cur,prev]=await Promise.all([loadOne(point,a,b,channel),loadOne(point,pa,pb,channel).catch(()=>null)]);
      render(cur,prev,pa,pb);
    }catch(e){
      $('cashierTbody').innerHTML=`<tr><td colspan="5" class="muted">Не удалось получить кассиров: ${html(e.message)}</td></tr>`;
      ['cashierCount','cashierOverallAvg','cashierBest','cashierRisk'].forEach(id=>{if($(id))$(id).textContent='—'});
    }
  }

  $('go')?.addEventListener('click',()=>{setTimeout(refresh,60)});
})();
