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
    .revision-status.show{display:block}.revision-status.ok{border-color:#294739;background:#0d1712;color:#9fe4bf}.revision-status.warn{border-color:#5a4228;background:#1b140d;color:#efc699}.revision-status.err{border-color:#653232;background:#211010;color:#ffb2b2}.revision-status b{color:#fff}.revision-status .scope{display:block;margin-top:4px;color:#a99b8d}.revision-status .diag{display:block;margin-top:7px;color:#9b8e82;font-size:10px}.go[disabled]{opacity:.65;cursor:wait}
    .rev-money.red{color:#ff7b7b}.rev-money.green{color:#6fdfa6}.rev-money.orange{color:#ff8b55}
    .revision-history{width:100%;border-collapse:collapse;margin-top:12px}.revision-history th{padding:10px 8px;color:#777;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:left;border-bottom:1px solid #292929}.revision-history td{padding:12px 8px;border-bottom:1px solid #222;font-size:12px}.revision-history tr:last-child td{border-bottom:0}.revision-history .num{text-align:right;font-weight:800}.revision-history .negative{color:#ff8b8b}.revision-history .positive{color:#8be0b2}
    .revision-row{grid-template-columns:120px minmax(0,1fr) auto!important;align-items:start!important}
    .rev-list-block{display:grid;gap:6px;min-width:0}.rev-list-item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;font-size:11px;line-height:1.35}.rev-list-item span:first-child{color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rev-list-item b{white-space:nowrap}.rev-list-item.neg b,.rev-list-item.repeat b{color:#ff8b8b}.rev-list-item.pos b{color:#8be0b2}.rev-empty{color:#777;font-size:11px}.rev-small{font-size:10px;color:#777;margin-top:4px;line-height:1.35}.rev-list-extra[hidden]{display:none}.rev-list-extra{display:grid;gap:6px}.rev-more{justify-self:start;margin-top:5px;padding:6px 10px;border:1px solid #343434;border-radius:999px;background:#0b0b0b;color:#ddd;font:700 10px Inter,system-ui;cursor:pointer}.rev-more:hover{border-color:#5b4a41;color:#fff}
    .rev-quality{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}.rev-quality-card{padding:13px 15px;border:1px solid #242424;border-radius:14px;background:#0e0e0e}.rev-quality-card span{display:block;color:#777;font-size:10px;text-transform:uppercase;letter-spacing:.06em}.rev-quality-card b{display:block;margin-top:5px;font-size:18px}.rev-quality-card small{display:block;margin-top:3px;color:#777;font-size:10px;line-height:1.35}
    @media(max-width:900px){.rev-quality{grid-template-columns:1fr 1fr}}
    @media(max-width:600px){.revision-row{grid-template-columns:1fr auto!important}.revision-row>b{grid-column:1/-1}.rev-quality{grid-template-columns:1fr 1fr}.revision-history{font-size:10px}.revision-history th,.revision-history td{padding:8px 5px}}
  `;
  document.head.appendChild(style);

  let status = $('revisionStatus');
  if (!status) {
    status = document.createElement('div');
    status.id = 'revisionStatus';
    status.className = 'revision-status';
    filters.insertAdjacentElement('afterend', status);
  }

  const cardsSection = document.querySelector('.cards');
  let quality = $('revisionQuality');
  if (!quality && cardsSection) {
    quality = document.createElement('div');
    quality.id = 'revisionQuality';
    quality.className = 'rev-quality';
    cardsSection.insertAdjacentElement('afterend', quality);
  }

  const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const monthLabel = value => {
    const m = /^(\d{4})-(\d{2})$/.exec(String(value || ''));
    if (!m) return value || '—';
    return `${monthNames[Number(m[2]) - 1]} ${m[1]}`;
  };
  const scopes = {arai:'Арай (АРАЙ общий)',arai_kitchen:'Арай (АРАЙ общий) · кухня',arai_counter:'Арай (АРАЙ общий) · напитки и товары точки',workshop:'ЦЕХ Основной (Цех) + ЦЕХ Основной (Цех. Хоз.товары)'};
  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const pct = value => `${Number(value || 0).toLocaleString('ru-RU',{maximumFractionDigits:1})}%`;
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

  function itemValue(item, kind) {
    if (kind === 'neg') return money(item.shortage);
    if (kind === 'pos') return money(item.surplus);
    return `${Number(item.shortageRevisionCount || 0)} рев.`;
  }

  function listHtml(items, kind, emptyText, key) {
    if (!items?.length) return `<div class="rev-empty">${escapeHtml(emptyText)}</div>`;
    const row = item => `<div class="rev-list-item ${kind}"><span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span><b>${itemValue(item,kind)}</b></div>`;
    const first = items.slice(0,5).map(row).join('');
    const rest = items.slice(5).map(row).join('');
    const more = items.length > 5
      ? `<div class="rev-list-extra" id="rev-extra-${key}" hidden>${rest}</div><button type="button" class="rev-more" data-target="rev-extra-${key}" data-total="${items.length}">Показать все ${items.length}</button>`
      : '';
    return `<div class="rev-list-block">${first}${more}</div>`;
  }

  function diagHtml(data) {
    const d = data?.diagnostics || {};
    const tx = (d.transactionValues || []).slice(0,10).join(', ');
    const stores = (d.storeValues || []).slice(0,12).join(', ');
    const accounts = (d.accountValues || []).slice(0,12).join(', ');
    const docs = (d.documentValues || []).slice(0,12).join(', ');
    const matchedDocs = (d.matchedDocuments || []).slice(0,12).join(', ');
    const parts = [];
    if (matchedDocs) parts.push(`Распознаны документы: ${escapeHtml(matchedDocs)}`);
    if (accounts) parts.push(`Счета/контра-счета: ${escapeHtml(accounts)}`);
    if (docs) parts.push(`Документы в OLAP: ${escapeHtml(docs)}`);
    if (tx) parts.push(`Типы операций: ${escapeHtml(tx)}`);
    if (stores) parts.push(`Склады в OLAP: ${escapeHtml(stores)}`);
    return parts.length ? `<span class="diag">${parts.join('<br>')}</span>` : '';
  }

  function renderQuality(summary) {
    if (!quality) return;
    const s = summary || {};
    quality.innerHTML = `
      <div class="rev-quality-card"><span>Оборот расхождений</span><b>${money(s.grossVariance)}</b><small>Недостачи + излишки за период</small></div>
      <div class="rev-quality-card"><span>Средняя недостача / ревизию</span><b>${money(s.avgShortagePerRevision)}</b><small>Не общий итог, а среднее на одну дату ревизии</small></div>
      <div class="rev-quality-card"><span>Концентрация недостачи</span><b>${pct(s.top5ShortageShare)}</b><small>Доля TOP-5 позиций во всей недостаче</small></div>
      <div class="rev-quality-card"><span>Документов найдено</span><b>${Number(s.documentsCount || 0).toLocaleString('ru-RU')}</b><small>Инвентаризационные документы iiko за период</small></div>`;
  }

  function render(data) {
    const cards = [...document.querySelectorAll('.cards .card')];
    const s = data.summary || {};
    setCard(cards[0], dateRu(s.lastRevision), s.revisionsCount ? `${s.revisionsCount} дат · ${s.documentsCount || 0} проведённых документов` : 'Проведённых ревизий за период нет');
    setCard(cards[1], money(s.shortage), 'Сумма отрицательных расхождений', s.shortage ? 'red' : '');
    setCard(cards[2], money(s.surplus), 'Сумма положительных расхождений', s.surplus ? 'green' : '');
    setCard(cards[3], money(s.net), 'Излишки минус недостача', s.net < 0 ? 'red' : s.net > 0 ? 'green' : '');
    renderQuality(s);

    const panels = [...document.querySelectorAll('.grid .panel')];
    const historyHost = panels[0]?.querySelector('.empty') || panels[0];
    if (historyHost) {
      if (data.history?.length) {
        historyHost.classList?.remove('empty');
        historyHost.innerHTML = `<table class="revision-history"><thead><tr><th>Дата / документы</th><th class="num">Недостача</th><th class="num">Излишки</th><th class="num">Оборот</th><th class="num">Итог</th></tr></thead><tbody>${data.history.map(row => {
          const docs = (row.documents || []).join(' · ');
          const stores = (row.stores || []).join(' · ');
          return `<tr><td><b>${dateRu(row.date)}</b>${docs ? `<div class="rev-small">${escapeHtml(docs)}</div>` : ''}${stores ? `<div class="rev-small">${escapeHtml(stores)}</div>` : ''}</td><td class="num negative">${money(row.shortage)}</td><td class="num positive">${money(row.surplus)}</td><td class="num">${money(row.gross ?? (Number(row.shortage||0)+Number(row.surplus||0)))}</td><td class="num ${row.net < 0 ? 'negative' : row.net > 0 ? 'positive' : ''}">${money(row.net)}</td></tr>`;
        }).join('')}</tbody></table>`;
      } else {
        historyHost.classList?.add('empty');
        historyHost.innerHTML = `<div><strong>За выбранный месяц ревизии пока не распознаны</strong>iikoServer доступен. Проверяем не только тип операции, но и номер документа и счета недостач/излишков.${diagHtml(data)}</div>`;
      }
    }

    if (panels[1]?.querySelector('h3')) panels[1].querySelector('h3').textContent = 'Ключевые отклонения';
    const list = panels[1]?.querySelector('.revision-list');
    if (list) {
      const recurring = data.recurringShortages || [];
      list.innerHTML = `
        <div class="revision-row"><b>TOP недостач</b><span>${listHtml(data.topShortages,'neg','Недостач нет','shortage')}</span><span class="pill">₸</span></div>
        <div class="revision-row"><b>TOP излишков</b><span>${listHtml(data.topSurpluses,'pos','Излишков нет','surplus')}</span><span class="pill">₸</span></div>
        <div class="revision-row"><b>Повторялось в минусе</b><span>${listHtml(recurring,'repeat','Повторяющихся недостач нет','recurring')}</span><span class="pill">ревизии</span></div>
        <div class="revision-row"><b>% расхождения</b><span class="muted">Нужен полный книжный остаток на момент каждой ревизии</span><span class="pill">%</span></div>`;
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

  document.addEventListener('click', event => {
    const more = event.target.closest('.rev-more');
    if (!more) return;
    const extra = document.getElementById(more.dataset.target || '');
    if (!extra) return;
    const opening = extra.hidden;
    extra.hidden = !opening;
    more.textContent = opening ? 'Скрыть' : `Показать все ${more.dataset.total || ''}`.trim();
  });

  button.addEventListener('click', async () => {
    const select = $('revisionPoint');
    const pointKey = select?.value || 'arai_kitchen';
    const point = select?.selectedOptions?.[0]?.textContent?.trim() || 'Точка';
    const period = $('revisionPeriod')?.value;
    if (!period) { show('err','Выбери месяц ревизии.'); return; }

    button.disabled = true;
    const oldText = button.textContent;
    button.textContent = 'Получаем…';
    show('', `<b>${point} · ${monthLabel(period)}</b><span class="scope">Контур: ${scopes[pointKey] || point}</span>Ищем документы и проводки инвентаризации в iikoServer…`);
    try {
      const data = await loadData(pointKey, period);
      if (!data) return;
      render(data);
      const stores = data.stores?.length ? data.stores.join(' + ') : (scopes[pointKey] || point);
      const count = Number(data.summary?.revisionsCount || 0);
      if (count > 0) {
        show('ok', `<b>${point} · ${monthLabel(period)}</b><span class="scope">${escapeHtml(stores)}</span>Найдено дат проведённых ревизий: <b>${count}</b>, документов: <b>${Number(data.summary?.documentsCount || 0)}</b>. Недостача: <b>${money(data.summary?.shortage)}</b>, излишки: <b>${money(data.summary?.surplus)}</b>.`);
      } else {
        show('warn', `<b>${point} · ${monthLabel(period)}</b><span class="scope">${escapeHtml(stores)}</span>Соединение работает, но ревизии ещё не сопоставились с полями вашей версии iiko.${diagHtml(data)}`);
      }
    } catch (error) {
      show('err', `<b>Не удалось получить ревизии.</b><br>${escapeHtml(String(error?.message || error))}`);
    } finally {
      button.disabled = false;
      button.textContent = oldText;
    }
  });
})();