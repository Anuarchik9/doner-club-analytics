(() => {
  if (window.__dcEconomicsFeatures) return;
  window.__dcEconomicsFeatures = true;

  const style=document.createElement('style');
  style.textContent=`
    .economics-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
    .econ-card{background:linear-gradient(160deg,#151515,#101010);border:1px solid var(--line);border-radius:20px;padding:20px;min-height:145px;position:relative;overflow:hidden}
    .econ-card:after{content:"";position:absolute;width:105px;height:105px;border-radius:50%;right:-52px;top:-52px;background:rgba(255,90,31,.07)}
    .econ-card small{display:block;color:var(--muted);font-size:12px;font-weight:750}
    .econ-card strong{display:block;font-size:34px;font-weight:950;letter-spacing:-.045em;margin-top:17px;white-space:nowrap}
    .econ-card span{display:block;color:var(--muted);font-size:11px;margin-top:8px;line-height:1.45}
    .econ-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:13px}
    .econ-list{display:grid;gap:12px;margin-top:18px}
    .econ-row{display:grid;grid-template-columns:minmax(100px,1.1fr) minmax(90px,.8fr) auto;gap:10px;align-items:center}
    .econ-row .econ-name{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .econ-track{height:7px;background:#252525;border-radius:99px;overflow:hidden}
    .econ-fill{height:100%;background:linear-gradient(90deg,var(--orange),#ff8e5e);border-radius:99px}
    .econ-values{text-align:right;white-space:nowrap;font-size:11px;color:var(--muted)}
    .econ-values b{color:#fff;font-size:12px}
    .econ-table-wrap{overflow:auto;margin-top:16px}.econ-table{width:100%;border-collapse:collapse;min-width:880px}
    .econ-table th{font-size:10px;color:#777;text-transform:uppercase;letter-spacing:.06em;padding:10px 8px;border-bottom:1px solid var(--line);text-align:left}
    .econ-table td{padding:11px 8px;border-bottom:1px solid #202020;font-size:12px}.econ-table .num{text-align:right;white-space:nowrap}
    .econ-note{color:#777;font-size:10px;line-height:1.45;margin-top:11px}
    @media(max-width:1000px){.economics-cards{grid-template-columns:1fr 1fr}.econ-grid{grid-template-columns:1fr}}
    @media(max-width:600px){.economics-cards{grid-template-columns:1fr}.econ-card strong{font-size:31px}.econ-row{grid-template-columns:90px 1fr}.econ-values{grid-column:2}}
  `;
  document.head.appendChild(style);

  const $=id=>document.getElementById(id);
  const rub=v=>`${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;
  const pct=v=>`${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(Number(v||0))}%`;
  const num=v=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(Number(v||0));
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function findSection(title){
    for(const h of document.querySelectorAll('.section h2')){
      if((h.textContent||'').trim()===title)return h.closest('.section');
    }
    return null;
  }

  const anchor=findSection('Что изменилось');
  if(anchor&&!$('economicsBlock')){
    const head=document.createElement('div');
    head.className='section';
    head.id='economicsHead';
    head.innerHTML='<h2>Экономика продаж</h2><span class="source-chip">iikoServer · Cost</span>';

    const block=document.createElement('div');
    block.id='economicsBlock';
    block.innerHTML=`
      <section class="economics-cards">
        <div class="econ-card"><small>Себестоимость</small><strong id="econCost">—</strong><span id="econCostMeta">Стоимость проданных позиций</span></div>
        <div class="econ-card"><small>Food Cost</small><strong id="econFoodCost">—</strong><span id="econFoodCostMeta">Себестоимость / выручка</span></div>
        <div class="econ-card"><small>Валовая прибыль</small><strong id="econGrossProfit">—</strong><span id="econGrossProfitMeta">Выручка − себестоимость</span></div>
        <div class="econ-card"><small>Валовая маржа</small><strong id="econGrossMargin">—</strong><span id="econGrossMarginMeta">Валовая прибыль / выручка</span></div>
      </section>
      <section class="econ-grid">
        <div class="panel"><h3>Food Cost по категориям</h3><div class="muted">Доля себестоимости в выручке категории</div><div class="econ-list" id="econCategories"><div class="muted">Данные появятся после загрузки</div></div></div>
        <div class="panel"><h3>Позиции по валовой прибыли</h3><div class="muted">Выручка, себестоимость и маржа</div><div class="econ-table-wrap"><table class="econ-table"><thead><tr><th>Позиция</th><th class="num">Выручка</th><th class="num">Себест./ед.</th><th class="num">Себест. всего</th><th class="num">Food Cost</th><th class="num">Вал. прибыль</th><th class="num">Маржа</th></tr></thead><tbody id="econProducts"><tr><td colspan="7" class="muted">Данные появятся после загрузки</td></tr></tbody></table></div></div>
      </section>
      <div class="econ-note" id="econNote">Норматив Food Cost пока не задан — показываем фактические значения из iiko без оценки «норма/критично».</div>`;
    anchor.insertAdjacentElement('beforebegin',block);
    block.insertAdjacentElement('beforebegin',head);
  }

  function loading(){
    if($('econCost'))$('econCost').textContent='…';
    if($('econFoodCost'))$('econFoodCost').textContent='…';
    if($('econGrossProfit'))$('econGrossProfit').textContent='…';
    if($('econGrossMargin'))$('econGrossMargin').textContent='…';
    if($('econCategories'))$('econCategories').innerHTML='<div class="muted">Считаем себестоимость…</div>';
    if($('econProducts'))$('econProducts').innerHTML='<tr><td colspan="7" class="muted">Считаем себестоимость…</td></tr>';
  }

  function failed(message){
    ['econCost','econFoodCost','econGrossProfit','econGrossMargin'].forEach(id=>{if($(id))$(id).textContent='—'});
    if($('econCategories'))$('econCategories').innerHTML='<div class="muted">Не удалось получить Cost из iiko</div>';
    if($('econProducts'))$('econProducts').innerHTML='<tr><td colspan="7" class="muted">Данные себестоимости недоступны</td></tr>';
    if($('econNote'))$('econNote').textContent=`Food Cost пока не загружен: ${message||'неизвестная ошибка'}`;
  }

  function render(data){
    if(!data||data._error){failed(data?._error);return;}
    const s=data.summary||{};
    $('econCost').textContent=rub(s.cost);
    $('econFoodCost').textContent=pct(s.foodCostPct);
    $('econGrossProfit').textContent=rub(s.grossProfit);
    $('econGrossMargin').textContent=pct(s.grossMarginPct);
    $('econCostMeta').textContent=`Выручка слоя Cost: ${rub(s.revenue)}`;
    $('econFoodCostMeta').textContent=`${rub(s.cost)} / ${rub(s.revenue)}`;
    $('econGrossProfitMeta').textContent=`После прямой себестоимости товаров`;
    $('econGrossMarginMeta').textContent=`Без ФОТ, аренды и прочих расходов`;

    const cats=data.categories||[];
    const max=Math.max(...cats.map(x=>Number(x.revenue||0)),1);
    $('econCategories').innerHTML=cats.length?cats.map(x=>`<div class="econ-row"><div class="econ-name" title="${esc(x.name)}">${esc(x.name)}</div><div class="econ-track"><div class="econ-fill" style="width:${Math.max(x.revenue?3:0,Number(x.revenue||0)/max*100)}%"></div></div><div class="econ-values"><b>${pct(x.foodCostPct)}</b><br>${rub(x.cost)} · ${num(x.quantity)} шт.</div></div>`).join(''):'<div class="muted">Нет данных по категориям</div>';

    const products=(data.products||[]).slice().sort((a,b)=>Number(b.grossProfit||0)-Number(a.grossProfit||0)).slice(0,20);
    $('econProducts').innerHTML=products.length?products.map(x=>`<tr><td title="${esc(x.name)}">${esc(x.name)}</td><td class="num">${rub(x.revenue)}</td><td class="num">${rub(x.costPerUnit || (Number(x.quantity||0)?Number(x.cost||0)/Number(x.quantity||0):0))}</td><td class="num">${rub(x.cost)}</td><td class="num">${pct(x.foodCostPct)}</td><td class="num">${rub(x.grossProfit)}</td><td class="num">${pct(x.grossMarginPct)}</td></tr>`).join(''):'<tr><td colspan="7" class="muted">Нет данных</td></tr>';

    let note='Food Cost рассчитан как Cost / выручка по данным iikoServer SALES OLAP. Валовая прибыль не учитывает ФОТ, аренду, налоги и прочие постоянные расходы.';
    if(Number(s.positionsWithoutCost||0)>0){
      const names=(data.positionsWithoutCost||[]).slice(0,4).map(x=>x.name).filter(Boolean);
      note+=` Позиции с продажами, но нулевой рассчитанной себестоимостью: ${s.positionsWithoutCost}${names.length?` (${names.join(', ')})`:''}.`;
    }
    $('econNote').textContent=note;
  }

  async function loadEconomics(){
    const point=$('point')?.value||'Arai',a=$('from')?.value,b=$('to')?.value,channel=$('salesChannel')?.value||'all';
    if(!a||!b)return;
    loading();
    try{
      const r=await fetch(`/economics-analytics?point=${encodeURIComponent(point)}&from=${a}&to=${b}&channel=${encodeURIComponent(channel)}`,{headers:{Accept:'application/json'}});
      const text=await r.text();
      let j=null;try{j=text?JSON.parse(text):null}catch(_){throw new Error(`HTTP ${r.status}: ответ не JSON`)}
      if(!r.ok||!j||j.success===false)throw new Error(j?.details||j?.message||`HTTP ${r.status}`);
      render(j);
    }catch(e){failed(e.message)}
  }

  const go=$('go');
  if(go)go.addEventListener('click',()=>{setTimeout(loadEconomics,0)});
})();
