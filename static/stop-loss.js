(() => {
  if (window.__dcStopLoss) return;
  window.__dcStopLoss = true;

  const style=document.createElement('style');
  style.textContent=`
    .stop-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:13px;margin-bottom:13px}
    .stop-card{background:linear-gradient(160deg,#151515,#101010);border:1px solid var(--line);border-radius:20px;padding:20px;min-height:140px;position:relative;overflow:hidden}
    .stop-card:after{content:"";position:absolute;width:100px;height:100px;border-radius:50%;right:-50px;top:-50px;background:rgba(255,90,31,.07)}
    .stop-card small{display:block;color:var(--muted);font-size:12px;font-weight:750}.stop-card strong{display:block;font-size:32px;font-weight:950;letter-spacing:-.04em;margin-top:17px}.stop-card span{display:block;color:var(--muted);font-size:11px;margin-top:8px;line-height:1.45}
    .stop-list{display:grid;gap:10px;margin-top:15px}.stop-item{display:grid;grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(110px,.65fr));gap:12px;align-items:center;padding:15px;border:1px solid var(--line);border-radius:16px;background:#0c0c0c}
    .stop-name b{display:block;font-size:13px}.stop-name span{display:block;color:var(--muted);font-size:10px;margin-top:5px}.stop-metric small{display:block;color:#777;font-size:9px;text-transform:uppercase;letter-spacing:.06em}.stop-metric b{display:block;margin-top:5px;font-size:13px}.stop-empty{padding:18px;border:1px solid #294b3a;background:#0d1b14;border-radius:16px;color:#9fe4bf}.stop-note{margin-top:11px;color:#777;font-size:10px;line-height:1.5}.stop-limited{margin-top:12px;color:#a9a9a3;font-size:11px;line-height:1.55}
    @media(max-width:900px){.stop-summary{grid-template-columns:1fr 1fr}.stop-item{grid-template-columns:1fr 1fr}.stop-name{grid-column:1/-1}}
    @media(max-width:600px){.stop-summary{grid-template-columns:1fr}.stop-item{grid-template-columns:1fr}.stop-name{grid-column:auto}.stop-card strong{font-size:30px}}
  `;
  document.head.appendChild(style);

  const $=id=>document.getElementById(id);
  const rub=v=>`${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v||0))} ₸`;
  const num=v=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(Number(v||0));
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function duration(mins){
    mins=Math.max(0,Math.round(Number(mins||0)));
    const h=Math.floor(mins/60),m=mins%60;
    if(h&&m)return `${h} ч ${m} мин`;
    if(h)return `${h} ч`;
    return `${m} мин`;
  }

  function findSection(title){
    for(const h of document.querySelectorAll('.section h2')){
      if((h.textContent||'').trim()===title)return h.closest('.section');
    }
    return null;
  }

  const anchor=findSection('Что изменилось');
  if(anchor&&!$('stopLossBlock')){
    const head=document.createElement('div');
    head.className='section';
    head.id='stopLossHead';
    head.innerHTML='<h2>Стоп-лист и упущенная выгода</h2><span class="source-chip">iiko stop-list</span>';
    const block=document.createElement('div');
    block.id='stopLossBlock';
    block.innerHTML=`
      <section class="stop-summary">
        <div class="stop-card"><small>Сейчас в стопе</small><strong id="stopCount">—</strong><span id="stopCountMeta">Проверяем текущий стоп-лист</span></div>
        <div class="stop-card"><small>Потенциально потерянная выручка</small><strong id="stopLostRevenue">—</strong><span>Оценка по обычной скорости продаж</span></div>
        <div class="stop-card"><small>Потенциально потерянная валовая прибыль</small><strong id="stopLostProfit">—</strong><span>С учётом исторической себестоимости</span></div>
      </section>
      <section class="panel"><h3>Позиции в стопе</h3><div class="muted">Сколько могли бы продать за время недоступности</div><div id="stopItems" class="stop-list"><div class="muted">Данные появятся после проверки iiko</div></div><div id="stopLimited" class="stop-limited"></div><div id="stopNote" class="stop-note"></div></section>`;
    anchor.insertAdjacentElement('beforebegin',block);
    block.insertAdjacentElement('beforebegin',head);
  }

  function loading(){
    if($('stopCount'))$('stopCount').textContent='…';
    if($('stopLostRevenue'))$('stopLostRevenue').textContent='…';
    if($('stopLostProfit'))$('stopLostProfit').textContent='…';
    if($('stopItems'))$('stopItems').innerHTML='<div class="muted">Проверяем стоп-лист и историю продаж…</div>';
  }
  function failed(message){
    if($('stopCount'))$('stopCount').textContent='—';
    if($('stopLostRevenue'))$('stopLostRevenue').textContent='—';
    if($('stopLostProfit'))$('stopLostProfit').textContent='—';
    if($('stopItems'))$('stopItems').innerHTML='<div class="muted">Не удалось получить стоп-лист</div>';
    if($('stopNote'))$('stopNote').textContent=message||'Неизвестная ошибка';
  }
  function render(data){
    if(!data||data._error){failed(data?._error);return;}
    const s=data.summary||{},items=data.items||[],limited=data.limited||[];
    $('stopCount').textContent=String(Math.round(Number(s.stoppedPositions||0)));
    $('stopLostRevenue').textContent=rub(s.estimatedLostRevenue||0);
    $('stopLostProfit').textContent=rub(s.estimatedLostGrossProfit||0);
    $('stopCountMeta').textContent=items.length?`Ожидаемо недопродано ≈ ${num(s.expectedLostUnits||0)} ед.`:'Активных стопов сейчас нет';
    if(!items.length){
      $('stopItems').innerHTML='<div class="stop-empty">Сейчас стоп-лист пуст — активных полностью недоступных позиций не найдено.</div>';
    }else{
      $('stopItems').innerHTML=items.map(x=>`<div class="stop-item"><div class="stop-name"><b>${esc(x.name)}</b><span>В стопе: ${duration(x.durationMinutes)} · ожидаемо ≈ ${num(x.expectedUnits)} ед.</span></div><div class="stop-metric"><small>Средняя цена</small><b>${rub(x.averagePrice)}</b></div><div class="stop-metric"><small>Потеря выручки</small><b>${rub(x.estimatedLostRevenue)}</b></div><div class="stop-metric"><small>Упущенная вал. прибыль</small><b>${rub(x.estimatedLostGrossProfit)}</b></div></div>`).join('');
    }
    $('stopLimited').textContent=limited.length?`Ограниченный остаток, но ещё не полный стоп: ${limited.slice(0,6).map(x=>`${x.name} — ${num(x.balance)}`).join(' · ')}${limited.length>6?' · …':''}`:'';
    $('stopNote').textContent='Оценка строится по продажам этой позиции в аналогичные часы и дни недели за последние 28 дней. Если iiko не отдаёт точное время постановки в стоп, отсчёт начинается с первого обнаружения дашбордом; после перезапуска Render локальный отсчёт может начаться заново.';
  }

  async function load(){
    const point=$('point')?.value||'Arai';
    if(!point)return;
    loading();
    try{
      const r=await fetch(`/stop-loss?point=${encodeURIComponent(point)}`,{headers:{Accept:'application/json'}});
      const text=await r.text();let j=null;try{j=text?JSON.parse(text):null}catch(_){throw new Error(`HTTP ${r.status}: ответ не JSON`)}
      if(!r.ok||!j||j.success===false)throw new Error(j?.details||j?.message||`HTTP ${r.status}`);
      render(j);
    }catch(e){failed(e.message)}
  }

  const go=$('go');
  if(go)go.addEventListener('click',()=>setTimeout(load,0));
  setTimeout(()=>{if($('point')?.value)load()},1200);
  setInterval(()=>{if(document.visibilityState==='visible'&&$('point')?.value)load()},5*60*1000);
})();
