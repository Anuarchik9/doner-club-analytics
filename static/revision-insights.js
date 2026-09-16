(() => {
  if (window.__dcRevisionInsights) return;
  window.__dcRevisionInsights = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-insights{margin-top:28px}.rev-insights-title{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:12px}.rev-insights-title h2{margin:0;font-size:20px}.rev-insights-title span{color:#777;font-size:11px}
    .rev-insights-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.55fr);gap:13px}.rev-trend-panel,.rev-signal-panel,.rev-problems-panel{background:linear-gradient(160deg,#151515,#101010);border:1px solid #292929;border-radius:20px;box-shadow:0 18px 50px rgba(0,0,0,.22)}
    .rev-trend-panel{padding:18px 18px 12px;position:relative}.rev-trend-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:8px}.rev-trend-head h3,.rev-signal-panel h3,.rev-problems-panel h3{margin:0;font-size:15px}.rev-trend-head p{margin:5px 0 0;color:#777;font-size:10px}.rev-legend{display:flex;gap:12px;flex-wrap:wrap;color:#999;font-size:9px}.rev-legend i{display:inline-block;width:16px;height:3px;border-radius:99px;margin-right:5px;vertical-align:2px}.rev-legend .shortage{background:#ff7272}.rev-legend .surplus{background:#4bd396}.rev-legend .net{background:#ff7b3d}
    .rev-chart-wrap{position:relative;min-height:285px}.rev-chart-wrap svg{display:block;width:100%;height:auto;overflow:visible}.rev-chart-grid{stroke:#242424;stroke-width:1}.rev-chart-zero{stroke:#4a403b;stroke-width:1;stroke-dasharray:5 6}.rev-chart-axis{fill:#777;font-size:9px}.rev-chart-path{fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.rev-chart-path.shortage{stroke:#ff7272}.rev-chart-path.surplus{stroke:#4bd396}.rev-chart-path.net{stroke:#ff6a2f}.rev-chart-dot{stroke:#0b0b0b;stroke-width:3;cursor:pointer;transition:r .14s ease}.rev-chart-dot:hover{r:7}.rev-chart-dot.shortage{fill:#ff7272}.rev-chart-dot.surplus{fill:#4bd396}.rev-chart-dot.net{fill:#ff6a2f}.rev-chart-hit{fill:transparent;cursor:pointer}
    .rev-chart-tooltip{position:absolute;display:none;z-index:5;pointer-events:none;min-width:175px;padding:9px 10px;border:1px solid #3a342f;border-radius:11px;background:rgba(8,8,8,.96);box-shadow:0 10px 30px rgba(0,0,0,.45);font-size:10px;line-height:1.55}.rev-chart-tooltip.show{display:block}.rev-chart-tooltip b{display:block;color:#fff;margin-bottom:3px}.rev-chart-tooltip .neg{color:#ff8b8b}.rev-chart-tooltip .pos{color:#8be0b2}.rev-chart-tooltip .net{color:#ff9b72}.rev-chart-note{color:#777;font-size:9px;margin-top:4px}
    .rev-side{display:grid;gap:13px}.rev-signal-panel,.rev-problems-panel{padding:18px}.rev-signals{display:grid;gap:8px;margin-top:13px}.rev-signal{padding:11px 12px;border:1px solid #292929;border-radius:13px;background:#0c0c0c}.rev-signal b{display:block;font-size:11px}.rev-signal span{display:block;color:#888;font-size:9px;line-height:1.45;margin-top:4px}.rev-signal.bad{border-color:#4a2828;background:#140d0d}.rev-signal.bad b{color:#ff9292}.rev-signal.good{border-color:#254235;background:#0c1511}.rev-signal.good b{color:#8be0b2}.rev-signal.warn{border-color:#4c3625;background:#17110c}.rev-signal.warn b{color:#ffad7d}
    .rev-problems{display:grid;gap:8px;margin-top:13px}.rev-problem{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:10px 0;border-bottom:1px solid #242424}.rev-problem:last-child{border-bottom:0}.rev-problem b{display:block;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rev-problem small{display:block;color:#777;font-size:9px;margin-top:3px;line-height:1.4}.rev-problem strong{font-size:10px;color:#ff8b8b;white-space:nowrap}.rev-problem-more{margin-top:10px;padding:7px 10px;border:1px solid #343434;border-radius:99px;background:#0b0b0b;color:#ddd;font:700 10px Inter,system-ui;cursor:pointer}.rev-problem-more:hover{border-color:#5b4a41;color:#fff}
    @media(max-width:980px){.rev-insights-grid{grid-template-columns:1fr}.rev-side{grid-template-columns:1fr 1fr}}
    @media(max-width:650px){.rev-insights-title{align-items:flex-start;flex-direction:column}.rev-side{grid-template-columns:1fr}.rev-trend-head{flex-direction:column}.rev-chart-wrap{overflow-x:auto}.rev-chart-wrap svg{min-width:720px}.rev-trend-panel{padding:15px 10px 10px}}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const pct = value => `${Math.abs(Number(value || 0)).toLocaleString('ru-RU',{maximumFractionDigits:1})}%`;
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
    return m ? `${m[3]}.${m[2]}` : String(value || '');
  };

  function ensureHost() {
    let host = document.getElementById('revisionInsights');
    if (!host) {
      host = document.createElement('section');
      host.id = 'revisionInsights';
      host.className = 'rev-insights';
      const cards = document.querySelector('.cards');
      const quality = document.getElementById('revisionQuality');
      (quality || cards)?.insertAdjacentElement('afterend', host);
    } else {
      const quality = document.getElementById('revisionQuality');
      if (quality && quality.nextElementSibling !== host) quality.insertAdjacentElement('afterend', host);
    }
    return host;
  }

  function smoothPath(points) {
    if (!points.length) return '';
    if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i - 1] || points[i];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[i + 2] || p2;
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return d;
  }

  function chartHtml(data) {
    const history = [...(data.history || [])].reverse();
    if (!history.length) return '<div style="color:#777;padding:60px 10px;text-align:center">Нет ревизий для построения динамики</div>';

    const W = 920, H = 300, L = 74, R = 24, T = 28, B = 46;
    const values = history.flatMap(x => [Number(x.shortage || 0), Number(x.surplus || 0), Number(x.net || 0), 0]);
    let min = Math.min(...values), max = Math.max(...values);
    if (max === min) { max += 1; min -= 1; }
    const padding = (max - min) * .08;
    max += padding; min -= padding;
    const x = i => history.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (history.length - 1);
    const y = value => T + (max - value) * (H - T - B) / (max - min);
    const series = {
      shortage: history.map((item,i) => ({x:x(i),y:y(Number(item.shortage || 0)),date:item.date,value:Number(item.shortage||0)})),
      surplus: history.map((item,i) => ({x:x(i),y:y(Number(item.surplus || 0)),date:item.date,value:Number(item.surplus||0)})),
      net: history.map((item,i) => ({x:x(i),y:y(Number(item.net || 0)),date:item.date,value:Number(item.net||0)})),
    };

    const ticks = Array.from({length:5},(_,i) => min + (max-min)*(4-i)/4);
    const grid = ticks.map(v => `<line class="rev-chart-grid" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text class="rev-chart-axis" x="${L-10}" y="${y(v)+3}" text-anchor="end">${money(v).replace(' ₸','')}</text>`).join('');
    const zero = min < 0 && max > 0 ? `<line class="rev-chart-zero" x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}"/>` : '';
    const labels = history.map((item,i) => `<text class="rev-chart-axis" x="${x(i)}" y="${H-15}" text-anchor="middle">${dateRu(item.date)}</text>`).join('');
    const paths = Object.entries(series).map(([key,points]) => `<path class="rev-chart-path ${key}" d="${smoothPath(points)}"/>`).join('');
    const dots = Object.entries(series).flatMap(([key,points]) => points.map((p,i) => {
      const item = history[i];
      return `<circle class="rev-chart-dot ${key}" cx="${p.x}" cy="${p.y}" r="5" data-date="${esc(p.date)}" data-kind="${key}" data-shortage="${item.shortage}" data-surplus="${item.surplus}" data-net="${item.net}"/>`;
    })).join('');

    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Динамика ревизий">${grid}${zero}${paths}${dots}${labels}</svg><div class="rev-chart-tooltip" id="revisionChartTooltip"></div>`;
  }

  function signalData(data) {
    const history = data.history || [];
    const signals = [];
    const latest = history[0];
    if (latest) {
      const change = latest.shortageChangePct;
      if (change !== null && change !== undefined) {
        if (change > 0.05) signals.push({kind:'bad',title:`Недостача выросла на ${pct(change)}`,text:`Последняя ревизия: ${money(latest.shortage)} недостачи против предыдущей.`});
        else if (change < -0.05) signals.push({kind:'good',title:`Недостача снизилась на ${pct(change)}`,text:`Последняя ревизия: ${money(latest.shortage)} недостачи. Динамика улучшилась.`});
        else signals.push({kind:'warn',title:'Недостача почти без изменений',text:`Последняя ревизия: ${money(latest.shortage)}.`});
      }
      if (Number(latest.net || 0) < 0) signals.push({kind:'bad',title:`Чистый минус ${money(Math.abs(latest.net))}`,text:'На последней ревизии недостача превышает излишки.'});
      else if (Number(latest.net || 0) > 0) signals.push({kind:'good',title:`Чистый плюс ${money(latest.net)}`,text:'На последней ревизии излишки превышают недостачу.'});
    }

    const top = data.latestTopShortage;
    if (top) signals.push({kind:'warn',title:`Главный минус: ${top.name}`,text:`На последней ревизии: ${money(top.latestShortage)}.`});

    const recurring = (data.systemProblems || []).find(item => Number(item.currentShortageStreak || 0) >= 2) || (data.systemProblems || [])[0];
    if (recurring) {
      const streak = Number(recurring.currentShortageStreak || 0);
      const maxStreak = Number(recurring.maxShortageStreak || 0);
      signals.push({kind:'bad',title:`Повторяется: ${recurring.name}`,text: streak >= 2 ? `${streak} ревизии подряд сейчас · всего ${money(recurring.shortage)} недостачи.` : `Максимум ${maxStreak} ревизии подряд · всего ${money(recurring.shortage)} недостачи.`});
    }
    return signals.slice(0,4);
  }

  function problemsHtml(data) {
    const items = data.systemProblems || [];
    if (!items.length) return '<div style="color:#777;font-size:10px;margin-top:12px">Повторяющихся недостач пока не найдено.</div>';
    const row = item => {
      const current = Number(item.currentShortageStreak || 0);
      const best = Number(item.maxShortageStreak || 0);
      const count = Number(item.shortageRevisionCount || 0);
      const label = current >= 2 ? `${current} подряд сейчас` : `макс. ${best} подряд · ${count} рев.`;
      return `<div class="rev-problem"><div><b title="${esc(item.name)}">${esc(item.name)}</b><small>${label}</small></div><strong>${money(item.shortage)}</strong></div>`;
    };
    const first = items.slice(0,5).map(row).join('');
    const rest = items.slice(5).map(row).join('');
    return `${first}${rest ? `<div id="revSystemExtra" hidden>${rest}</div><button type="button" class="rev-problem-more" id="revSystemMore" data-total="${items.length}">Показать все ${items.length}</button>` : ''}`;
  }

  function render(data) {
    if (!data?.success) return;
    const host = ensureHost();
    const signals = signalData(data);
    host.innerHTML = `
      <div class="rev-insights-title"><h2>Динамика и сигналы</h2><span>Клик по точке графика открывает соответствующую ревизию</span></div>
      <div class="rev-insights-grid">
        <div class="rev-trend-panel">
          <div class="rev-trend-head"><div><h3>Недостача / излишки / чистый итог</h3><p>По каждой проведённой ревизии выбранного месяца</p></div><div class="rev-legend"><span><i class="shortage"></i>Недостача</span><span><i class="surplus"></i>Излишки</span><span><i class="net"></i>Чистый итог</span></div></div>
          <div class="rev-chart-wrap">${chartHtml(data)}</div>
          <div class="rev-chart-note">«Подряд» считается по последовательности проведённых ревизий выбранного направления.</div>
        </div>
        <div class="rev-side">
          <div class="rev-signal-panel"><h3>Автоматические сигналы</h3><div class="rev-signals">${signals.length ? signals.map(s => `<div class="rev-signal ${s.kind}"><b>${esc(s.title)}</b><span>${esc(s.text)}</span></div>`).join('') : '<div style="color:#777;font-size:10px">Пока недостаточно ревизий для сигналов.</div>'}</div></div>
          <div class="rev-problems-panel"><h3>Системные проблемы</h3><div class="rev-problems">${problemsHtml(data)}</div></div>
        </div>
      </div>`;
    bindChart(host);
  }

  function openRevision(date) {
    const attempt = tries => {
      const row = document.querySelector(`.revision-history tr.rev-master[data-revision-date="${date}"]`);
      if (row) {
        if (!row.classList.contains('is-open')) row.click();
        row.scrollIntoView({behavior:'smooth',block:'center'});
        return;
      }
      if (tries > 0) setTimeout(() => attempt(tries-1), 120);
    };
    attempt(6);
  }

  function bindChart(host) {
    const wrap = host.querySelector('.rev-chart-wrap');
    const tip = host.querySelector('#revisionChartTooltip');
    if (!wrap || !tip) return;
    wrap.addEventListener('pointermove', event => {
      const dot = event.target.closest('.rev-chart-dot');
      if (!dot) { tip.classList.remove('show'); return; }
      const rect = wrap.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(dot.dataset.date)}</b><span class="neg">Недостача: ${money(dot.dataset.shortage)}</span><br><span class="pos">Излишки: ${money(dot.dataset.surplus)}</span><br><span class="net">Итог: ${money(dot.dataset.net)}</span>`;
      tip.style.left = `${Math.min(event.clientX - rect.left + 12, Math.max(8, rect.width - 190))}px`;
      tip.style.top = `${Math.max(8, event.clientY - rect.top - 78)}px`;
      tip.classList.add('show');
    });
    wrap.addEventListener('pointerleave', () => tip.classList.remove('show'));
    wrap.addEventListener('click', event => {
      const dot = event.target.closest('.rev-chart-dot');
      if (!dot?.dataset.date) return;
      openRevision(dot.dataset.date);
    });
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('#revSystemMore');
    if (!button) return;
    const extra = document.getElementById('revSystemExtra');
    if (!extra) return;
    const opening = extra.hidden;
    extra.hidden = !opening;
    button.textContent = opening ? 'Скрыть' : `Показать все ${button.dataset.total || ''}`.trim();
  });

  const previousFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await previousFetch(...args);
    try {
      const target = String(args?.[0]?.url || args?.[0] || '');
      if (target.includes('/revision-data')) {
        response.clone().json().then(data => {
          if (data?.success) {
            window.__dcRevisionInsightsData = data;
            setTimeout(() => render(data), 90);
          }
        }).catch(() => {});
      }
    } catch (_) {}
    return response;
  };
})();