(() => {
  if (window.__dcRevisionBalance) return;
  window.__dcRevisionBalance = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-accuracy{margin-top:28px}.rev-accuracy-title{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:12px}.rev-accuracy-title h2{margin:0;font-size:20px}.rev-accuracy-title span{color:#777;font-size:10px;text-align:right;line-height:1.45}
    .rev-accuracy-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.rev-accuracy-card{padding:15px 16px;border:1px solid #292929;border-radius:16px;background:linear-gradient(160deg,#151515,#0e0e0e);min-height:110px}.rev-accuracy-card span{display:block;color:#777;font-size:9px;text-transform:uppercase;letter-spacing:.07em}.rev-accuracy-card b{display:block;margin-top:8px;font-size:23px;letter-spacing:-.03em}.rev-accuracy-card small{display:block;color:#777;font-size:9px;line-height:1.4;margin-top:5px}.rev-accuracy-card .ok{color:#78dca7}.rev-accuracy-card .warn{color:#ffad72}.rev-accuracy-card .critical{color:#ff7f7f}
    .rev-accuracy-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(330px,.55fr);gap:12px;margin-top:12px}.rev-accuracy-panel{border:1px solid #292929;border-radius:18px;background:linear-gradient(160deg,#151515,#0f0f0f);padding:17px}.rev-accuracy-panel h3{margin:0;font-size:14px}.rev-accuracy-panel p{margin:5px 0 0;color:#777;font-size:9px;line-height:1.45}.rev-accuracy-chart{margin-top:10px;overflow-x:auto}.rev-accuracy-chart svg{display:block;width:100%;min-width:620px;height:auto}.rev-acc-grid{stroke:#232323;stroke-width:1}.rev-acc-threshold{stroke-width:1;stroke-dasharray:5 6}.rev-acc-threshold.ok{stroke:#315f46}.rev-acc-threshold.warn{stroke:#6b4b31}.rev-acc-path{fill:none;stroke:#ff6a2f;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.rev-acc-dot{fill:#ff6a2f;stroke:#0b0b0b;stroke-width:3}.rev-acc-label{fill:#8a8a84;font-size:9px}.rev-acc-value{fill:#ff9c72;font-size:9px;font-weight:800}.rev-accuracy-table{width:100%;border-collapse:collapse;margin-top:10px}.rev-accuracy-table th{padding:9px 7px;color:#666;font-size:8px;text-transform:uppercase;letter-spacing:.05em;text-align:left;border-bottom:1px solid #262626}.rev-accuracy-table td{padding:10px 7px;border-bottom:1px solid #202020;font-size:10px}.rev-accuracy-table tr:last-child td{border-bottom:0}.rev-accuracy-table .r{text-align:right;font-weight:750}.rev-status{display:inline-flex;padding:4px 7px;border-radius:999px;font-size:8px;font-weight:900}.rev-status.ok{color:#8be0b2;border:1px solid #29503a;background:#0d1712}.rev-status.warn{color:#ffbd8c;border:1px solid #60432d;background:#19110c}.rev-status.critical{color:#ff9898;border:1px solid #5a3030;background:#1b0f0f}.rev-balance-error{padding:15px 16px;border:1px solid #594027;border-radius:15px;background:#19120c;color:#d8b48f;font-size:10px;line-height:1.55}.rev-balance-error b{display:block;color:#fff;margin-bottom:4px}.rev-accuracy-note{margin-top:11px;color:#777;font-size:9px;line-height:1.55}.rev-accuracy-note strong{color:#aaa}
    @media(max-width:980px){.rev-accuracy-cards{grid-template-columns:1fr 1fr}.rev-accuracy-grid{grid-template-columns:1fr}}
    @media(max-width:600px){.rev-accuracy-title{align-items:flex-start;flex-direction:column}.rev-accuracy-title span{text-align:left}.rev-accuracy-cards{grid-template-columns:1fr 1fr}.rev-accuracy-card b{font-size:19px}.rev-accuracy-panel{padding:13px 10px}.rev-accuracy-table{min-width:520px}.rev-accuracy-table-wrap{overflow-x:auto}}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const pct = value => value === null || value === undefined ? '—' : `${Number(value || 0).toLocaleString('ru-RU',{maximumFractionDigits:2})}%`;
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
    return m ? `${m[3]}.${m[2]}` : String(value || '');
  };

  function statusHtml(status) {
    if (!status?.label) return '<span class="rev-status">—</span>';
    return `<span class="rev-status ${esc(status.key || '')}">${esc(status.label)}</span>`;
  }

  function ensureHost() {
    let host = document.getElementById('revisionAccuracy');
    if (!host) {
      host = document.createElement('section');
      host.id = 'revisionAccuracy';
      host.className = 'rev-accuracy';
    }
    const insights = document.getElementById('revisionInsights');
    const quality = document.getElementById('revisionQuality');
    const cards = document.querySelector('.cards');
    const anchor = insights || quality || cards;
    if (anchor && anchor.nextElementSibling !== host) anchor.insertAdjacentElement('afterend', host);
    return host;
  }

  function chartHtml(history) {
    const rows = [...(history || [])].reverse().filter(item => item.discrepancyPct !== null && item.discrepancyPct !== undefined);
    if (!rows.length) return '<div style="padding:55px 10px;text-align:center;color:#777;font-size:10px">Нет книжного остатка для построения % динамики</div>';
    const W=820,H=250,L=48,R=18,T=28,B=38;
    const values = rows.map(item => Number(item.discrepancyPct || 0));
    let max = Math.max(2.4, ...values) * 1.12;
    const x = i => rows.length === 1 ? (L+W-R)/2 : L + i*(W-L-R)/(rows.length-1);
    const y = value => T + (max-value)*(H-T-B)/max;
    const ticks = [0,1,2,max].filter((v,i,a)=>a.indexOf(v)===i).sort((a,b)=>a-b);
    const grid = ticks.map(v => `<line class="rev-acc-grid" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text class="rev-acc-label" x="${L-8}" y="${y(v)+3}" text-anchor="end">${Number(v).toLocaleString('ru-RU',{maximumFractionDigits:1})}%</text>`).join('');
    const thresholds = `<line class="rev-acc-threshold ok" x1="${L}" x2="${W-R}" y1="${y(1)}" y2="${y(1)}"/><line class="rev-acc-threshold warn" x1="${L}" x2="${W-R}" y1="${y(2)}" y2="${y(2)}"/>`;
    const points = rows.map((item,i)=>({x:x(i),y:y(Number(item.discrepancyPct||0)),item}));
    const path = points.map((p,i)=>`${i?'L':'M'} ${p.x} ${p.y}`).join(' ');
    const dots = points.map(p=>`<circle class="rev-acc-dot" cx="${p.x}" cy="${p.y}" r="5"><title>${dateRu(p.item.date)} · ${pct(p.item.discrepancyPct)} · ${money(p.item.bookValue)}</title></circle><text class="rev-acc-value" x="${p.x}" y="${Math.max(12,p.y-10)}" text-anchor="middle">${pct(p.item.discrepancyPct)}</text>`).join('');
    const labels = points.map(p=>`<text class="rev-acc-label" x="${p.x}" y="${H-13}" text-anchor="middle">${dateRu(p.item.date)}</text>`).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Процент расхождения ревизий">${grid}${thresholds}<path class="rev-acc-path" d="${path}"/>${dots}${labels}</svg>`;
  }

  function tableHtml(history) {
    const rows = (history || []).filter(item => item.bookValue !== null && item.bookValue !== undefined);
    if (!rows.length) return '<div style="color:#777;font-size:10px;margin-top:12px">Нет рассчитанных книжных остатков.</div>';
    return `<div class="rev-accuracy-table-wrap"><table class="rev-accuracy-table"><thead><tr><th>Ревизия</th><th class="r">Книжный остаток</th><th class="r">Недостача</th><th class="r">Излишки</th><th class="r">Общее расх.</th><th class="r">Статус</th></tr></thead><tbody>${rows.map(item=>`<tr><td>${dateRu(item.date)}</td><td class="r">${money(item.bookValue)}</td><td class="r">${pct(item.shortagePct)}</td><td class="r">${pct(item.surplusPct)}</td><td class="r">${pct(item.discrepancyPct)}</td><td class="r">${statusHtml(item.accuracyStatus)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function updateExistingPercentRow(data) {
    const rows = [...document.querySelectorAll('.revision-list .revision-row')];
    const row = rows.find(el => (el.querySelector('b')?.textContent || '').includes('% расхождения'));
    if (!row) return;
    const s = data.summary || {};
    const spans = row.querySelectorAll(':scope > span');
    if (!s.bookBalanceAvailable) {
      if (spans[0]) spans[0].textContent = 'Книжный остаток пока не получен';
      return;
    }
    if (spans[0]) spans[0].innerHTML = `<b style="color:#fff">${pct(s.latestDiscrepancyPct)}</b> на последней ревизии · ${money(s.latestBookValue)} книжного остатка`;
    if (spans[1]) spans[1].outerHTML = statusHtml(s.latestAccuracyStatus);
  }

  function renderUnavailable(data) {
    const host = ensureHost();
    const diag = data.balanceDiagnostics || {};
    const errors = (diag.errors || []).slice(0,3);
    host.innerHTML = `<div class="rev-accuracy-title"><h2>Точность ревизий</h2><span>Книжный остаток из iikoServer</span></div><div class="rev-balance-error"><b>% расхождения пока не рассчитан</b>Сами ревизии продолжают работать. Не удалось получить книжную стоимость склада непосредственно перед проводкой.${errors.length ? `<br><span style="color:#9c8068">${errors.map(esc).join('<br>')}</span>` : ''}</div>`;
    updateExistingPercentRow(data);
  }

  function render(data) {
    if (!data?.success) return;
    if (!data.summary?.bookBalanceAvailable) { renderUnavailable(data); return; }
    const host = ensureHost();
    const s = data.summary || {};
    host.innerHTML = `
      <div class="rev-accuracy-title"><h2>Точность ревизий</h2><span>Книжный остаток берётся непосредственно перед проводкой инвентаризации</span></div>
      <div class="rev-accuracy-cards">
        <div class="rev-accuracy-card"><span>Книжный остаток</span><b>${money(s.latestBookValue)}</b><small>Стоимость по учёту перед последней ревизией</small></div>
        <div class="rev-accuracy-card"><span>Недостача</span><b>${pct(s.latestShortagePct)}</b><small>Доля недостачи от книжной стоимости</small></div>
        <div class="rev-accuracy-card"><span>Излишки</span><b>${pct(s.latestSurplusPct)}</b><small>Доля излишков от книжной стоимости</small></div>
        <div class="rev-accuracy-card"><span>Общее расхождение</span><b class="${esc(s.latestAccuracyStatus?.key || '')}">${pct(s.latestDiscrepancyPct)}</b><small>${statusHtml(s.latestAccuracyStatus)} · недостача + излишки</small></div>
      </div>
      <div class="rev-accuracy-grid">
        <div class="rev-accuracy-panel"><h3>Расхождение по ревизиям, %</h3><p>Сравнивает недели честнее, чем абсолютная сумма в ₸: учитывает размер книжного остатка.</p><div class="rev-accuracy-chart">${chartHtml(data.history)}</div></div>
        <div class="rev-accuracy-panel"><h3>Контроль по датам</h3><p>Стоимость склада и доля расхождений для каждой проведённой ревизии.</p>${tableHtml(data.history)}</div>
      </div>
      <div class="rev-accuracy-note"><strong>Расчёт:</strong> (недостача + излишки) ÷ книжная стоимость × 100%. Баланс запрашивается через iikoServer на секунду раньше времени проводки документа. <strong>Пороги пока рабочие:</strong> ≤1% — Норма, 1–2% — Внимание, >2% — Критично. Их можно заменить внутренними нормативами Doner Club.</div>`;
    updateExistingPercentRow(data);
  }

  function schedule(data) {
    [80,220,600].forEach(ms => setTimeout(() => render(data), ms));
  }

  const previousFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await previousFetch(...args);
    try {
      const target = String(args?.[0]?.url || args?.[0] || '');
      if (target.includes('/revision-data')) {
        response.clone().json().then(data => { if (data?.success) schedule(data); }).catch(()=>{});
      }
    } catch (_) {}
    return response;
  };
})();