(() => {
  if (window.__dcSmartProgress) return;
  window.__dcSmartProgress = true;

  const style = document.createElement('style');
  style.textContent = `
    .dc-progress-wrap{width:min(560px,82vw);text-align:left}
    .dc-progress-top{display:flex;align-items:center;justify-content:space-between;gap:16px}
    .dc-progress-title{font-size:14px;font-weight:900;color:#fff}
    .dc-progress-pct{font-size:24px;font-weight:950;letter-spacing:-.04em;color:#ff7d49;min-width:58px;text-align:right}
    .dc-progress-track{height:9px;margin-top:12px;background:#262626;border-radius:999px;overflow:hidden;border:1px solid #313131}
    .dc-progress-fill{height:100%;width:0;background:linear-gradient(90deg,#ff5a1f,#ff915d);border-radius:999px;transition:width .28s ease}
    .dc-progress-stage{margin-top:10px;font-size:11px;color:#d0c7c1;font-weight:750;line-height:1.4}
    .dc-progress-meta{margin-top:5px;color:#777;font-size:10px;line-height:1.45}
    .dc-progress-inline{display:none;margin-top:12px;padding:14px 15px;border:1px solid #3d332d;border-radius:14px;background:linear-gradient(135deg,#15110f,#101010)}
    .dc-progress-inline.show{display:block}
    .dc-progress-inline.done{border-color:#294739;background:#0d1712}
    .dc-progress-inline.error{border-color:#653232;background:#211010}
    .dc-progress-inline .dc-progress-wrap{width:100%}
    .dc-progress-inline .dc-progress-pct{font-size:20px}
    #loading .box.dc-progress-box{min-width:min(620px,88vw);padding:24px 26px;text-align:left}
    #loading .box.dc-progress-box .spin{display:none!important}
    @media(max-width:600px){.dc-progress-wrap{width:86vw}.dc-progress-pct{font-size:20px}.dc-progress-title{font-size:13px}}
  `;
  document.head.appendChild(style);

  const state = {
    active:false,
    kind:null,
    percent:0,
    target:0,
    startedAt:0,
    startedRequests:0,
    finishedRequests:0,
    timer:null,
    requestNames:new Map(),
    revisionSummary:null,
  };

  const $ = id => document.getElementById(id);
  const clamp = (v,a,b) => Math.max(a,Math.min(b,v));

  function stageFor(kind,p){
    if(p>=100) return 'Готово';
    if(kind==='revisions'){
      if(p<15)return 'Подключаемся к iikoServer';
      if(p<34)return 'Ищем документы инвентаризации';
      if(p<55)return 'Разбираем проводки и позиции';
      if(p<73)return 'Считаем недостачи и излишки';
      if(p<89)return 'Сверяем книжные остатки';
      return 'Собираем управленческий вывод';
    }
    if(p<15)return 'Подключаемся к iiko';
    if(p<38)return 'Загружаем продажи и документы';
    if(p<60)return 'Считаем выручку и товары';
    if(p<80)return 'Загружаем чеки и гостей';
    return 'Собираем аналитику и графики';
  }

  function ensureRevisionHost(){
    let host=$('dcRevisionProgress');
    if(!host){
      host=document.createElement('div');
      host.id='dcRevisionProgress';
      host.className='dc-progress-inline';
      const anchor=$('revisionStatus') || document.querySelector('.filters');
      if(anchor) anchor.insertAdjacentElement('afterend',host);
    }
    return host;
  }

  function markup(title){
    return `<div class="dc-progress-wrap"><div class="dc-progress-top"><div class="dc-progress-title">${title}</div><div class="dc-progress-pct">0%</div></div><div class="dc-progress-track"><div class="dc-progress-fill"></div></div><div class="dc-progress-stage">Подготавливаем запрос…</div><div class="dc-progress-meta">Ожидание ответа iiko</div></div>`;
  }

  function dashboardHost(){
    const loading=$('loading');
    if(!loading)return null;
    let box=loading.querySelector('.box');
    if(!box)return null;
    if(!box.classList.contains('dc-progress-box')){
      box.classList.add('dc-progress-box');
      box.innerHTML=markup('Загрузка продаж и аналитики');
    }
    return box;
  }

  function currentHost(){
    return state.kind==='revisions' ? ensureRevisionHost() : dashboardHost();
  }

  function metaText(){
    const elapsed=Math.max(0,Math.floor((Date.now()-state.startedAt)/1000));
    if(state.kind==='revisions'){
      if(state.revisionSummary){
        const s=state.revisionSummary;
        const docs=Number(s.documentsCount||0).toLocaleString('ru-RU');
        const dates=Number(s.revisionsCount||0).toLocaleString('ru-RU');
        return `Получено: ${docs} документов · ${dates} дат ревизий · ${elapsed} с`;
      }
      return `iikoServer обрабатывает выбранный период · прошло ${elapsed} с`;
    }
    const req=state.startedRequests ? `Ответов: ${state.finishedRequests} из ${state.startedRequests}` : 'Подготавливаем запросы';
    return `${req} · прошло ${elapsed} с`;
  }

  function paint(){
    const host=currentHost();
    if(!host)return;
    const pct=host.querySelector('.dc-progress-pct');
    const fill=host.querySelector('.dc-progress-fill');
    const stage=host.querySelector('.dc-progress-stage');
    const meta=host.querySelector('.dc-progress-meta');
    if(pct)pct.textContent=`${Math.round(state.percent)}%`;
    if(fill)fill.style.width=`${clamp(state.percent,0,100)}%`;
    if(stage)stage.textContent=stageFor(state.kind,state.percent);
    if(meta)meta.textContent=metaText();
    if(state.kind==='revisions'){
      host.classList.add('show');
      const button=$('revisionShow');
      if(button && button.disabled) button.textContent=`${Math.round(state.percent)}%`;
    }
  }

  function bump(value){
    if(!state.active)return;
    state.target=Math.max(state.target,clamp(value,0,99));
  }

  function start(kind){
    if(state.active && state.kind===kind)return;
    clearInterval(state.timer);
    state.active=true; state.kind=kind; state.percent=3; state.target=8; state.startedAt=Date.now();
    state.startedRequests=0; state.finishedRequests=0; state.requestNames.clear(); state.revisionSummary=null;
    const host=currentHost();
    if(kind==='revisions'){
      host.className='dc-progress-inline show';
      host.innerHTML=markup('Загрузка ревизий');
    }else if(host){
      const wrap=host.querySelector('.dc-progress-wrap');
      if(!wrap)host.innerHTML=markup('Загрузка продаж и аналитики');
    }
    paint();
    state.timer=setInterval(()=>{
      if(!state.active)return;
      const elapsed=(Date.now()-state.startedAt)/1000;
      const timeTarget = elapsed<1?12 : elapsed<2.5?24 : elapsed<5?42 : elapsed<8?59 : elapsed<12?73 : elapsed<18?84 : 91;
      state.target=Math.max(state.target,timeTarget);
      if(state.percent < state.target) state.percent += Math.max(.5,(state.target-state.percent)*.12);
      if(state.percent>98)state.percent=98;
      paint();
    },180);
  }

  function finish(error=false){
    if(!state.active)return;
    clearInterval(state.timer); state.timer=null;
    state.percent=100; state.target=100; paint();
    const host=currentHost();
    if(state.kind==='revisions' && host){
      host.classList.toggle('done',!error); host.classList.toggle('error',!!error);
      const stage=host.querySelector('.dc-progress-stage');
      if(stage)stage.textContent=error?'Загрузка завершилась с ошибкой':'Готово';
      const button=$('revisionShow'); if(button) button.textContent='Показать';
      setTimeout(()=>{host.classList.remove('show','done','error');},900);
    }
    state.active=false;
  }

  function relevantPath(raw){
    try{
      const u=new URL(String(raw?.url||raw||''),location.href);
      if(u.origin!==location.origin)return null;
      const p=u.pathname;
      if(p.startsWith('/static/')||p==='/departments'||p==='/login')return null;
      return p;
    }catch(_){return null;}
  }

  const nativeFetch=window.fetch.bind(window);
  window.fetch=async(...args)=>{
    const path=relevantPath(args[0]);
    let tracked=false;
    if(state.active && path){
      if(state.kind==='revisions' && path==='/revision-data') tracked=true;
      if(state.kind==='dashboard' && path!=='/revision-data') tracked=true;
    }
    if(tracked){
      state.startedRequests++;
      bump(state.kind==='revisions'?22:Math.min(70,18+state.startedRequests*7));
      paint();
    }
    try{
      const response=await nativeFetch(...args);
      if(tracked){
        state.finishedRequests++;
        if(state.kind==='dashboard'){
          const ratio=state.startedRequests?state.finishedRequests/state.startedRequests:0;
          bump(24+ratio*64);
        }else{
          bump(94);
          try{
            const data=await response.clone().json();
            if(data?.summary) state.revisionSummary=data.summary;
          }catch(_){}
        }
        paint();
      }
      return response;
    }catch(error){
      if(tracked){state.finishedRequests++;paint();}
      throw error;
    }
  };

  const loading=$('loading');
  if(loading){
    dashboardHost();
    const obs=new MutationObserver(()=>{
      const shown=loading.classList.contains('show');
      if(shown && !state.active) start('dashboard');
      if(!shown && state.active && state.kind==='dashboard'){
        state.percent=98; paint();
        setTimeout(()=>finish(false),120);
      }
    });
    obs.observe(loading,{attributes:true,attributeFilter:['class']});
  }

  const revisionButton=$('revisionShow');
  if(revisionButton){
    ensureRevisionHost();
    const obs=new MutationObserver(()=>{
      if(revisionButton.disabled && !state.active) start('revisions');
      if(!revisionButton.disabled && state.active && state.kind==='revisions'){
        const status=$('revisionStatus');
        const error=!!status?.classList.contains('err');
        state.percent=98; paint();
        setTimeout(()=>finish(error),130);
      }
    });
    obs.observe(revisionButton,{attributes:true,attributeFilter:['disabled']});
  }
})();