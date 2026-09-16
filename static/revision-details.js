(() => {
  if (window.__dcRevisionDetails) return;
  window.__dcRevisionDetails = true;

  const style = document.createElement('style');
  style.textContent = `
    .revision-history tbody tr.rev-master{cursor:pointer;transition:background .15s ease}
    .revision-history tbody tr.rev-master:hover{background:rgba(255,90,31,.045)}
    .rev-open-hint{display:inline-flex;margin-left:7px;padding:2px 6px;border:1px solid #353535;border-radius:999px;color:#9b8e82;font-size:8px;font-weight:800;letter-spacing:.04em;vertical-align:1px}
    .rev-master.is-open .rev-open-hint{border-color:#6a3a26;color:#ff9c73}
    .rev-detail-row td{padding:0!important;border-bottom:1px solid #292929!important;background:#090909}
    .rev-detail-wrap{padding:14px 12px 18px;display:grid;gap:12px}
    .rev-detail-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
    .rev-detail-head h4{margin:0;font-size:14px}.rev-detail-head p{margin:4px 0 0;color:#777;font-size:10px;line-height:1.45}
    .rev-doc{border:1px solid #292929;border-radius:14px;background:#0e0e0e;overflow:hidden}
    .rev-doc-head{display:grid;grid-template-columns:minmax(0,1fr) repeat(4,auto);gap:16px;align-items:center;padding:12px 14px;border-bottom:1px solid #242424}
    .rev-doc-name b{display:block;font-size:12px}.rev-doc-name small{display:block;color:#777;margin-top:3px;font-size:9px}
    .rev-doc-metric{text-align:right}.rev-doc-metric span{display:block;color:#666;font-size:8px;text-transform:uppercase;letter-spacing:.06em}.rev-doc-metric b{display:block;margin-top:2px;font-size:11px}
    .rev-doc-metric.neg b{color:#ff8b8b}.rev-doc-metric.pos b{color:#8be0b2}.rev-doc-metric.ok b{color:#9fe4bf}
    .rev-lines-scroll{overflow-x:auto}.rev-lines{width:100%;min-width:720px;border-collapse:collapse}.rev-lines th{padding:9px 12px;color:#696969;font-size:8px;text-transform:uppercase;letter-spacing:.06em;text-align:left;border-bottom:1px solid #202020}.rev-lines td{padding:9px 12px!important;font-size:10px!important;border-bottom:1px solid #1c1c1c!important;background:transparent!important}.rev-lines tr:last-child td{border-bottom:0!important}.rev-lines .r{text-align:right}.rev-lines .neg{color:#ff8b8b}.rev-lines .pos{color:#8be0b2}.rev-lines .muted{color:#777}
    .rev-doc:not(.show-zero) .rev-zero-row{display:none}.rev-zero-toggle{margin:10px 12px 12px;padding:6px 10px;border:1px solid #303030;border-radius:999px;background:#090909;color:#aaa;font-size:9px;font-weight:700;cursor:pointer}.rev-zero-toggle:hover{border-color:#5a453a;color:#fff}
    .rev-validation{padding:10px 12px;border:1px solid #2d2925;border-radius:12px;background:#110e0b;color:#a59689;font-size:9px;line-height:1.5}
    .rev-validation b{color:#ddd}.rev-delta-up{color:#ff8b8b}.rev-delta-down{color:#8be0b2}.rev-delta-flat{color:#777}
    @media(max-width:700px){.rev-doc-head{grid-template-columns:1fr 1fr}.rev-doc-name{grid-column:1/-1}.rev-doc-metric{text-align:left}.rev-detail-wrap{padding:10px 5px 14px}.rev-open-hint{display:none}}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const qty = value => Number(value || 0).toLocaleString('ru-RU',{maximumFractionDigits:3});
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
    return m ? `${m[3]}.${m[2]}.${m[1]}` : (value || '—');
  };

  function trendHtml(value) {
    if (value === null || value === undefined) return '<span class="rev-delta-flat">нет предыдущей ревизии</span>';
    const n = Number(value || 0);
    if (Math.abs(n) < 0.05) return '<span class="rev-delta-flat">без изменений</span>';
    const cls = n > 0 ? 'rev-delta-up' : 'rev-delta-down';
    const arrow = n > 0 ? '↑' : '↓';
    return `<span class="${cls}">${arrow} ${Math.abs(n).toLocaleString('ru-RU',{maximumFractionDigits:1})}% к предыдущей</span>`;
  }

  function isZeroLine(item) {
    return Math.abs(Number(item.quantityDelta || 0)) < .0005 && Number(item.shortage || 0) < .005 && Number(item.surplus || 0) < .005;
  }

  function lineRows(products) {
    if (!products?.length) return '<tr><td colspan="6" class="muted">В OLAP нет строк товаров для этого документа</td></tr>';
    return products.map(item => {
      const delta = Number(item.quantityDelta || 0);
      const deltaClass = delta < 0 ? 'neg' : delta > 0 ? 'pos' : 'muted';
      const net = Number(item.net || 0);
      const zero = isZeroLine(item) ? ' class="rev-zero-row"' : '';
      return `<tr${zero}>
        <td><b>${esc(item.name)}</b>${item.unit ? `<span class="muted"> · ${esc(item.unit)}</span>` : ''}</td>
        <td class="r ${deltaClass}">${delta > 0 ? '+' : ''}${qty(delta)}</td>
        <td class="r">${money(item.unitCost)}</td>
        <td class="r neg">${item.shortage ? money(item.shortage) : '—'}</td>
        <td class="r pos">${item.surplus ? money(item.surplus) : '—'}</td>
        <td class="r ${net < 0 ? 'neg' : net > 0 ? 'pos' : ''}">${money(net)}</td>
      </tr>`;
    }).join('');
  }

  function docHtml(doc) {
    const zeroCount = (doc.products || []).filter(isZeroLine).length;
    return `<div class="rev-doc">
      <div class="rev-doc-head">
        <div class="rev-doc-name"><b>${esc(doc.document || 'Без номера')}</b><small>${esc(doc.store || 'Склад не определён')}</small></div>
        <div class="rev-doc-metric neg"><span>Недостача</span><b>${money(doc.shortage)}</b></div>
        <div class="rev-doc-metric pos"><span>Излишки</span><b>${money(doc.surplus)}</b></div>
        <div class="rev-doc-metric"><span>Итог</span><b>${money(doc.net)}</b></div>
        <div class="rev-doc-metric ok"><span>Расчёт</span><b>Δ × себест.</b></div>
      </div>
      <div class="rev-lines-scroll"><table class="rev-lines"><thead><tr><th>Позиция</th><th class="r">Δ количество*</th><th class="r">Себест./ед.</th><th class="r">Недостача</th><th class="r">Излишки</th><th class="r">Итог</th></tr></thead><tbody>${lineRows(doc.products)}</tbody></table></div>
      ${zeroCount ? `<button type="button" class="rev-zero-toggle" data-count="${zeroCount}">Показать нулевые позиции (${zeroCount})</button>` : ''}
    </div>`;
  }

  function detailsForDate(data, date) {
    return (data?.revisionDetails || []).find(item => item.date === date) || null;
  }

  function detailHtml(data, historyItem) {
    const detail = detailsForDate(data, historyItem.date);
    const docs = detail?.documents || [];
    return `<div class="rev-detail-wrap">
      <div class="rev-detail-head"><div><h4>Ревизия ${dateRu(historyItem.date)}</h4><p>${docs.length} докум. · ${trendHtml(historyItem.shortageChangePct)}</p></div></div>
      ${docs.length ? docs.map(docHtml).join('') : '<div class="rev-validation">Детализация документов для этой даты не найдена.</div>'}
      <div class="rev-validation"><b>* Δ количество</b> — разница количества из TRANSACTIONS OLAP. Денежное расхождение теперь считается по формуле <b>|Δ количество| × себестоимость за единицу</b>, как в строке «Разница сумма, тг.» окна iikoChain. Бухгалтерские Incoming/Outgoing суммы не складываются, потому что одна физическая недостача может присутствовать в двух сторонах проводки.</div>
    </div>`;
  }

  function decorate(data) {
    if (!data?.success || !data.history?.length) return;
    const rows = [...document.querySelectorAll('.revision-history tbody tr')].filter(row => !row.classList.contains('rev-detail-row'));
    if (!rows.length) return;
    rows.forEach((row,index) => {
      const historyItem = data.history[index];
      if (!historyItem) return;
      row.classList.add('rev-master');
      row.dataset.revisionDate = historyItem.date;
      if (!row.querySelector('.rev-open-hint')) {
        const first = row.cells?.[0];
        const b = first?.querySelector('b');
        if (b) b.insertAdjacentHTML('afterend','<span class="rev-open-hint">Детали</span>');
      }
    });
  }

  function scheduleDecorate(data) {
    [40,120,350,900].forEach(ms => setTimeout(() => decorate(data), ms));
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    try {
      const target = String(args?.[0]?.url || args?.[0] || '');
      if (target.includes('/revision-data')) {
        response.clone().json().then(data => {
          if (data?.success) {
            window.__dcRevisionDetailData = data;
            scheduleDecorate(data);
          }
        }).catch(() => {});
      }
    } catch (_) {}
    return response;
  };

  document.addEventListener('click', event => {
    const zeroButton = event.target.closest('.rev-zero-toggle');
    if (zeroButton) {
      const doc = zeroButton.closest('.rev-doc');
      if (!doc) return;
      const opening = !doc.classList.contains('show-zero');
      doc.classList.toggle('show-zero', opening);
      zeroButton.textContent = opening ? 'Скрыть нулевые позиции' : `Показать нулевые позиции (${zeroButton.dataset.count || 0})`;
      return;
    }

    const master = event.target.closest('.revision-history tr.rev-master');
    if (!master || event.target.closest('button,a,input,select')) return;
    const data = window.__dcRevisionDetailData;
    const date = master.dataset.revisionDate;
    if (!data || !date) return;

    const next = master.nextElementSibling;
    if (next?.classList.contains('rev-detail-row')) {
      next.remove();
      master.classList.remove('is-open');
      return;
    }

    document.querySelectorAll('.rev-detail-row').forEach(row => row.remove());
    document.querySelectorAll('.revision-history tr.rev-master.is-open').forEach(row => row.classList.remove('is-open'));

    const historyItem = (data.history || []).find(item => item.date === date);
    if (!historyItem) return;
    const detailRow = document.createElement('tr');
    detailRow.className = 'rev-detail-row';
    detailRow.innerHTML = `<td colspan="5">${detailHtml(data, historyItem)}</td>`;
    master.insertAdjacentElement('afterend', detailRow);
    master.classList.add('is-open');
  });
})();