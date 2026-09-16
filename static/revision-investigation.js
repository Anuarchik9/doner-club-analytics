(() => {
  if (window.__dcRevisionInvestigation) return;
  window.__dcRevisionInvestigation = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-investigation{margin-top:28px;padding:20px;border:1px solid #3a302a;border-radius:18px;background:linear-gradient(160deg,#15110f,#0f0f0f)}
    .rev-investigation-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.rev-investigation-head h3{margin:0;font-size:19px}.rev-investigation-head p{margin:6px 0 0;color:#8b8179;font-size:11px;line-height:1.55;max-width:880px}.rev-investigation-tools{display:flex;gap:8px;flex-wrap:wrap}
    .rev-investigation-btn{border:1px solid #3b3733;background:#101010;color:#ddd;border-radius:11px;padding:9px 12px;font:800 10px Inter,system-ui;cursor:pointer}.rev-investigation-btn:hover{border-color:#6a4a39;color:#fff}.rev-investigation-btn.good{border-color:#28513d;color:#9fe4bf;background:#0c1511}
    .rev-investigation-alert{margin-top:14px;padding:14px 15px;border:1px solid #51372a;border-radius:14px;background:#19100d;color:#cdb9ab;font-size:11px;line-height:1.6}.rev-investigation-alert b{color:#fff}.rev-investigation-alert strong{color:#ff9c72}
    .rev-investigation-list{display:grid;gap:9px;margin-top:14px}.rev-question{border:1px solid #292929;border-radius:14px;background:#101010;overflow:hidden}.rev-question-top{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:11px;align-items:start;padding:13px 14px}.rev-question-num{display:grid;place-items:center;width:28px;height:28px;border-radius:9px;background:rgba(255,90,31,.13);color:#ff8e61;font-size:10px;font-weight:900}.rev-question b{display:block;font-size:12px;line-height:1.45}.rev-question small{display:block;color:#777;font-size:9.5px;line-height:1.5;margin-top:4px}.rev-question-check{display:flex;align-items:center;gap:6px;color:#888;font-size:9px;white-space:nowrap;cursor:pointer}.rev-question-check input{accent-color:#4bd396}.rev-question.is-done{border-color:#284535;background:#0d1410}.rev-question.is-done .rev-question-num{background:rgba(75,211,150,.12);color:#8be0b2}.rev-question-answer{display:block;width:calc(100% - 28px);margin:0 14px 13px;min-height:58px;resize:vertical;border:1px solid #2c2c2c;border-radius:10px;background:#0a0a0a;color:#e8e8e3;padding:10px 11px;font:11px/1.5 Inter,system-ui;outline:none}.rev-question-answer:focus{border-color:#654431}.rev-question-answer::placeholder{color:#555}
    .rev-next-revision{margin-top:24px}.rev-next-revision h3{margin:0;font-size:18px}.rev-next-revision>p{margin:5px 0 0;color:#7c7c76;font-size:10px;line-height:1.5}.rev-protocol{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px}.rev-protocol-item{display:grid;grid-template-columns:22px minmax(0,1fr);gap:10px;padding:12px 13px;border:1px solid #292929;border-radius:13px;background:#0f0f0f;cursor:pointer}.rev-protocol-item input{margin-top:2px;accent-color:#4bd396}.rev-protocol-item b{display:block;font-size:10.5px}.rev-protocol-item span{display:block;color:#777;font-size:9px;line-height:1.45;margin-top:3px}.rev-protocol-item.is-done{border-color:#284535;background:#0d1410}.rev-investigation-foot{margin-top:12px;padding-top:11px;border-top:1px solid #28231f;color:#766d67;font-size:9px;line-height:1.5}
    @media(max-width:900px){.rev-investigation-head{flex-direction:column}.rev-protocol{grid-template-columns:1fr}}
    @media(max-width:600px){.rev-investigation{padding:14px}.rev-question-top{grid-template-columns:28px minmax(0,1fr)}.rev-question-check{grid-column:2}.rev-investigation-tools{width:100%}.rev-investigation-btn{flex:1}}
  `;
  document.head.appendChild(style);

  const money = v => `${Math.round(Number(v||0)).toLocaleString('ru-RU')} ₸`;
  const qty = v => `${Number(v||0)>0?'+':Number(v||0)<0?'−':''}${Math.abs(Number(v||0)).toLocaleString('ru-RU',{maximumFractionDigits:3})}`;
  const esc = v => String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = v => {const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(v||''));return m?`${m[3]}.${m[2]}.${m[1]}`:String(v||'');};

  function aggregateLatest(data,name){
    const revisions=(data?.revisionDetails||[]).slice().sort((a,b)=>String(b.date).localeCompare(String(a.date)));
    for(const revision of revisions){
      const docs=[];
      for(const doc of revision.documents||[]){
        let q=0,s=0,p=0,n=0,unit='',matched=false;
        for(const line of doc.products||[]){
          if(String(line.name||'').trim()!==name) continue;
          matched=true; const lq=Number(line.quantityDelta||0), ls=Number(line.shortage||0), lp=Number(line.surplus||0), ln=Number(line.net ?? (lp-ls));
          q+=lq;s+=ls;p+=lp;n+=ln;if(!unit&&line.unit)unit=String(line.unit);
        }
        if(matched)docs.push({document:String(doc.document||'Без номера'),store:String(doc.store||'Склад не определён'),quantityDelta:q,shortage:s,surplus:p,net:n,unit});
      }
      if(docs.length)return {date:revision.date,docs};
    }
    return null;
  }

  function mixedStats(data,name){
    let totalShort=0,totalSurplus=0,mixed=0,rows=0,shortageRows=0,surplusRows=0;
    for(const revision of data?.revisionDetails||[]){
      let s=0,p=0,found=false;
      for(const doc of revision.documents||[]){for(const line of doc.products||[]){if(String(line.name||'').trim()===name){found=true;s+=Number(line.shortage||0);p+=Number(line.surplus||0);}}}
      if(!found)continue; rows++; totalShort+=s; totalSurplus+=p;if(s>.005)shortageRows++;if(p>.005)surplusRows++;if(s>.005&&p>.005)mixed++;
    }
    const gross=totalShort+totalSurplus, net=totalSurplus-totalShort, comp=gross>0?(gross-Math.abs(net))/gross*100:0;
    return {totalShort,totalSurplus,mixed,rows,shortageRows,surplusRows,comp};
  }

  function makeQuestions(data,name,latest,stats){
    const docs=latest?.docs||[];
    const neg=docs.filter(d=>d.net<-.005).sort((a,b)=>a.net-b.net)[0];
    const pos=docs.filter(d=>d.net>.005).sort((a,b)=>b.net-a.net)[0];
    const date=dateRu(latest?.date);
    const specific = neg&&pos
      ? `Что произошло между документами ${neg.document} (${qty(neg.quantityDelta)} ${neg.unit||'ед.'}, ${money(neg.net)}) и ${pos.document} (${qty(pos.quantityDelta)} ${pos.unit||'ед.'}, +${money(pos.net)}) ${date}? Один документ исправлял другой, это были разные этапы учёта или независимые операции?`
      : `Какие именно документы сформировали отклонение по позиции «${name}» ${date}, и зачем был создан каждый из них?`;
    const orderDocs = docs.length ? docs.map(d=>d.document).join(', ') : 'документы этой ревизии';
    return [
      {q:specific,why:'Нужно восстановить причинно-следственную связь, а не просто увидеть два противоположных числа.'},
      {q:`Кто и во сколько создал и провёл ${orderDocs}? В какой последовательности они были проведены?`,why:'Время и порядок проведения покажут, был ли плюс корректировкой минуса, поздним движением или отдельной операцией.'},
      {q:`Какое фактическое количество «${name}» реально увидели при пересчёте? Как его измеряли: весы, штуки, тара, брутто/нетто?`,why:'Нужно отделить ошибку фактического пересчёта от ошибки учётной единицы.'},
      {q:'На момент пересчёта были непроведённые приходы, списания, перемещения, акты производства или возвраты по этой позиции?',why:'Документ, проведённый после фактического счёта, может создать искусственный минус или плюс.'},
      {q:`Не была ли часть «${name}» уже передана в полуфабрикат, производство или другую номенклатуру, но соответствующий документ ещё не был проведён?`,why:'Для сырья и полуфабрикатов важно понимать момент перехода из одной стадии учёта в другую.'},
      {q:'Есть ли другая карточка номенклатуры, под которой фактически мог быть посчитан тот же товар? Какие позиции считаются связанными с этой?',why:'Это проверка возможного пересорта, дублей номенклатуры и неправильной карточки товара.'},
      {q:`Почему по этой позиции одновременно есть недостача и излишки в ${stats.mixed} из ${stats.rows} ревизий? Это нормальная схема работы документов или уже известная учётная проблема?`,why:`Внутренняя компенсация сейчас около ${stats.comp.toLocaleString('ru-RU',{maximumFractionDigits:1})}% — такой повторяющийся рисунок важно объяснить процессом.`},
      {q:'Перед проводкой ревизии крупные отклонения пересчитывали второй раз? Кто подтвердил итоговое количество?',why:'Повторный независимый пересчёт нужен, чтобы исключить ошибку ввода, весов или человеческий фактор.'},
      {q:'После проводки кто проверил итоговые отклонения и почему эта позиция продолжала повторяться из ревизии в ревизию?',why:'Нам нужно понять, где сейчас обрывается контроль: на пересчёте, проверке, корректировке или последующем контроле.'},
      {q:'Какую конкретную причину мы фиксируем по этой ревизии и какое одно изменение в процессе должно не допустить повторения на следующей?',why:'Ответ должен закончиться действием и владельцем действия, иначе расследование останется просто обсуждением цифр.'}
    ];
  }

  const protocol=[
    ['Зафиксировать время и ответственного','Записать время начала и окончания пересчёта и кто именно считал/проводил документы.'],
    ['Закрыть незавершённые движения','До пересчёта провести или отдельно зафиксировать все приходы, списания, перемещения и производство.'],
    ['Не двигать товар во время счёта','Если движение остановить нельзя — записывать каждое движение, которое произошло во время ревизии.'],
    ['Зафиксировать книжный остаток до проводки','Сохранить учётный остаток до корректирующих документов, чтобы потом понимать исходную точку.'],
    ['Проверить единицу измерения и тару','Для весовых позиций убедиться, что кг/шт., тара, брутто и нетто используются одинаково в факте и в iiko.'],
    ['Пересчитать крупные отклонения','Позиции с заметным минусом/плюсом пересчитать повторно до проводки, желательно вторым человеком.'],
    ['Проверить сырьё ↔ полуфабрикат','Перед итоговой проводкой убедиться, что переходы в производство и связанные номенклатуры отражены документами.'],
    ['Подписать причину каждого крупного расхождения','Не оставлять большой минус/плюс без короткого комментария: пересорт, поздний документ, ошибка единицы, фактическая недостача и т.д.'],
    ['Проверить итог после проводки','После проведения открыть TOP отклонений и убедиться, что противоположные документы объяснены, а не просто взаимно скрыли друг друга.'],
    ['Назначить контроль следующей ревизии','Для системной позиции заранее отметить, что именно проверяем повторно и какой результат будет считаться исправлением.']
  ];

  function storageKey(name,date){
    const scope=document.getElementById('revisionPoint')?.value||'scope';
    const period=document.getElementById('revisionPeriod')?.value||'period';
    return `dc-revision-investigation-v1:${scope}:${period}:${name}:${date||''}`;
  }
  function load(key){try{return JSON.parse(localStorage.getItem(key)||'{}')}catch(_){return {}}}
  function save(key,state){try{localStorage.setItem(key,JSON.stringify(state))}catch(_){}}

  function build(data,name){
    const drawer=document.getElementById('revProductDrawer');
    if(!drawer||!drawer.classList.contains('show')||drawer.querySelector('.rev-investigation'))return;
    const latest=aggregateLatest(data,name); if(!latest)return;
    const stats=mixedStats(data,name), questions=makeQuestions(data,name,latest,stats), key=storageKey(name,latest.date), state=load(key);
    const section=document.createElement('section');section.className='rev-investigation';section.dataset.storageKey=key;
    const neg=latest.docs.filter(d=>d.net<-.005).sort((a,b)=>a.net-b.net)[0], pos=latest.docs.filter(d=>d.net>.005).sort((a,b)=>b.net-a.net)[0];
    const focus=neg&&pos ? `Главный фокус: <strong>${esc(neg.document)}</strong> дал ${money(neg.net)}, а <strong>${esc(pos.document)}</strong> дал +${money(pos.net)} по той же позиции в ту же дату.` : 'Главный фокус — восстановить последовательность документов и фактического пересчёта.';
    section.innerHTML=`
      <div class="rev-investigation-head"><div><h3>Вопросы человеку, который проводил ревизию</h3><p>Задача этого блока — не найти виноватого, а восстановить, что реально происходило с товаром и документами. Ответы должны привести к конкретному изменению процесса.</p></div><div class="rev-investigation-tools"><button class="rev-investigation-btn" type="button" data-copy-questions>Скопировать вопросы</button><button class="rev-investigation-btn good" type="button" data-copy-report>Скопировать ответы</button></div></div>
      <div class="rev-investigation-alert"><b>Что сейчас нужно выяснить.</b> ${focus} По позиции одновременно есть минусы и плюсы в <strong>${stats.mixed} из ${stats.rows}</strong> ревизий, поэтому сначала восстанавливаем процесс учёта и движения товара.</div>
      <div class="rev-investigation-list">${questions.map((x,i)=>{const done=!!state[`q${i}Done`],answer=state[`q${i}Answer`]||'';return `<div class="rev-question ${done?'is-done':''}" data-q="${i}"><div class="rev-question-top"><div class="rev-question-num">${i+1}</div><div><b>${esc(x.q)}</b><small>Зачем спрашиваем: ${esc(x.why)}</small></div><label class="rev-question-check"><input type="checkbox" ${done?'checked':''}> ответ получен</label></div><textarea class="rev-question-answer" placeholder="Запишите ответ, факт или ссылку на подтверждающий документ...">${esc(answer)}</textarea></div>`}).join('')}</div>
      <div class="rev-next-revision"><h3>Что обязательно сделать на следующей ревизии</h3><p>Это уже не вопросы, а короткий рабочий протокол, чтобы та же проблема не повторилась незамеченной.</p><div class="rev-protocol">${protocol.map((x,i)=>{const done=!!state[`p${i}`];return `<label class="rev-protocol-item ${done?'is-done':''}" data-p="${i}"><input type="checkbox" ${done?'checked':''}><div><b>${esc(x[0])}</b><span>${esc(x[1])}</span></div></label>`}).join('')}</div></div>
      <div class="rev-investigation-foot">Ответы и отметки автоматически сохраняются в этом браузере для выбранной точки, периода, товара и даты ревизии. Это рабочий журнал разбора; подтверждённую причину после проверки лучше также зафиксировать во внутреннем регламенте/комментарии к ревизии.</div>`;

    const actions=[...drawer.querySelectorAll('.rev-product-section')].find(s=>(s.querySelector('h3')?.textContent||'').includes('Что проверить'));
    if(actions) actions.insertAdjacentElement('beforebegin',section); else drawer.querySelector('.rev-product-body')?.appendChild(section);

    section.addEventListener('input',event=>{
      const q=event.target.closest('.rev-question'); if(!q)return; const i=q.dataset.q; const st=load(key);
      if(event.target.matches('textarea'))st[`q${i}Answer`]=event.target.value;
      if(event.target.matches('input[type=checkbox]')){st[`q${i}Done`]=event.target.checked;q.classList.toggle('is-done',event.target.checked)}
      save(key,st);
    });
    section.addEventListener('change',event=>{
      const p=event.target.closest('.rev-protocol-item'); if(!p)return; const st=load(key);st[`p${p.dataset.p}`]=event.target.checked;p.classList.toggle('is-done',event.target.checked);save(key,st);
    });
    section.querySelector('[data-copy-questions]')?.addEventListener('click',async event=>{
      const text=`Разбор ревизии ${dateRu(latest.date)} — ${name}\n\n`+questions.map((x,i)=>`${i+1}. ${x.q}`).join('\n');
      try{await navigator.clipboard.writeText(text);event.currentTarget.textContent='Скопировано';setTimeout(()=>event.currentTarget.textContent='Скопировать вопросы',1200)}catch(_){ }
    });
    section.querySelector('[data-copy-report]')?.addEventListener('click',async event=>{
      const st=load(key);const text=`Разбор ревизии ${dateRu(latest.date)} — ${name}\n\n`+questions.map((x,i)=>`${i+1}. ${x.q}\nОтвет: ${st[`q${i}Answer`]||'—'}`).join('\n\n');
      try{await navigator.clipboard.writeText(text);event.currentTarget.textContent='Скопировано';setTimeout(()=>event.currentTarget.textContent='Скопировать ответы',1200)}catch(_){ }
    });
  }

  function enhance(){
    const drawer=document.getElementById('revProductDrawer'); if(!drawer||!drawer.classList.contains('show'))return;
    const data=window.__dcRevisionDetailData; if(!data)return;
    const name=(drawer.querySelector('.rev-product-head h2')?.textContent||'').trim(); if(name)build(data,name);
  }
  const observer=new MutationObserver(()=>setTimeout(enhance,20));observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
})();
