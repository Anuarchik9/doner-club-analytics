(() => {
  if (window.__dcRevisionsUi) return;
  window.__dcRevisionsUi = true;

  const $ = id => document.getElementById(id);
  const button = $('revisionShow');
  const filters = document.querySelector('.filters');
  if (!button || !filters) return;

  const style = document.createElement('style');
  style.textContent = `
    .revision-status{display:none;margin-top:12px;padding:13px 15px;border:1px solid #3a342d;border-radius:14px;background:#14110e;color:#c8b7a8;font-size:12px;line-height:1.5}
    .revision-status.show{display:block}.revision-status.ok{border-color:#294739;background:#0d1712;color:#9fe4bf}.revision-status.warn{border-color:#5a4228;background:#1b140d;color:#efc699}.revision-status.err{border-color:#653232;background:#211010;color:#ffb2b2}.revision-status b{color:#fff}.revision-status .scope{display:block;margin-top:4px;color:#a99b8d}.go[disabled]{opacity:.65;cursor:wait}
    .rev-money.red{color:#ff7b7b}.rev-money.green{color:#6fdfa6}.rev-money.orange{color:#ff8b55}
    .revision-history{width:100%;border-collapse:collapse;margin-top:12px}.revision-history th{padding:10px 8px;color:#777;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:left;border-bottom:1px solid #292929}.revision-history td{padding:12px 8px;border-bottom:1px solid #222;font-size:12px}.revision-history tr:last-child td{border-bottom:0}.revision-history .num{text-align:right;font-weight:800}.revision-history .negative{color:#ff8b8b}.revision-history .positive{color:#8be0b2}
    .rev-list-block{display:grid;gap:5px}.rev-list-item{display:flex;justify-content:space-between;gap:12px;font-size:11px;line-height:1.35}.rev-list-item span:first-child{color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rev-list-item b{white-space:nowrap}.rev-list-item.neg b{color:#ff8b8b}.rev-list-item.pos b{color:#8be0b2}.rev-empty{color:#777;font-size:11px}.rev-small{font-size:10px;color:#777;margin-top:4px}
  `;
  document.head.appendChild(style);

  let status = $('revisionStatus');
  if (!status) {
    status = document.createElement('div');
    status.id = 'revisionStatus';
    status.className = 'revision-status';
    filters.insertAdjacentElement('afterend', status);
  }

  const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const monthLabel = value => {
    const m = /^(\d{4})-(\d{2})$/.exec(String(value || ''));
    if (!m) return value || '—';
    return `${monthNames[Number(m[2]) - 1]} ${m[1]}`;
  };
  const scopes = {arai:'Арай (АРАЙ общий) + Арай (Хоз.товары АРАЙ)',workshop:'ЦЕХ Основной (Цех) + ЦЕХ Основной (Цех. Хоз.товары)'};
  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const dateRu = value => {
    if (!value) return '—';
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    return m ? `${m[3]}.${m[2]}.${m[1]}` : value;
  };
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function show(kind, html) {
    status.className = `revision-status show ${kind || ''}`.trim();
    status.innerHTML = html;
  }

  function setCard(card, value, sub, cls='') {
    if (!card) return;
    const valueEl = card.querySelector('.value');
    const subEl = card.querySelector('.sub');
    if (valueEl) { valueEl.textContent = value; valueEl.className = `value rev-money ${cls}`.trim(); }
    if (subEl) subEl.textContent = sub;
  }

  function listHtml(items, kind, emptyText) {
    if (!items?.length) return `<div class="rev-empty">${escapeHtml(emptyText)}</div>`;
    return `<div class="rev-list-block">${items.slice(0,5).map(item => `<div class="rev-list-item ${kind}"><span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span><b>${money(kind === 'neg' ? item.shortage : item.surplus)}</b></div>`).join('')}</div>`;
  }

  function render(data) {
    const cards = [...document.querySelectorAll('.cards .card')];
    const s = data.summary || {};
    setCard(cards[0], dateRu(s.lastRevision), s.revisionsCount ? `${s.revisionsCount} ревиз. за период` : 'Ревизий за период нет');
    setCard(cards[1], money(s.shortage), 'Сумма отрицательных расхождений', s.shortage ? 'red' : '');
    setCard(cards[2], money(s.surplus), 'Сумма положительных расхождений', s.surplus ? 'green' : '');
    setCard(cards[3], money(s.net), 'Излишки минус недостача', s.net < 0 ? 'red' : s.net > 0 ? 'green' : '');

    const panels = [...document.querySelectorAll('.grid .panel')];
    const historyHost = panels[0]?.querySelector('.empty') || panels[0];
    if (historyHost) {
      if (data.history?.length) {
        historyHost.classList?.remove('empty');
        historyHost.innerHTML = `<table class="revision-history"><thead><tr><th>Дата</th><th class="num">Недостача</th><th class="num">Излишки</th><th class="num">Итог</th></tr></thead><tbody>${data.history.map(row => `<tr><td><b>${dateRu(row.date)}</b><div class="rev-small">${escapeHtml((row.stores || []).join(' · '))}</div></td><td class="num negative">${money(row.shortage)}</td><td class="num positive">${money(row.surplus)}</td><td class="num ${row.net < 0 ? 'negative' : row.net > 0 ? 'positive' : ''}">${money(row.net)}</td></tr>`).join('')}</tbody></table>`;
      } else {
        historyHost.classList?.add('empty');
        historyHost.innerHTML = `<div><strong>За выбранный месяц ревизии не найдены</strong>iikoServer доступен, но для выбранного контура не найдено проведённых проводок инвентаризации INVTR.</div>`;
      }
    }

    const list = panels[1]?.querySelector('.revision-list');
    if (list) {
      const recurring = data.recurringShortages || [];
      list.innerHTML = `
        <div class="revision-row"><b>TOP недостач</b><span>${listHtml(data.topShortages,'neg','Недостач нет')}</span><span class="pill">₸</span><span>${data.topShortages?.length || 0}</span></div>
        <div class="revision-row"><b>TOP излишков</b><span>${listHtml(data.topSurpluses,'pos','Излишков нет')}</span><span class="pill">₸</span><span>${data.topSurpluses?.length || 0}</span></div>
        <div class="revision-row"><b>Повторяющиеся</b><span>${recurring.length ? `<div class="rev-list-block">${recurring.slice(0,5).map(item => `<div class="rev-list-item neg"><span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span><b>${item.shortageRevisionCount}×</b></div>`).join('')}</div>` : '<div class="rev-empty">Повторяющихся недостач нет</div>'}</span><span class="pill">тренд</span><span>${recurring.length}</span></div>
        <div class="revision-row"><b>% расхождения</b><span class="muted">Нужен книжный остаток на момент ревизии</span><span class="pill">%</span><span>—</span></div>`;
    }
  }

  async function loadData(scope, period) {
    const response = await fetch(`/revision-data?scope=${encodeURIComponent(scope)}&period=${encodeURIComponent(period)}`, {headers:{Accept:'application/json'}, cache:'no-store'});
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) {
      location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
      return null;
    }
    if (!response.ok || !data?.success) throw new Error(data?.details || data?.message || `HTTP ${response.status}`);
    return data;
  }

  button.addEventListener('click', async () => {
    const select = $('revisionPoint');
    const pointKey = select?.value || 'arai';
    const point = select?.selectedOptions?.[0]?.textContent?.trim() || 'Точка';
    const period = $('revisionPeriod')?.value;
    if (!period) { show('err','Выбери месяц ревизии.'); return; }

    button.disabled = true;
    const oldText = button.textContent;
    button.textContent = 'Получаем…';
    show('', `<b>${point} · ${monthLabel(period)}</b><span class="scope">Контур: ${scopes[pointKey] || point}</span>Получаем проведённые инвентаризации из iikoServer…`);
    try {
      const data = await loadData(pointKey, period);
      if (!data) return;
      render(data);
      const stores = data.stores?.length ? data.stores.join(' + ') : (scopes[pointKey] || point);
      show('ok', `<b>${point} · ${monthLabel(period)}</b><span class="scope">${escapeHtml(stores)}</span>Найдено ревизий: <b>${data.summary?.revisionsCount || 0}</b>. Недостача: <b>${money(data.summary?.shortage)}</b>, излишки: <b>${money(data.summary?.surplus)}</b>.`);
    } catch (error) {
      show('err', `<b>Не удалось получить ревизии.</b><br>${escapeHtml(String(error?.message || error))}`);
    } finally {
      button.disabled = false;
      button.textContent = oldText;
    }
  });
})();
