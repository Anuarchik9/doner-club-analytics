(() => {
  if (window.__dcRevisionAudit) return;
  window.__dcRevisionAudit = true;

  const style = document.createElement('style');
  style.textContent = `
    .rev-accuracy-cards.rev-audit-five{grid-template-columns:repeat(5,minmax(0,1fr))}
    .rev-audit-money{display:block;color:#a8a8a2;font-size:10px;font-weight:750;margin-top:4px;text-transform:none!important;letter-spacing:0!important}
    .rev-audit-net-negative{color:#ff7f7f!important}.rev-audit-net-positive{color:#ffad72!important}.rev-audit-net-zero{color:#aaa!important}
    .rev-audit-cell{white-space:nowrap}.rev-audit-cell b{display:block;color:#f4f4ef;font-size:10px}.rev-audit-cell small{display:block;color:#777;font-size:8px;margin-top:2px}
    @media(max-width:1180px){.rev-accuracy-cards.rev-audit-five{grid-template-columns:repeat(3,minmax(0,1fr))}}
    @media(max-width:760px){.rev-accuracy-cards.rev-audit-five{grid-template-columns:1fr 1fr}}
    @media(max-width:520px){.rev-accuracy-cards.rev-audit-five{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const money = value => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₸`;
  const pct = value => value === null || value === undefined ? '—' : `${Number(value || 0).toLocaleString('ru-RU',{maximumFractionDigits:2})}%`;
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const dateRu = value => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
    return m ? `${m[3]}.${m[2]}` : String(value || '');
  };
  const signedMoney = value => {
    const n = Number(value || 0);
    const sign = n > 0 ? '+' : n < 0 ? '−' : '';
    return `${sign}${Math.round(Math.abs(n)).toLocaleString('ru-RU')} ₸`;
  };
  const signedPct = value => {
    if (value === null || value === undefined) return '—';
    const n = Number(value || 0);
    const sign = n > 0 ? '+' : n < 0 ? '−' : '';
    return `${sign}${Math.abs(n).toLocaleString('ru-RU',{maximumFractionDigits:2})}%`;
  };
  const netClass = value => Number(value || 0) < -0.01 ? 'rev-audit-net-negative' : Number(value || 0) > 0.01 ? 'rev-audit-net-positive' : 'rev-audit-net-zero';
  const statusHtml = status => status?.label ? `<span class="rev-status ${esc(status.key || '')}">${esc(status.label)}</span>` : '<span class="rev-status">—</span>';

  function auditCell(amount, percent) {
    return `<div class="rev-audit-cell"><b>${money(amount)}</b><small>${pct(percent)}</small></div>`;
  }

  function apply(data) {
    if (!data?.success || !data.summary?.bookBalanceAvailable) return;
    const history = (data.history || []).filter(item => item.bookValue !== null && item.bookValue !== undefined);
    if (!history.length) return;

    const latest = history[0];
    const net = latest.net !== null && latest.net !== undefined ? Number(latest.net) : Number(latest.surplus || 0) - Number(latest.shortage || 0);
    const netPct = Number(latest.bookValue || 0) > 0.01 ? net / Number(latest.bookValue) * 100 : null;
    const host = document.getElementById('revisionAccuracy');
    if (!host) return;

    const cards = host.querySelector('.rev-accuracy-cards');
    if (cards) {
      cards.classList.add('rev-audit-five');
      const cardList = [...cards.querySelectorAll(':scope > .rev-accuracy-card')];
      if (cardList[1]) {
        const value = cardList[1].querySelector('b');
        const note = cardList[1].querySelector('small');
        if (value) value.textContent = money(latest.shortage);
        if (note) note.innerHTML = `<span class="rev-audit-money">${pct(latest.shortagePct)} от книжного остатка</span>`;
      }
      if (cardList[2]) {
        const value = cardList[2].querySelector('b');
        const note = cardList[2].querySelector('small');
        if (value) value.textContent = money(latest.surplus);
        if (note) note.innerHTML = `<span class="rev-audit-money">${pct(latest.surplusPct)} от книжного остатка</span>`;
      }
      if (cardList[3]) {
        const value = cardList[3].querySelector('b');
        const note = cardList[3].querySelector('small');
        if (value) value.textContent = money(latest.gross);
        if (note) note.innerHTML = `${statusHtml(latest.accuracyStatus)}<span class="rev-audit-money">${pct(latest.discrepancyPct)} · недостача + излишки</span>`;
      }
      let netCard = cards.querySelector('[data-rev-audit="net"]');
      if (!netCard) {
        netCard = document.createElement('div');
        netCard.className = 'rev-accuracy-card';
        netCard.dataset.revAudit = 'net';
        cards.appendChild(netCard);
      }
      netCard.innerHTML = `<span>Чистое расхождение</span><b class="${netClass(net)}">${signedMoney(net)}</b><small><span class="rev-audit-money">${signedPct(netPct)} · излишки − недостача</span></small>`;
    }

    const table = host.querySelector('.rev-accuracy-table');
    if (table) {
      table.innerHTML = `<thead><tr><th>Ревизия</th><th class="r">Книжный остаток</th><th class="r">Недостача</th><th class="r">Излишки</th><th class="r">Общее расх.</th><th class="r">Чистое</th><th class="r">Статус</th></tr></thead><tbody>${history.map(item => {
        const rowNet = item.net !== null && item.net !== undefined ? Number(item.net) : Number(item.surplus || 0) - Number(item.shortage || 0);
        const rowNetPct = Number(item.bookValue || 0) > 0.01 ? rowNet / Number(item.bookValue) * 100 : null;
        return `<tr><td>${dateRu(item.date)}</td><td class="r">${money(item.bookValue)}</td><td class="r">${auditCell(item.shortage,item.shortagePct)}</td><td class="r">${auditCell(item.surplus,item.surplusPct)}</td><td class="r">${auditCell(item.gross,item.discrepancyPct)}</td><td class="r"><div class="rev-audit-cell"><b class="${netClass(rowNet)}">${signedMoney(rowNet)}</b><small>${signedPct(rowNetPct)}</small></div></td><td class="r">${statusHtml(item.accuracyStatus)}</td></tr>`;
      }).join('')}</tbody>`;
    }

    const note = host.querySelector('.rev-accuracy-note');
    if (note) note.innerHTML = '<strong>Общее расхождение:</strong> недостача + излишки — показывает весь объём ошибок пересчёта. <strong>Чистое расхождение:</strong> излишки − недостача — показывает итоговый финансовый знак ревизии. Проценты считаются относительно книжной стоимости склада непосредственно перед проводкой. Рабочие пороги общего расхождения: ≤1% — Норма, 1–2% — Внимание, >2% — Критично.';
  }

  function schedule(data) {
    [120,340,780].forEach(ms => setTimeout(() => apply(data), ms));
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