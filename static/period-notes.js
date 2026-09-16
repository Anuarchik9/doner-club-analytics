(() => {
  if (window.__dcPeriodNotes) return;
  window.__dcPeriodNotes = true;

  const style=document.createElement('style');
  style.textContent=`
    .period-notes{display:none;margin:16px 0 22px}
    .period-notes.show{display:block}
    .period-notes-panel{border:1px solid #3b302b;border-radius:18px;background:linear-gradient(155deg,rgba(255,90,31,.09),#111 58%);padding:18px 20px}
    .period-notes-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:13px}
    .period-notes-head h3{margin:0;font-size:17px}.period-notes-head span{font-size:10px;color:var(--orange);font-weight:850;text-transform:uppercase;letter-spacing:.08em}
    .period-notes-list{display:grid;gap:10px}
    .period-note{display:grid;grid-template-columns:110px 1fr;gap:13px;padding:11px 12px;border:1px solid #2b2928;border-radius:13px;background:rgba(10,10,10,.58)}
    .period-note time{color:#ff9a71;font-size:11px;font-weight:850}.period-note div{font-size:12px;line-height:1.5;color:#ddd}
    @media(max-width:600px){.period-note{grid-template-columns:1fr;gap:5px}.period-notes-panel{padding:16px}}
  `;
  document.head.appendChild(style);

  const NOTES=[
    {from:'2025-03-01',to:'2025-03-31',date:'Март 2025',text:'Ораза.'},
    {from:'2025-04-01',to:'2025-04-30',date:'Апрель 2025',text:'Комбо от Wolt — Донер 1.5 куриный.'},
    {from:'2025-05-01',to:'2025-05-31',date:'Май 2025',text:'Комбо «Ас бокс» — Донер 1.5 куриный.'},
    {from:'2025-06-01',to:'2025-06-30',date:'Июнь 2025',text:'Комбо Батон Ассорти + Куриный. Акция Манас: куриный стандарт + айран.'},
    {from:'2025-06-08',to:'2025-06-09',date:'8–9 июня 2025',text:'Wolt Ads стоял; ориентировочно потеряно около 2,3 млн ₸ оборота вместе с повторным периодом 17–19 июня.'},
    {from:'2025-06-16',to:'2025-06-16',date:'16 июня 2025',text:'«Бирге же» — Донер 1.5 ассорти, 2 шт.'},
    {from:'2025-06-17',to:'2025-06-19',date:'17–19 июня 2025',text:'Wolt Ads стоял; период повлиял на оборот.'},
    {from:'2025-07-01',to:'2025-07-31',date:'Июль 2025',text:'2 полтора ассорти + двойной ассорти. Начало работы Starter.'},
    {from:'2025-07-01',to:'2025-07-01',date:'1 июля 2025',text:'Остановка скидки 20% в Wolt на батоны куриный и ассорти.'},
    {from:'2025-12-01',to:'2025-12-31',date:'Декабрь 2025',text:'Начало работы с Chocofood.'},
    {from:'2025-12-15',to:'2025-12-15',date:'15 декабря 2025',text:'Добавление комбо «Донер говяжий».'},
    {from:'2026-01-09',to:'2026-01-27',date:'9–27 января 2026',text:'Стандарт заменён на 1.5, 1.5 — на двойной; добавлена новая позиция «Мини донер». Компания проработала в этой конфигурации 19 дней.'},
    {from:'2026-01-28',to:'2026-01-30',date:'28 января 2026',text:'Размеры вернули как было; новый Мини донер оставлен. Итого — 4 вида донеров.'},
    {from:'2026-01-31',to:'2026-01-31',date:'31 января 2026',text:'Закрылась точка Манас.'},
    {from:'2026-04-01',to:'2026-04-30',date:'Апрель 2026',text:'Новый дизайн меню от Жазиры.'},
    {from:'2026-05-06',to:'2026-05-06',date:'6 мая 2026',text:'Закрылась точка Сыганак.'},
    {from:'2026-09-01',to:'2026-09-30',date:'Сентябрь 2026',text:'Открытие новой точки Doner Club на Республике.',point:'republic'},
  ];

  const fromInput=document.getElementById('from');
  const toInput=document.getElementById('to');
  const pointInput=document.getElementById('point');
  const error=document.getElementById('error');
  if(!fromInput||!toInput||!error)return;

  const wrap=document.createElement('div');
  wrap.id='periodNotes';
  wrap.className='period-notes';
  wrap.innerHTML='<section class="period-notes-panel"><div class="period-notes-head"><h3>Примечания периода</h3><span>Что могло повлиять на показатели</span></div><div class="period-notes-list" id="periodNotesList"></div></section>';
  error.insertAdjacentElement('afterend',wrap);

  const overlap=(a1,a2,b1,b2)=>a1<=b2&&a2>=b1;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function republicSelected(){
    try {
      if(window.DCPointSelection?.includesRepublic) return !!window.DCPointSelection.includesRepublic();
    } catch(_) {}
    const option=pointInput?.options?.[pointInput.selectedIndex];
    const text=`${pointInput?.value||''} ${option?.textContent||''}`.toLowerCase();
    return text.includes('республика')||text.includes('republic');
  }

  function noteApplies(note){
    if(!note.point) return true;
    if(note.point==='republic') return republicSelected();
    return true;
  }

  function hide(){wrap.classList.remove('show');const list=document.getElementById('periodNotesList');if(list)list.innerHTML='';}
  function render(){
    const a=fromInput.value,b=toInput.value||a;
    if(!a||!b){hide();return;}
    const matches=NOTES.filter(n=>overlap(a,b,n.from,n.to)&&noteApplies(n));
    if(!matches.length){hide();return;}
    document.getElementById('periodNotesList').innerHTML=matches.map(n=>`<div class="period-note"><time>${esc(n.date)}</time><div>${esc(n.text)}</div></div>`).join('');
    wrap.classList.add('show');
  }

  // Notes are intentionally absent in the untouched/default dashboard.
  // They appear only after the user explicitly requests a selected period.
  document.getElementById('go')?.addEventListener('click',()=>setTimeout(render,50));
  fromInput.addEventListener('input',hide);
  toInput.addEventListener('input',hide);
  pointInput?.addEventListener('change',hide);
  window.addEventListener('dc:points-changed',hide);
})();